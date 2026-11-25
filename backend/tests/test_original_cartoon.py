"""Original cartoon regeneration must never inherit source-media rights."""
from pathlib import Path

import generate_original_cartoon as cartoon


def test_originality_receipt_never_claims_reused_media():
    receipt = cartoon.originality_receipt(
        {'plan_sha256': 'abc'}, Path('/tmp/original_cartoon.mp4'))
    assert receipt['source_footage'] is False
    assert receipt['source_dialogue'] is False
    assert receipt['third_party_title_or_likeness'] is False
    assert receipt['upload_allowed'] is False
    assert receipt['renderer'] == 'motlab'


def test_empty_topic_is_rejected_before_any_render(tmp_path):
    try:
        cartoon.generate('   ', tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError('empty topic must be rejected')
