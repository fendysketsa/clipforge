from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_WHISPER_MODEL = "Systran/faster-whisper-medium"
WHISPER_MODEL_FILES = (
    "config.json",
    "model.bin",
    "preprocessor_config.json",
    "tokenizer.json",
    "vocabulary.*",
)
REQUIRED_WHISPER_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json")
MIN_WHISPER_MODEL_BYTES = 1024
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_maintenance_lock = threading.Lock()
_maintenance_started = False


def env_enabled(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def huggingface_home() -> Path:
    return Path(
        os.environ.get("HF_HOME", "").strip()
        or Path.home() / ".cache" / "huggingface"
    )


def huggingface_hub_cache() -> Path:
    return Path(
        os.environ.get("HF_HUB_CACHE", "").strip()
        or huggingface_home() / "hub"
    )


def whisper_cache_state_path() -> Path:
    configured = os.environ.get("FENDY_CLIPPER_WHISPER_UPDATE_STATE_PATH", "").strip()
    return Path(configured) if configured else huggingface_home() / "clipforge_whisper_update.json"


def configured_whisper_model() -> str:
    model_name = os.environ.get(
        "FENDY_CLIPPER_WHISPER_MODEL",
        DEFAULT_WHISPER_MODEL,
    ).strip()
    if not MODEL_ID_PATTERN.fullmatch(model_name):
        return DEFAULT_WHISPER_MODEL
    return model_name


def cached_whisper_model_path(model_name: str) -> Path | None:
    """Resolve a complete Hub snapshot without making a network request."""
    configured_path = Path(model_name).expanduser()
    if configured_path.is_dir():
        return configured_path
    if not MODEL_ID_PATTERN.fullmatch(model_name):
        return None

    model_cache = huggingface_hub_cache() / f"models--{model_name.replace('/', '--')}"
    snapshots = model_cache / "snapshots"
    candidates: list[Path] = []
    state = read_whisper_cache_state()
    active_revision = (
        str(state.get("active_revision") or state.get("revision") or "").strip()
        if state.get("model") == model_name and state.get("cached") is True
        else ""
    )
    if active_revision:
        candidates.append(snapshots / active_revision)
    main_ref = model_cache / "refs" / "main"
    try:
        revision = main_ref.read_text(encoding="utf-8").strip()
    except OSError:
        revision = ""
    if revision:
        candidates.append(snapshots / revision)
    try:
        candidates.extend(
            sorted(
                (item for item in snapshots.iterdir() if item.is_dir()),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        )
    except OSError:
        pass

    for candidate in candidates:
        try:
            validate_whisper_snapshot(candidate)
        except (OSError, RuntimeError):
            continue
        else:
            return candidate
    return None


def read_whisper_cache_state() -> dict[str, Any]:
    try:
        payload = json.loads(whisper_cache_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_whisper_cache_state(payload: dict[str, Any]) -> None:
    path = whisper_cache_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_whisper_snapshot(snapshot: Path) -> None:
    missing = [
        filename
        for filename in REQUIRED_WHISPER_MODEL_FILES
        if not (snapshot / filename).is_file()
    ]
    if missing:
        raise RuntimeError("snapshot Whisper tidak lengkap: " + ", ".join(missing))
    if (snapshot / "model.bin").stat().st_size < MIN_WHISPER_MODEL_BYTES:
        raise RuntimeError("model.bin Whisper kosong atau terpotong")
    for filename in ("config.json", "tokenizer.json"):
        try:
            payload = json.loads((snapshot / filename).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise RuntimeError(f"{filename} Whisper tidak valid") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{filename} Whisper harus berupa objek JSON")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_error_text(exc: Exception) -> str:
    message = re.sub(r"[\r\n\x00-\x1f]+", " ", str(exc)).strip()
    for variable in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        secret = os.environ.get(variable, "").strip()
        if secret:
            message = message.replace(secret, "[redacted]")
    return f"{type(exc).__name__}: {message[:300]}"


def update_interval_seconds() -> float:
    try:
        hours = float(
            os.environ.get("FENDY_CLIPPER_WHISPER_UPDATE_INTERVAL_HOURS", "24")
        )
    except (TypeError, ValueError):
        hours = 24.0
    return max(1.0, min(168.0, hours)) * 3600.0


def update_retry_seconds() -> float:
    try:
        hours = float(
            os.environ.get("FENDY_CLIPPER_WHISPER_UPDATE_RETRY_HOURS", "1")
        )
    except (TypeError, ValueError):
        hours = 1.0
    return max(0.25, min(24.0, hours)) * 3600.0


def state_check_age_seconds(state: dict[str, Any]) -> float | None:
    value = str(state.get("checked_at") or "").strip()
    if not value:
        return None
    try:
        checked_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - checked_at).total_seconds())


def refresh_whisper_model_cache(
    *,
    force: bool = False,
    downloader: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Atomically refresh the trusted model snapshot while preserving old cache."""
    model_name = configured_whisper_model()
    previous_snapshot = cached_whisper_model_path(model_name)
    state = read_whisper_cache_state()
    age = state_check_age_seconds(state)
    previous_status = str(state.get("status") or "")
    next_check_seconds = (
        update_retry_seconds()
        if previous_status in {"checking", "update_failed", "update_failed_cache_kept"}
        else update_interval_seconds()
    )
    if not force and age is not None and age < next_check_seconds:
        return {
            **state,
            "status": "fresh",
            "cached": previous_snapshot is not None,
        }

    checked_at = iso_now()
    write_whisper_cache_state(
        {
            **state,
            "model": model_name,
            "checked_at": checked_at,
            "status": "checking",
            "cached": previous_snapshot is not None,
            "revision": previous_snapshot.name if previous_snapshot else None,
            "active_revision": previous_snapshot.name if previous_snapshot else None,
            "error": None,
        }
    )
    try:
        if downloader is None:
            from huggingface_hub import snapshot_download

            downloader = snapshot_download
        token = (
            os.environ.get("HF_TOKEN", "").strip()
            or os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
            or None
        )
        snapshot_value = downloader(
            repo_id=model_name,
            cache_dir=str(huggingface_hub_cache()),
            allow_patterns=list(WHISPER_MODEL_FILES),
            token=token,
        )
        snapshot = Path(snapshot_value)
        validate_whisper_snapshot(snapshot)
        updated = previous_snapshot is None or snapshot.resolve() != previous_snapshot.resolve()
        result = {
            "model": model_name,
            "checked_at": checked_at,
            "updated_at": iso_now() if updated else state.get("updated_at"),
            "status": "updated" if updated else "current",
            "cached": True,
            "revision": snapshot.name,
            "active_revision": snapshot.name,
            "error": None,
        }
        write_whisper_cache_state(result)
        return result
    except Exception as exc:
        # Hugging Face snapshots are immutable. A failed refresh therefore
        # cannot corrupt the last complete snapshot used by active/new jobs.
        result = {
            "model": model_name,
            "checked_at": checked_at,
            "updated_at": state.get("updated_at"),
            "status": "update_failed_cache_kept" if previous_snapshot else "update_failed",
            "cached": previous_snapshot is not None,
            "revision": previous_snapshot.name if previous_snapshot else None,
            "active_revision": previous_snapshot.name if previous_snapshot else None,
            "error": safe_error_text(exc),
        }
        write_whisper_cache_state(result)
        return result


def whisper_model_cache_maintenance_loop(
    can_refresh: Callable[[], bool] | None = None,
) -> None:
    while env_enabled("FENDY_CLIPPER_WHISPER_AUTO_UPDATE", True):
        if can_refresh is not None:
            try:
                refresh_allowed = can_refresh()
            except Exception:
                refresh_allowed = False
            if not refresh_allowed:
                time.sleep(60.0)
                continue
        result = refresh_whisper_model_cache()
        print(
            "Whisper model cache: "
            f"{result.get('status')} · {result.get('model')} · "
            f"revision {result.get('revision') or '-'}",
            flush=True,
        )
        # Wake hourly so interval changes apply without a backend restart. The
        # persisted checked_at gate prevents unnecessary Hub requests.
        time.sleep(min(3600.0, update_interval_seconds(), update_retry_seconds()))


def start_whisper_model_cache_maintenance(
    can_refresh: Callable[[], bool] | None = None,
) -> bool:
    global _maintenance_started
    if not env_enabled("FENDY_CLIPPER_WHISPER_AUTO_UPDATE", True):
        return False
    with _maintenance_lock:
        if _maintenance_started:
            return False
        _maintenance_started = True
    threading.Thread(
        target=whisper_model_cache_maintenance_loop,
        args=(can_refresh,),
        name="whisper-model-cache",
        daemon=True,
    ).start()
    return True
