import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_state_files(monkeypatch, tmp_path):
    """Never let unit tests overwrite the application's persisted runtime state."""
    api = sys.modules.get("api")
    if api is not None:
        monkeypatch.setenv('TIKTOK_AUTOMATIC_RETRY_ENABLED','false')
        for name in ("jobs", "youtube_uploads", "tiktok_uploads", "auto_viral_runs", "source_usage_history"):
            monkeypatch.setattr(api, name, {})
        monkeypatch.setattr(api,'processed_source_history',set())
        monkeypatch.setattr(api,'SOURCE_USAGE_ARCHIVE_DIR_OVERRIDE','')
        monkeypatch.setattr(api, "auto_viral_schedule_enabled_override", None)
        monkeypatch.setattr(api, "AUTO_VIRAL_SCHEDULE_CONTROL_PATH", tmp_path / "schedule_control.json")
        monkeypatch.setattr(api, "JOBS_PATH", tmp_path / "jobs.json")
        monkeypatch.setattr(api, "YOUTUBE_UPLOADS_PATH", tmp_path / "youtube_uploads.json")
        monkeypatch.setattr(
            api,
            "PROCESSED_SOURCE_HISTORY_PATH",
            tmp_path / "processed_source_history.json",
        )
        monkeypatch.setattr(
            api,
            "SOURCE_USAGE_HISTORY_PATH",
            tmp_path / "source_usage_history.json",
        )
        monkeypatch.setattr(
            api,
            "AUTO_VIRAL_RUNS_PATH",
            tmp_path / "auto_viral_runs.json",
        )
    yield
