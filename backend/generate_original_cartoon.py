"""Generate an original RYUUNDY cartoon short, never a re-edit of source footage.

Usage:
    python generate_original_cartoon.py "topik atau brief" /path/to/output

The output is a 9:16 MP4 with the existing Motlab character renderer, an
original/curated in-house script, and a receipt stating that no third-party
footage, dialogue, title or likeness was reused. It does NOT upload anything.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import facebook_originals as originals
import facebook_stories as stories


def originality_receipt(plan: dict, media: Path) -> dict:
    return dict(
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_footage=False,
        source_dialogue=False,
        third_party_title_or_likeness=False,
        characters='original RYUUNDY vector cast',
        script='original or curated in-house narration',
        renderer='motlab',
        plan_sha256=plan.get('plan_sha256'),
        media=str(media),
        upload_allowed=False,  # QC and rights owners still decide publication.
    )


def generate(topic: str, folder: Path) -> tuple[Path, dict]:
    cleaned = stories.normalize_topic(topic)
    if not cleaned:
        raise ValueError('Topik kartun tidak boleh kosong.')
    seed = hashlib.sha256(cleaned.casefold().encode('utf-8')).hexdigest()
    plan = originals.plan(seed, 'reel', custom_topic=cleaned, series=stories.SERIES_KEY)
    plan = originals.author(plan)
    media = originals.render(plan, folder)
    receipt = originality_receipt(plan, media)
    (folder / 'originality.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return media, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('topic', help='Brief/topik orisinal, tanpa judul atau footage pihak ketiga')
    parser.add_argument('output', type=Path, help='Folder keluaran')
    args = parser.parse_args()
    media, receipt = generate(args.topic, args.output)
    print(json.dumps(dict(media=str(media), originality=receipt), ensure_ascii=False))


if __name__ == '__main__':
    main()
