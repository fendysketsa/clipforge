#!/usr/bin/env python3
"""Commit changed source files and fast-forward push them to a pinned branch."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import time


MAX_BYTES = 20 * 1024 * 1024
QUIET_SECONDS = 30 * 60
SECRET = re.compile(rb'-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----|'
    rb'\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b|'
    rb'\bsk-(?:or-v1-|proj-)[A-Za-z0-9_-]{40,}\b')


def protected(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name.lower()
    examples = {'.env.example', '.env.docker.example'}
    return bool(
        name not in examples and (name == '.env' or name.startswith('.env.'))
        or any(part in {'.ssh', '.aws', 'node_modules', '.venv', '__pycache__'}
               or part.startswith('.next') for part in parts)
        or path.startswith(('backend/data/', 'backend/outputs/', 'backend/uploads/',
                            'outputs/', 'reports/runtime-record-protection-', 'reports/backend-build-'))
        or name in {'id_rsa', 'id_ed25519', 'id_ecdsa', 'credentials', 'cookies.txt',
                    'youtube_storage_state.json', 'tiktok_storage_state.json', 'backend/jobs.json'}
        or name.endswith(('.key', '.p12', '.pfx'))
        or path in {'backend/jobs.json', 'backend/jobs.json.tmp'}
    )


def source_activity(path: str) -> bool:
    # Render/QC reports can change continuously while nobody is editing code.
    return not protected(path) and not path.startswith('reports/')


class GitError(RuntimeError):
    pass


class Sync:
    def __init__(self, repo: Path, remote: str, branch: str, settle_seconds: int, max_bytes: int):
        self.repo, self.remote, self.branch = repo.resolve(), remote, branch
        self.settle_seconds, self.max_bytes = settle_seconds, max_bytes
        self.env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
        if not self.env.get('GIT_SSH_COMMAND'):
            custom = self.git('config', '--get', 'core.sshCommand', check=False)
            if not custom:
                self.env['GIT_SSH_COMMAND'] = 'ssh -o BatchMode=yes -o ConnectTimeout=15'
        self.gitdir = Path(os.fsdecode(self.git('rev-parse', '--absolute-git-dir')).strip())

    def git(self, *args: str, check=True, input=None) -> bytes:
        try:
            result = subprocess.run(['git', '-C', str(self.repo), *args], input=input,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise GitError(f'git {args[0]} timed out; retained local commits') from exc
        if check and result.returncode:
            # Never persist raw Git stderr: an HTTPS remote may contain a token.
            reason = 'authentication' if any(word in result.stderr.lower()
                for word in (b'permission denied', b'authentication failed', b'could not read username')) else 'command failed'
            raise GitError(f'git {args[0]}: {reason} (exit {result.returncode})')
        return result.stdout if result.returncode == 0 else b''

    def save(self, state: str, **details):
        record = dict(state=state, checked_at=datetime.now(ZoneInfo('Asia/Jakarta')).isoformat(),
                      remote=self.remote, branch=self.branch, **details)
        target = self.gitdir / 'clipforge-auto-sync-status.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(target)
        return record

    def paths(self, *args):
        return [os.fsdecode(path) for path in self.git(*args).split(b'\0') if path]

    def source_snapshot(self):
        files = []
        for path in sorted(set(self.paths('ls-files', '--cached', '--others', '--exclude-standard', '-z'))):
            if not source_activity(path): continue
            try:
                stat = (self.repo / path).lstat()
                files.append((path, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_mode))
            except FileNotFoundError:
                # Missing paths must stay absent both before and after our
                # own git add stages a deletion. The previous snapshot still
                # detects the moment the formerly present file disappears.
                continue
        index = [os.fsdecode(entry) for entry in self.git('ls-files', '--stage', '-z').split(b'\0')
                 if entry and source_activity(os.fsdecode(entry.split(b'\t', 1)[1]))]
        digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=True).encode()).hexdigest()
        return dict(files=digest(files), index=digest(index), head=self.git('rev-parse', 'HEAD').decode().strip())

    def remember_activity(self, snapshot, last_activity):
        target = self.gitdir / 'clipforge-auto-sync-activity.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(version=1, snapshot=snapshot,
            last_activity_epoch=last_activity, quiet_seconds=self.settle_seconds)) + '\n')
        temporary.chmod(0o600)
        temporary.replace(target)

    def quiet_gate(self, snapshot):
        now = time.time()
        if not self.settle_seconds: return None, now
        try:
            previous = json.loads((self.gitdir / 'clipforge-auto-sync-activity.json').read_text())
        except (OSError, ValueError):
            previous = {}
        last = previous.get('last_activity_epoch')
        if (previous.get('version') != 1 or previous.get('snapshot') != snapshot
                or previous.get('quiet_seconds') != self.settle_seconds
                or not isinstance(last, (int, float)) or last > now):
            last = now
            self.remember_activity(snapshot, last)
        remaining = max(0, self.settle_seconds - (now - last))
        if remaining:
            return self.save('waiting_for_quiet', idle_seconds=round(now-last),
                remaining_seconds=round(remaining), quiet_seconds=self.settle_seconds,
                eligible_after=datetime.fromtimestamp(last+self.settle_seconds, ZoneInfo('Asia/Jakarta')).isoformat()), last
        return None, last

    def commit_message(self):
        changes = []
        for item in self.git('diff', '--cached', '--numstat', '--no-renames', '-z').split(b'\0'):
            if item:
                added, removed, path = item.split(b'\t', 2)
                changes.append((os.fsdecode(path), added.decode(), removed.decode()))
        statuses = self.git('diff', '--cached', '--name-status', '--no-renames', '-z').split(b'\0')
        actions = {os.fsdecode(statuses[i+1]): statuses[i].decode() for i in range(0, len(statuses)-1, 2)}
        sources = [path for path, _, _ in changes if source_activity(path)]
        scopes = {'git' if 'git-auto-sync' in path else 'frontend' if path.startswith('frontend/')
            else 'tests' if '/tests/' in path else 'backend' if path.startswith('backend/')
            else 'docs' if path.endswith('.md') else 'repo' for path in sources}
        scope = next(iter(scopes)) if len(scopes) == 1 else 'app'
        diff = self.git('diff', '--cached', '--no-ext-diff', '--no-color', '--unified=0', '--', *sources).decode(errors='replace') if sources else ''
        additions = '\n'.join(line[1:] for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
        if 'git' in scopes:
            scope = 'git'
            topics = []
            if 'quiet_gate' in additions or 'QUIET_SECONDS' in additions:
                seconds = re.search(r'^\s*QUIET_SECONDS\s*=\s*(\d+)(?:\s*\*\s*(\d+))?', additions, re.MULTILINE)
                if seconds:
                    value = int(seconds.group(1)) * int(seconds.group(2) or 1)
                    topics.append(f'jeda auto-sync {value // 60} menit' if value % 60 == 0 else f'jeda auto-sync {value} detik')
                else:
                    topics.append('jeda mengikuti aktivitas kode')
            if 'def commit_message' in additions: topics.append('ringkasan pesan commit')
            subject = 'chore(git): perbarui ' + (' dan '.join(topics) or 'otomatisasi commit dan push')
        elif any('HistorySection' in path for path in sources) or '.jobProgressMeta' in additions or 'history-four-columns' in additions:
            columns = re.search(r'\.jobList\s*\{[^}]*grid-template-columns:\s*repeat\((\d+)', additions)
            subject = f'style(history): atur {columns.group(1)} kartu per baris' if columns else 'style(history): perjelas tampilan dan progres kartu'
        else:
            names = list(dict.fromkeys(Path(path).stem.replace('_', '-') for path in sources))
            label = ', '.join(names[:3]) or 'laporan perubahan'
            only_added = all(actions.get(path) == 'A' for path in sources) and bool(sources)
            only_removed = all(actions.get(path) == 'D' for path in sources) and bool(sources)
            kind = 'docs' if scope == 'docs' else 'test' if scope == 'tests' else 'style' if sources and all(path.endswith('.css') for path in sources) else 'feat' if only_added else 'chore'
            verb = 'tambahkan' if only_added else 'hapus' if only_removed else 'perbarui'
            subject = f'{kind}({scope}): {verb} {label}'
        if len(subject) > 100: subject = subject[:97].rsplit(' ', 1)[0] + '...'
        body = [subject, '', 'Ringkasan perubahan staged:']
        for path, added, removed in changes[:50]:
            count = 'binary' if added == '-' else f'+{added}/-{removed} baris'
            body.append(f'- {actions.get(path, "M")} {path} ({count})')
        if len(changes) > 50: body.append(f'- {len(changes)-50} file tambahan')
        symbols = list(dict.fromkeys(re.findall(r'^[+-]\s*(?:async\s+def|def|(?:export\s+)?(?:async\s+)?function)\s+([A-Za-z_]\w*)', diff, re.MULTILINE)))
        if symbols: body += ['', 'Simbol kode yang diubah: ' + ', '.join(symbols[:12])]
        return '\n'.join(body)

    def blob_issue(self, oid, path):
        if protected(path): return f'protected path: {path}'
        if int(self.git('cat-file', '-s', oid)) > self.max_bytes:
            return f'file exceeds {self.max_bytes} byte limit: {path}'
        if SECRET.search(self.git('cat-file', 'blob', oid)):
            return f'credential detected: {path}'
        return None

    def staged_issue(self):
        changed = set(self.paths('diff', '--cached', '--name-only', '-z'))
        for path in changed:
            if protected(path): return f'protected staged path: {path}'
        for entry in self.git('ls-files', '--stage', '-z').split(b'\0'):
            if not entry: continue
            info, raw_path = entry.split(b'\t', 1)
            mode, oid, stage = info.decode().split()
            path = os.fsdecode(raw_path)
            if path in changed and mode != '160000':
                issue = self.blob_issue(oid, path)
                if issue: return issue
        return None

    def run(self, dry_run=False):
        lock = (self.gitdir / 'clipforge-auto-sync.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return dict(state='already_running')
        try:
            return self._run(dry_run)
        except (GitError, OSError) as exc:
            return self.save('retry_later', error=str(exc))
        finally:
            lock.close()

    def _run(self, dry_run):
        branch = os.fsdecode(self.git('symbolic-ref', '--quiet', '--short', 'HEAD', check=False)).strip()
        if branch != self.branch: return self.save('wrong_branch', current_branch=branch)
        if self.remote not in self.git('remote').decode().splitlines():
            return self.save('configuration_error', error='Configured remote does not exist')
        self.git('check-ref-format', '--branch', self.branch)
        if any((self.gitdir / marker).exists() for marker in
               ('index.lock', 'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'BISECT_START')):
            return self.save('git_operation_in_progress')
        if self.paths('diff', '--name-only', '--diff-filter=U', '-z'):
            return self.save('git_operation_in_progress')
        observed = self.source_snapshot()
        waiting, last_activity = self.quiet_gate(observed)
        if waiting: return waiting
        issue = self.staged_issue()
        if issue: return self.save('held', error=issue)
        changed = set(self.paths('ls-files', '--modified', '--deleted', '--others', '--exclude-standard', '-z'))
        changed.update(self.paths('diff', '--cached', '--name-only', '-z'))
        eligible = sorted(path for path in changed if not protected(path))
        ignored = len(changed) - len(eligible)
        for path in eligible:
            file = self.repo / path
            if file.is_symlink() or not file.exists(): continue
            if not file.is_file(): return self.save('held', error=f'Nested repository or directory: {path}')
            if file.stat().st_size > self.max_bytes:
                return self.save('held', error=f'File exceeds size limit: {path}')
            if SECRET.search(file.read_bytes()):
                return self.save('held', error=f'Credential detected: {path}')
        if dry_run:
            return self.save('dry_run', eligible_files=eligible, protected_files_skipped=ignored,
                             quiet_seconds=self.settle_seconds)
        committed = False
        code_changed = any(source_activity(path) for path in eligible)
        if eligible and code_changed:
            self.git('add', '--all', '--pathspec-from-file=-', '--pathspec-file-nul',
                     input=b''.join(b':(literal)' + os.fsencode(path) + b'\0' for path in eligible))
            issue = self.staged_issue()
            if issue: return self.save('held', error=issue)
            if os.fsdecode(self.git('symbolic-ref', '--quiet', '--short', 'HEAD')).strip() != self.branch:
                return self.save('wrong_branch')
            if self.paths('diff', '--cached', '--name-only', '-z'):
                prepared = self.source_snapshot()
                if prepared['files'] != observed['files'] or prepared['head'] != observed['head']:
                    waiting, _ = self.quiet_gate(prepared)
                    return waiting or self.save('waiting_for_quiet')
                message = self.commit_message()
                current = self.source_snapshot()
                if current != prepared:
                    waiting, _ = self.quiet_gate(current)
                    return waiting or self.save('waiting_for_quiet')
                self.git('commit', '-m', message)
                committed = True
        current = self.source_snapshot()
        if current['files'] != observed['files']:
            waiting, _ = self.quiet_gate(current)
            return waiting or self.save('waiting_for_quiet')
        # Our own staging/commit must not restart the idle clock on a network
        # retry; the next external edit or manual commit still restarts it.
        self.remember_activity(current, last_activity)
        head = self.git('rev-parse', 'HEAD').decode().strip()
        remote_ref = f'refs/remotes/{self.remote}/{self.branch}'
        if not code_changed and head == self.git('rev-parse', '--verify', remote_ref, check=False).decode().strip():
            return self.save('synced', head=head, committed=False, pushed=False, changed_files=0,
                             generated_files_pending=len(eligible), quiet_seconds=self.settle_seconds,
                             protected_files_skipped=ignored)
        self.git('fetch', '--no-tags', self.remote, f'refs/heads/{self.branch}:{remote_ref}')
        remote_head = self.git('rev-parse', remote_ref).decode().strip()
        ancestor = self.git('merge-base', head, remote_head).decode().strip()
        if ancestor != remote_head:
            return self.save('needs_sync', head=head, committed=committed,
                error='Remote advanced or diverged; automatic merge, rebase and force-push are disabled')
        # Inspect outgoing history too, including a commit retained after an
        # earlier network failure. Worktree cleanliness alone is insufficient.
        for line in self.git('rev-list', '--objects', f'{remote_ref}..{head}').splitlines():
            oid, _, raw_path = line.partition(b' ')
            if self.git('cat-file', '-t', oid.decode()).strip() != b'blob': continue
            issue = self.blob_issue(oid.decode(), os.fsdecode(raw_path))
            if issue: return self.save('held', head=head, error=issue)
        if self.source_snapshot() != current:
            waiting, _ = self.quiet_gate(self.source_snapshot())
            return waiting or self.save('waiting_for_quiet')
        if head != remote_head:
            self.git('push', '--porcelain', self.remote, f'{head}:refs/heads/{self.branch}')
        return self.save('synced', head=head, committed=committed,
            pushed=head != remote_head, changed_files=len(eligible), protected_files_skipped=ignored)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--branch', default='master')
    parser.add_argument('--settle-seconds', type=int, default=QUIET_SECONDS)
    parser.add_argument('--max-bytes', type=int, default=MAX_BYTES)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.remote.startswith('-') or not re.fullmatch(r'[A-Za-z0-9_.-]+', args.remote):
        parser.error('Invalid remote name')
    if args.settle_seconds < 0 or args.max_bytes < 1: parser.error('Invalid limits')
    sync = Sync(args.repo, args.remote, args.branch, args.settle_seconds, args.max_bytes)
    result = sync.run(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    if result['state'] in {'held', 'needs_sync', 'retry_later', 'configuration_error'}:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
