import json
from pathlib import Path

import whisper_cache


MODEL = "Systran/faster-whisper-medium"


def make_snapshot(hub: Path, revision: str) -> Path:
    model_cache = hub / "models--Systran--faster-whisper-medium"
    snapshot = model_cache / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (model_cache / "refs").mkdir(exist_ok=True)
    (model_cache / "refs" / "main").write_text(revision + "\n", encoding="utf-8")
    for filename in whisper_cache.REQUIRED_WHISPER_MODEL_FILES:
        content = b"{}" if filename.endswith(".json") else b"ready" * 300
        (snapshot / filename).write_bytes(content)
    return snapshot


def configure_cache(monkeypatch, tmp_path):
    hub = tmp_path / "huggingface" / "hub"
    state = tmp_path / "huggingface" / "update.json"
    monkeypatch.setenv("HF_HOME", str(tmp_path / "huggingface"))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    monkeypatch.setenv("FENDY_CLIPPER_WHISPER_UPDATE_STATE_PATH", str(state))
    monkeypatch.setenv("FENDY_CLIPPER_WHISPER_MODEL", MODEL)
    return hub, state


def test_refresh_downloads_new_snapshot_and_records_revision(monkeypatch, tmp_path):
    hub, state_path = configure_cache(monkeypatch, tmp_path)
    old_snapshot = make_snapshot(hub, "old-revision")

    def downloader(**kwargs):
        assert kwargs["repo_id"] == MODEL
        assert kwargs["cache_dir"] == str(hub)
        assert "*.py" not in kwargs["allow_patterns"]
        return str(make_snapshot(hub, "new-revision"))

    result = whisper_cache.refresh_whisper_model_cache(force=True, downloader=downloader)

    assert result["status"] == "updated"
    assert result["revision"] == "new-revision"
    assert result["active_revision"] == "new-revision"
    assert old_snapshot.is_dir()
    assert json.loads(state_path.read_text(encoding="utf-8"))["cached"] is True


def test_failed_refresh_keeps_last_complete_snapshot(monkeypatch, tmp_path):
    hub, _state_path = configure_cache(monkeypatch, tmp_path)
    old_snapshot = make_snapshot(hub, "stable-revision")

    def downloader(**_kwargs):
        raise ConnectionError("offline")

    result = whisper_cache.refresh_whisper_model_cache(force=True, downloader=downloader)

    assert result["status"] == "update_failed_cache_kept"
    assert result["revision"] == "stable-revision"
    assert old_snapshot.is_dir()
    assert whisper_cache.cached_whisper_model_path(MODEL) == old_snapshot


def test_invalid_new_snapshot_keeps_previous_active_revision(monkeypatch, tmp_path):
    hub, _state_path = configure_cache(monkeypatch, tmp_path)
    old_snapshot = make_snapshot(hub, "stable-revision")

    def downloader(**_kwargs):
        model_cache = hub / "models--Systran--faster-whisper-medium"
        broken = model_cache / "snapshots" / "broken-revision"
        broken.mkdir(parents=True)
        (model_cache / "refs" / "main").write_text(
            "broken-revision\n", encoding="utf-8"
        )
        (broken / "config.json").write_text("{}", encoding="utf-8")
        return str(broken)

    result = whisper_cache.refresh_whisper_model_cache(force=True, downloader=downloader)

    assert result["status"] == "update_failed_cache_kept"
    assert result["active_revision"] == "stable-revision"
    assert whisper_cache.cached_whisper_model_path(MODEL) == old_snapshot


def test_recent_success_skips_network_check(monkeypatch, tmp_path):
    hub, _state_path = configure_cache(monkeypatch, tmp_path)
    snapshot = make_snapshot(hub, "current-revision")
    whisper_cache.write_whisper_cache_state(
        {
            "model": MODEL,
            "checked_at": whisper_cache.iso_now(),
            "status": "current",
            "cached": True,
            "revision": snapshot.name,
        }
    )

    def downloader(**_kwargs):
        raise AssertionError("network should not be called")

    result = whisper_cache.refresh_whisper_model_cache(downloader=downloader)

    assert result["status"] == "fresh"
    assert result["revision"] == "current-revision"


def test_error_state_redacts_huggingface_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_private_value")

    message = whisper_cache.safe_error_text(
        RuntimeError("download failed for hf_private_value\nretry later")
    )

    assert "hf_private_value" not in message
    assert "[redacted]" in message
    assert "\n" not in message
