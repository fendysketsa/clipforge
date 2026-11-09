"""Durable, idempotent source-processing admissions; upload retries are unrelated."""
from __future__ import annotations

import fcntl
import json
from pathlib import Path

PROCESS_LIMIT = 2


class SourceProcessLimitReached(RuntimeError):
    pass


def merge_attempts(path: Path, observed: dict[str, set[str]], *,
                   source: str = '', job_id: str = '', enforce: bool = False) -> dict[str, set[str]]:
    """Merge known attempts, then reserve one real worker start under a file lock.

    Missing is a fresh ledger; unreadable/corrupt is unknown and must not reset
    the count. Records have no age/history-card truncation. Same-job recovery
    is idempotent even after reaching the cap.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            raw = json.loads(path.read_text())
        except FileNotFoundError:
            raw = {}
        except (OSError, ValueError) as exc:
            raise RuntimeError('Riwayat jumlah proses sumber tidak terbaca; cron ditahan agar tidak mengulang sumber.') from exc
        if not isinstance(raw, dict) or any(not isinstance(k,str) or not isinstance(v,list)
                or any(not isinstance(i,str) or not i for i in v) for k,v in raw.items()):
            raise RuntimeError('Format riwayat proses sumber tidak valid; hitungan tidak direset.')
        records = {key:set(value) for key,value in raw.items()}
        for key, ids in observed.items():
            if key and ids:
                records.setdefault(key,set()).update(ids)
        rejected = bool(source and job_id and enforce and job_id not in records.get(source,set())
                        and len(records.get(source,set())) >= PROCESS_LIMIT)
        if source and job_id and not rejected:
            records.setdefault(source,set()).add(job_id)
        payload = {key:sorted(ids) for key,ids in sorted(records.items())}
        if payload != raw:
            temp = path.with_suffix('.json.tmp')
            temp.write_text(json.dumps(payload,indent=2)+'\n')
            temp.replace(path)
        if rejected:
            raise SourceProcessLimitReached(f'Sumber sudah diproses {len(records[source])} kali; batas cron {PROCESS_LIMIT}. Lewati dan cari sumber lain.')
        return records
