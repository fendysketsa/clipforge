"""Bounded transport recovery and redacted diagnostics for YouTube source reads."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

VERSION = 1
RETRY_DELAYS = (2, 5)
TRANSIENT = frozenset({'dns', 'connect_timeout', 'read_timeout', 'connection_reset',
                       'connection_refused', 'network_unreachable', 'server_error'})


def category(error: BaseException | str) -> str:
    parts = [str(error)]
    current = error.__cause__ or error.__context__ if isinstance(error, BaseException) else None
    for _ in range(4):
        if current is None:
            break
        parts.append(str(current))
        current = current.__cause__ or current.__context__
    text = " ".join(parts).casefold()
    # Policy and authentication errors do not authorize transport retries.
    if any(term in text for term in ('private video', 'video unavailable', 'video has been removed', 'copyright', 'content safety')):
        return 'source_unavailable'
    if any(term in text for term in ('sign in', 'login', "not a bot", 'age restricted')):
        return 'authentication'
    if '403' in text or 'forbidden' in text:
        return 'forbidden'
    if '429' in text or 'too many requests' in text:
        return 'rate_limited'
    if any(term in text for term in ('temporary failure in name resolution', 'name or service not known',
                                     'failed to resolve', 'getaddrinfo failed', 'nodename nor servname')):
        return 'dns'
    if 'connection refused' in text:
        return 'connection_refused'
    if any(term in text for term in ('network is unreachable', 'no route to host', 'errno 101', 'cannot assign requested address')):
        return 'network_unreachable'
    if any(term in text for term in ('connection reset', 'connection aborted', 'remote end closed', 'remote disconnected', 'broken pipe')):
        return 'connection_reset'
    if 'connecttimeout' in text or 'connection timed out' in text:
        return 'connect_timeout'
    if 'timed out' in text or 'readtimeout' in text or 'read timeout' in text:
        return 'read_timeout'
    if re.search(r'(?:http (?:error )?|status(?: code)?[=: ]+)(?:500|502|503|504)\b', text):
        return 'server_error'
    if 'requested format is not available' in text:
        return 'format_unavailable'
    if 'ffmpeg exited' in text:
        return 'media_reader'
    return 'unknown'


def is_download_failure(error: str | None, diagnostics: dict | None = None) -> bool:
    if str(error or '').startswith(('Koneksi server ke YouTube gagal saat', 'Koneksi jalur unduh YouTube terputus saat')):
        return True
    return bool(diagnostics and diagnostics.get('transport_failure') and not diagnostics.get('recovered')
                and category(error or '') in TRANSIENT)


def redact(value: str) -> str:
    text = re.sub(r'\x1b\[[0-9;]*m', '', str(value))
    def safe_url(match):
        try:
            url = urlsplit(match[0])
            return f'{url.scheme}://{url.hostname or "redacted"}{url.path}'
        except ValueError:
            return '[redacted-url]'
    text = re.sub(r'https?://[^\s\]\)\"\']+', safe_url, text)
    text = re.sub(r'(?i)\b(cookie|authorization|api[_-]?key|access[_-]?token|token|password|passwd|proxy[_-]?password)\s*[:=]\s*[^\r\n]+', r'\1=[redacted]', text)
    return text[:1000]


def source_id(value: str) -> str:
    try:
        url = urlsplit(value)
        if url.hostname == 'youtu.be':
            candidate = url.path.strip('/')
        elif url.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
            candidate = parse_qs(url.query).get('v', [''])[0]
            if not candidate:
                match = re.fullmatch(r'/(?:shorts|live|embed)/([\w-]{11})/?', url.path)
                candidate = match[1] if match else ''
        else:
            return ''
        return candidate if re.fullmatch(r'[\w-]{11}', candidate) else ''
    except ValueError:
        return ''


def record(path: Path | None, url: str, *, stage: str, strategy: str, attempt: int,
           error: BaseException | None = None, recovered: bool = False, messages: list[str] | None = None) -> None:
    if path is None:
        return
    target = path / 'source_download_diagnostics.json'
    identity = source_id(url)
    if not identity:
        return
    payload = {'version': VERSION, 'source_id': identity, 'source_url': f'https://www.youtube.com/watch?v={identity}', 'events': []}
    if target.is_file():
        try:
            existing = json.loads(target.read_text())
            if existing.get('source_id') == identity and isinstance(existing.get('events'), list):
                payload = existing
        except (OSError, ValueError, AttributeError):
            pass
    event = dict(stage=stage, strategy=strategy, attempt=attempt, recovered=recovered,
                 checked_at=datetime.now(timezone.utc).isoformat())
    if error is not None:
        event.update(category=category(error), error_type=type(error).__name__, message=redact(str(error)))
        causes = []; current = error.__cause__ or error.__context__
        while current is not None and len(causes) < 4:
            causes.append({'type': type(current).__name__, 'message': redact(str(current))[:400]})
            current = current.__cause__ or current.__context__
        if causes:
            event['causes'] = causes
    if messages:
        event['downloader_messages'] = [redact(value)[:400] for value in messages[-3:]]
    payload['events'] = [*payload['events'], event][-24:]
    path.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    temporary.chmod(0o600)
    temporary.replace(target)


def capabilities() -> dict:
    return {'version': VERSION, 'transport_retry_delays': list(RETRY_DELAYS),
            'bounded_transport_retries': True, 'redacted_diagnostics': True,
            'same_strategy_partial_resume': True, 'rights_and_auth_gates_preserved': True}
