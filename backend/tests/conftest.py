import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_state_files(monkeypatch, tmp_path):
    """Never let unit tests overwrite the application's persisted runtime state."""
    api = sys.modules.get("api")
    if api is not None:
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
    yield
