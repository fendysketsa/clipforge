"""Real audience-retention data is read when available, never invented."""
import io
import json

import api


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def payload(rows, names=("elapsedVideoTimeRatio", "audienceRetention")):
    return json.dumps({"columnHeaders": [{"name": name} for name in names], "rows": rows}).encode()


def test_retention_curve_and_first_thirty_seconds_are_measured(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return Response(payload([[0.0, 100.0], [0.1, 71.5], [0.5, 42.0], [1.0, 18.0]]))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    first, curve = api.youtube_audience_retention_snapshot("token", "abcDEF12345",
                                                           "2026-11-01", "2026-11-24", 300)
    assert first == 71.5
    assert len(curve) == 4
    assert curve[1] == {"ratio": 0.1, "retention": 71.5}
    assert "audienceRetention" in calls[0] and "elapsedVideoTimeRatio" in calls[0]


def test_missing_or_denied_report_never_fabricates_retention(monkeypatch):
    import urllib.error
    def denied(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)
    monkeypatch.setattr(api.urllib.request, "urlopen", denied)
    assert api.youtube_audience_retention_snapshot("token", "abcDEF12345",
                                                   "2026-11-01", "2026-11-24", 300) == (None, None)


def test_malformed_rows_are_discarded(monkeypatch):
    monkeypatch.setattr(api.urllib.request, "urlopen",
                        lambda request, timeout: Response(payload([[0.0, "bad"], [None, 50], [0.5, 42]])))
    first, curve = api.youtube_audience_retention_snapshot("token", "abcDEF12345",
                                                           "2026-11-01", "2026-11-24")
    assert curve == [{"ratio": 0.5, "retention": 42.0}]
    assert first is None  # duration unknown: curve is stored, 30s value is not guessed


def test_diagnosis_reports_measured_retention_without_claiming_prediction():
    upload = api.YouTubeUploadJob(
        id="upload-long-retention",
        source_job_id="job-long-retention",
        clip_url="/outputs/demo/clips/long.mp4",
        clip_name="long.mp4",
        status="completed",
        created_at="2026-11-01T00:00:00+00:00",
        updated_at="2026-11-01T00:00:00+00:00",
        title="Cerita Panjang",
        video_url="https://www.youtube.com/watch?v=long12345",
        growth_series="RYUUNDY Long",
    )
    snapshot = api.YouTubePerformanceSnapshot(
        captured_at="2026-11-24T00:00:00+00:00",
        source="youtube_analytics",
        views=1000,
        retention_first_30_seconds=48.0,
        retention_curve=[{"ratio": 0.0, "retention": 100.0}, {"ratio": 0.2, "retention": 48.0}],
    )
    diagnosis = api.youtube_performance_diagnosis(upload, snapshot, [])
    assert any("48.0%" in row and "bukan perkiraan" in row for row in diagnosis)
    assert any("turun lebih dari 15 poin" in row for row in diagnosis)


def test_manual_and_public_snapshots_keep_retention_fields_optional():
    snapshot = api.YouTubePerformanceSnapshot(captured_at="2026-11-24T00:00:00+00:00",
                                              source="youtube_public", views=10)
    assert snapshot.retention_first_30_seconds is None
    assert snapshot.retention_curve is None
