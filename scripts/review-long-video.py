#!/usr/bin/env python3
"""Read-only offline audit of an existing Long; emit the AI QC JSON contract."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import long_video_qc as qc
from source_rights import source_rights_risk_reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    jobs = json.loads((ROOT / 'backend/data/jobs.json').read_text())
    job = next(row for row in jobs if row['id'] == args.job_id)
    if job['request']['clip_mode'] != 'highlight_5m' or job['status'] != 'completed':
        raise SystemExit('Expected one completed Long highlight job')
    request = job['request']
    results = []
    for clip in job['clips']:
        media = (ROOT / 'backend' / clip['url'].lstrip('/')).resolve()
        if ROOT / 'backend/outputs' not in media.parents:
            raise SystemExit('Unsafe output path')
        metadata_path = media.parent.parent / 'metadata.json'
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        context = {
            'source_job_id': job['id'], 'source_clip_url': clip['url'],
            'source_url': job.get('source_url') or request['url'],
            'rights_confirmed': request.get('confirm_source_rights') is True,
            'rights_evidence': request.get('source_rights_evidence', ''),
            'rights_risks': source_rights_risk_reasons(metadata),
            # This CLI never authorizes uploads: remote claims must be checked
            # again by the running worker before any upload can be enqueued.
            'claim_block': None, 'news_hot': request.get('scheduled_news_hot', False),
            'repair_attempted': bool(job.get('repair_source_job_id') or job.get('repair_source_clip_url')
                or any(line.startswith('AUTO_REPAIR_ATTEMPTED:') for line in job.get('logs', []))),
            'score_floor_met': (clip.get('fyp_score') or 0) >= 80
                and clip.get('growth_quality_gate_passed') is not False,
        }
        result = qc.audit_long(media, context)
        results.append(result['audit'] if result.get('audit') else result)
    text = json.dumps(results[0] if len(results) == 1 else results, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
