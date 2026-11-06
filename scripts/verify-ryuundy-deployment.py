#!/usr/bin/env python3
"""Verify the requested source version against activation evidence and the live API."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
MODULES = ('api', 'youtube_remote_status', 'ryuundy_reference_learning', 'clipper', 'ryuundy_motion')


def read_api(endpoint):
    with urllib.request.urlopen('http://127.0.0.1:8010/api/' + endpoint, timeout=15) as response:
        return json.load(response)


def main():
    hashes = {name: hashlib.sha256((ROOT / f'backend/{name}.py').read_bytes()).hexdigest()
              for name in MODULES}
    path = ROOT / 'reports/ryuundy-reference-learning-activation.json'
    activation = json.loads(path.read_text()) if path.is_file() else {}
    recorded = activation.get('sha256', {})
    matching = {name: recorded.get(name) == digest for name, digest in hashes.items()}
    validation_path = ROOT / 'reports/ryuundy-motion-validation-20261106.json'
    validation = json.loads(validation_path.read_text()) if validation_path.is_file() else {}
    test_hashes = validation.get('test_sha256', {})
    validated = (validation.get('source_sha256') == hashes and bool(test_hashes)
                 and all((ROOT / name).is_file()
                         and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                         for name, digest in test_hashes.items()))
    health, schedule, jobs = read_api('health'), read_api('automation/viral-cc/schedule'), read_api('jobs')
    schedule_expected = activation.get('schedule', {}).get('enabled')
    scheduler_ok = (isinstance(schedule_expected, bool) and schedule['enabled'] == schedule_expected
                    and (not schedule_expected or schedule['scheduler_running']))
    confirmed = validated and all(matching.values()) and health.get('status') == 'ok' and scheduler_ok
    report = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'activation_confirmed' if confirmed else 'activation_not_confirmed',
        'evidence': 'Activation-script runtime hashes plus current read-only API health/scheduler.',
        'module_hashes_match_activation': matching, 'expected_sha256': hashes,
        'activation_verified_at': activation.get('verified_at'),
        'health': health, 'schedule': schedule,
        'job_status_counts': dict(Counter(row['status'] for row in jobs)),
        'source_and_tests_complete': validated,
        'tests': validation.get('tests', {}),
        'visual_demo': 'reports/ryuundy-motion-demo-20261106.mp4',
        'visual_demo_scope': 'Original silent 18-second study, not a published or narrated source clip.',
        'export_smoke': 'reports/ryuundy-motion-export-smoke-20261106.json',
    }
    output = ROOT / 'reports/ryuundy-motion-completion-20261106.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'hash_matches': matching,
                      'scheduler_ok': scheduler_ok, 'report': str(output)}, ensure_ascii=False))
    return 0 if confirmed else 1


if __name__ == '__main__':
    raise SystemExit(main())
