"""Image integrity and Compose readiness. No publishing or checkpoint rewrites."""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
MANIFEST = 'deployment-manifest.json'


def source_files(root: Path) -> list[Path]:
    files = [*root.glob('*.py'), root / 'requirements.txt', root / 'docker-entrypoint.sh', root / 'Dockerfile']
    remotion = root / 'remotion'
    for name in ('package.json', 'package-lock.json', 'render.mjs'):
        files.append(remotion / name)
    files.extend((remotion / 'src').rglob('*'))
    files.extend((root / 'assets' / 'branding').rglob('*'))
    return sorted(path for path in files if path.is_file())


def fingerprint(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files(root)}


def release_id(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.deployment-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(payload, stream, indent=2)
            stream.write('\n')
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_manifest(root: Path) -> dict:
    for path in root.glob('*.py'):
        ast.parse(path.read_bytes(), filename=str(path))
    files = fingerprint(root)
    if 'api.py' not in files or 'telegram_bot.py' not in files:
        raise RuntimeError('Backend or telegram-bot source missing from build')
    result = dict(schema=1, release_id=release_id(files), files=files)
    write_json(root / MANIFEST, result)
    return result


def verify_manifest(root: Path, source: Path | None = None) -> dict:
    manifest = json.loads((root / MANIFEST).read_text())
    actual = fingerprint(root)
    if manifest.get('schema') != 1 or manifest.get('release_id') != release_id(actual) or manifest.get('files') != actual:
        raise RuntimeError('Image source differs from its build manifest; rebuild the stack')
    if source is not None and fingerprint(source) != actual:
        raise RuntimeError('Source changed since the image was built; rerun the same Compose command')
    return manifest


def verify_dependencies() -> None:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    from playwright.sync_api import BrowserType
    import cv2
    if 'no_defaults' not in inspect.signature(BrowserType.connect_over_cdp).parameters:
        raise RuntimeError('Playwright lacks safe CDP no_defaults support')
    if not all(hasattr(cv2, name) for name in ('VideoCapture', 'CascadeClassifier', 'HOGDescriptor')):
        raise RuntimeError('OpenCV runtime is incomplete')
    decoders = subprocess.check_output(['ffmpeg', '-hide_banner', '-decoders'], stderr=subprocess.STDOUT, text=True, timeout=15)
    if 'librsvg' not in decoders:
        raise RuntimeError('FFmpeg SVG decoder required by the director is missing')
    subprocess.run(['node', '--version'], check=True, stdout=subprocess.DEVNULL, timeout=5)
    if not (ROOT / 'remotion/node_modules/remotion/package.json').is_file():
        raise RuntimeError('Remotion dependencies missing from image')


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def backend_contract(base: str) -> dict:
    if get_json(base + '/api/health').get('status') != 'ok':
        raise RuntimeError('Backend is not healthy')
    config = get_json(base + '/api/tiktok/config')
    schedule = get_json(base + '/api/automation/viral-cc/schedule')
    expected = {'duplicate_guard_version': 2, 'cron_draft_policy': 'discard'}
    if any(config.get(key) != value for key, value in expected.items()):
        raise RuntimeError('TikTok duplicate or cron draft guard is stale')
    if schedule.get('cron_director_effects_policy_version') != 4 or schedule.get('cron_source_process_limit') != 2:
        raise RuntimeError('Cron director/source policy is stale')
    return {**expected, 'cron_enabled': schedule.get('enabled'),
            'scheduler_running': schedule.get('scheduler_running'),
            'director_policy': 4, 'source_process_limit': 2}


def report_path(role: str) -> Path:
    return Path(os.environ.get('CLIPFORGE_DEPLOYMENT_REPORT_DIR', '/app/data/deployment')) / (role + '.json')


def prepare(role: str, command: list[str]) -> dict:
    source = os.environ.get('CLIPFORGE_VERIFY_SOURCE_DIR', '').strip()
    manifest = verify_manifest(ROOT, Path(source) if source else None)
    if role == 'backend':
        verify_dependencies()
    elif role == 'telegram-bot':
        if not os.environ.get('TELEGRAM_BOT_TOKEN', '').strip() or not os.environ.get('TELEGRAM_OWNER_ID', '').strip().isdigit():
            raise RuntimeError('Telegram token or numeric owner ID is not configured')
    else:
        raise RuntimeError('Unknown deployment role')
    record = dict(schema=1, verified=True, role=role, release_id=manifest['release_id'],
                  source_verified=bool(source), hostname=socket.gethostname(),
                  app_pid=os.getppid(), prepared_at=time.time(), command=command)
    if role == 'telegram-bot':
        record['backend'] = backend_contract(os.environ.get('BACKEND_API_BASE', 'http://127.0.0.1:8010').rstrip('/'))
        backend = json.loads(report_path('backend').read_text())
        if backend.get('release_id') != record['release_id']:
            raise RuntimeError('Backend and telegram-bot were built from different source')
        frontend = get_json(os.environ.get('FRONTEND_BASE', 'http://127.0.0.1:3000').rstrip('/') + '/deployment.json')
        if frontend.get('schema') != 1 or not frontend.get('build_id') or not frontend.get('ui_verified'):
            raise RuntimeError('Frontend release verification is missing')
        record['frontend'] = frontend
    write_json(report_path(role), record)
    return record


def health(role: str) -> dict:
    manifest = verify_manifest(ROOT)
    record = json.loads(report_path(role).read_text())
    if not record.get('verified') or record.get('hostname') != socket.gethostname() or record.get('release_id') != manifest['release_id']:
        raise RuntimeError('Current container has no matching startup verification')
    if role == 'backend':
        capabilities = backend_contract('http://127.0.0.1:8010')
        write_json(report_path('backend-health'), dict(verified=True, checked_at=time.time(),
            release_id=record['release_id'], **capabilities))
    else:
        command = Path(f"/proc/{int(record['app_pid'])}/cmdline").read_bytes().split(b'\0')
        if not any(Path(os.fsdecode(arg)).name == 'telegram_bot.py' for arg in command if arg):
            raise RuntimeError('Telegram bot process is not running')
    return dict(healthy=True, role=role, release_id=record['release_id'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'prepare', 'health', 'wait-ready'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    role = os.environ.get('CLIPFORGE_SERVICE', 'backend')
    if args.action == 'build':
        result = build_manifest(ROOT)
    elif args.action == 'prepare':
        result = prepare(role, args.command)
    elif args.action == 'health':
        result = health(role)
    else:
        deadline = time.monotonic() + 60
        while True:
            try:
                result = health(role)
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Deployment check failed: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1)
