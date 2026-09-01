#!/usr/bin/env python3
"""Mirror the source usage index into year/month audit folders."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def partition(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        local = parsed.astimezone(ZoneInfo("Asia/Jakarta"))
    except ZoneInfoNotFoundError:
        local = parsed.astimezone(timezone(timedelta(hours=7)))
    return local.year, local.month


def load_items(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    return [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []


def write_month(path: Path, additions: list[dict[str, Any]], year: int, month: int) -> int:
    by_key = {
        (str(item.get("job_id") or ""), str(item.get("clip_mode") or "")): item
        for item in load_items(path)
        if str(item.get("job_id") or "")
    }
    for event in additions:
        by_key[(str(event.get("job_id") or ""), str(event.get("clip_mode") or ""))] = event
    items = sorted(by_key.values(), key=lambda item: str(item.get("processed_at") or ""), reverse=True)
    payload = {"schema_version": 1, "year": year, "month": month, "total": len(items), "items": items}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return len(items)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=Path, help="Path to source_usage_history.json")
    parser.add_argument("archive", type=Path, help="Destination source_usage directory")
    args = parser.parse_args()

    try:
        history = json.loads(args.index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Tidak dapat membaca indeks: {exc}") from exc
    if not isinstance(history, dict):
        raise SystemExit("Indeks sumber bukan object JSON yang valid")

    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for record in history.values():
        if not isinstance(record, dict):
            continue
        for event in record.get("events", []):
            if not isinstance(event, dict):
                continue
            if str(event.get("clip_mode") or "") not in {"short", "highlight_5m"}:
                continue
            grouped.setdefault(partition(str(event.get("processed_at") or "")), []).append(dict(event))

    total = 0
    for (year, month), events in sorted(grouped.items()):
        total += write_month(args.archive / f"{year:04d}" / f"{month:02d}" / "source_usage.json", events, year, month)
    print(f"Migrasi selesai: {len(grouped)} folder bulan, {total} event sukses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
