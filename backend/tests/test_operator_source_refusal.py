"""An explicit source refusal cannot be bypassed by the cron rights checkbox."""
import sys

import pytest

import api
import clipper


@pytest.mark.parametrize("mode", ["short", "highlight_5m"])
@pytest.mark.parametrize("review_only", [False, True])
def test_worker_rejects_dw_before_download_without_cc(monkeypatch, tmp_path, mode, review_only):
    args = ["clipper.py", "https://www.youtube.com/watch?v=SSU8Ko6wKm4",
            "--clip-mode", mode, "--output", str(tmp_path), "--confirm-source-rights"]
    if review_only:
        args.append("--review-only")
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(clipper, "fetch_metadata", lambda *a, **kw: {"title": "AI", "license": "Standard YouTube License"})
    monkeypatch.setattr(clipper, "download_video", lambda *a, **kw: pytest.fail("Forbidden source must not download"))
    monkeypatch.setattr(clipper, "download_review_audio", lambda *a, **kw: pytest.fail("Forbidden source must not scan"))
    with pytest.raises(clipper.UserFacingError, match="operator melarang"):
        clipper.main()


def test_discovery_and_final_admission_reject_dw_without_cc(monkeypatch):
    monkeypatch.setenv("YOUTUBE_TRUSTED_SOURCE_CHANNEL_IDS", "UCY5eSpSrHUKeEAh7t4N81cQ")
    source = {"channel_id": "UCY5eSpSrHUKeEAh7t4N81cQ", "title": "Penjelasan teknologi"}
    for gate in (api.viral_source_discovery_rejection_reason, api.viral_source_rejection_reason):
        assert "operator melarang" in gate(source, require_creative_commons=False)
