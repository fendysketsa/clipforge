"""Millisecond carry must produce valid SRT at second/minute/hour boundaries."""

import pytest

from clipper import seconds_to_stamp


@pytest.mark.parametrize(('seconds', 'expected'), [
    (96.9999, '00:01:37,000'),
    (59.9999, '00:01:00,000'),
    (3599.9999, '01:00:00,000'),
    (96.58, '00:01:36,580'),
    (1.0004, '00:00:01,000'),
    (-.2, '00:00:00,000'),
])
@pytest.mark.parametrize('srt', [True, False])
def test_subtitle_timestamp_carries_milliseconds(seconds, expected, srt):
    assert seconds_to_stamp(seconds, srt=srt) == (expected if srt else expected.replace(',', '.'))
