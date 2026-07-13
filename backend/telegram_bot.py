from __future__ import annotations

import json
import mimetypes
import os
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = Path(os.environ.get("TELEGRAM_OUTPUTS_DIR", BASE_DIR / "outputs"))
STATE_PATH = Path(
    os.environ.get("TELEGRAM_STATE_PATH", BASE_DIR / "data" / "telegram_bot_state.json")
)
BACKEND_API_BASE = os.environ.get("BACKEND_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PUBLIC_OUTPUT_BASE_URL = os.environ.get("TELEGRAM_PUBLIC_BASE_URL", "").rstrip("/")
POLL_TIMEOUT_SECONDS = 3
MAX_UPLOAD_BYTES = min(
    49 * 1024 * 1024,
    max(1, int(float(os.environ.get("TELEGRAM_MAX_UPLOAD_MB", "49")) * 1024 * 1024)),
)
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running"}
ALLOWED_QUALITY = {"standard", "high", "max"}
ALLOWED_CROP = {"center", "person", "streamer"}
ALLOWED_CAPTION_POSITIONS = {"upper", "center", "bottom"}
ALLOWED_TOP = {None, 3, 5, 8, 10, 12}
ALLOWED_DURATION_PRESETS = {(15, 60), (35, 180), (60, 180)}

DEFAULT_SETTINGS: dict[str, Any] = {
    "top": None,
    "min_duration": 35,
    "max_duration": 180,
    "video_quality": "high",
    "crop_mode": "person",
    "burn_subtitles": True,
    "ai_enabled": True,
    "caption_position": "upper",
    "caption_font_size": 18,
}


class ServiceError(RuntimeError):
    pass


def format_duration(seconds: float | int | None) -> str:
    value = max(0, int(round(float(seconds or 0))))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}j {minutes}m {secs}d"
    if minutes:
        return f"{minutes}m {secs}d"
    return f"{secs}d"


def format_size(size_bytes: int | float | None) -> str:
    value = max(0.0, float(size_bytes or 0))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def is_supported_video_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().removeprefix("www.")
    return host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def normalize_settings(value: object) -> dict[str, Any]:
    settings = DEFAULT_SETTINGS.copy()
    if not isinstance(value, dict):
        return settings

    top = value.get("top")
    settings["top"] = top if top in ALLOWED_TOP else None

    duration = (value.get("min_duration"), value.get("max_duration"))
    if duration in ALLOWED_DURATION_PRESETS:
        settings["min_duration"], settings["max_duration"] = duration

    quality = value.get("video_quality")
    if quality in ALLOWED_QUALITY:
        settings["video_quality"] = quality

    crop = value.get("crop_mode")
    if crop in ALLOWED_CROP:
        settings["crop_mode"] = crop

    if isinstance(value.get("burn_subtitles"), bool):
        settings["burn_subtitles"] = value["burn_subtitles"]
    if isinstance(value.get("ai_enabled"), bool):
        settings["ai_enabled"] = value["ai_enabled"]

    position = value.get("caption_position")
    if position in ALLOWED_CAPTION_POSITIONS:
        settings["caption_position"] = position

    font_size = value.get("caption_font_size")
    if font_size in {14, 18, 24}:
        settings["caption_font_size"] = font_size
    return settings


def default_state() -> dict[str, Any]:
    return {
        "update_offset": 0,
        "waiting_for_url": False,
        "pending_url": "",
        "active_job_id": None,
        "settings": DEFAULT_SETTINGS.copy(),
        "jobs": {},
    }


def normalize_state(value: object) -> dict[str, Any]:
    state = default_state()
    if not isinstance(value, dict):
        return state
    if isinstance(value.get("update_offset"), int):
        state["update_offset"] = max(0, value["update_offset"])
    state["waiting_for_url"] = bool(value.get("waiting_for_url", False))
    if isinstance(value.get("pending_url"), str):
        state["pending_url"] = value["pending_url"]
    if isinstance(value.get("active_job_id"), str):
        state["active_job_id"] = value["active_job_id"]
    state["settings"] = normalize_settings(value.get("settings"))
    if isinstance(value.get("jobs"), dict):
        state["jobs"] = value["jobs"]
    return state


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        return normalize_state(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return default_state()


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state, ensure_ascii=False, indent=2)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(data, encoding="utf-8")
    temp_path.replace(path)


def build_job_payload(url: str, settings: dict[str, Any]) -> dict[str, Any]:
    clean = normalize_settings(settings)
    return {
        "url": url.strip(),
        "top": clean["top"],
        "min_duration": clean["min_duration"],
        "max_duration": clean["max_duration"],
        "video_quality": clean["video_quality"],
        "burn_subtitles": clean["burn_subtitles"],
        "crop_mode": clean["crop_mode"],
        "ai_enabled": clean["ai_enabled"],
        "caption_position": clean["caption_position"],
        "caption_font_size": clean["caption_font_size"],
    }


def output_path_from_url(url: str, outputs_dir: Path = OUTPUTS_DIR) -> Path | None:
    if not url.startswith("/outputs/"):
        return None
    relative = unquote(url.removeprefix("/outputs/").split("?", 1)[0])
    candidate = (outputs_dir / relative).resolve()
    root = outputs_dir.resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def split_text(text: str, limit: int = 3900) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    chunks: list[str] = []
    while len(clean) > limit:
        split_at = clean.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = clean.rfind(" ", 0, limit + 1)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(clean[:split_at].rstrip())
        clean = clean[split_at:].lstrip()
    if clean:
        chunks.append(clean)
    return chunks


def elapsed_for_job(job: dict[str, Any]) -> float:
    stored = job.get("duration_seconds")
    if isinstance(stored, (int, float)):
        return max(0.0, float(stored))
    started_at = job.get("started_at")
    if not isinstance(started_at, str) or not started_at:
        return 0.0
    try:
        started = datetime.fromisoformat(started_at)
        now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
        return max(0.0, (now - started).total_seconds())
    except ValueError:
        return 0.0


def progress_stage(job: dict[str, Any]) -> str:
    logs = "\n".join(str(line) for line in job.get("logs", [])[-30:]).lower()
    if "exporting vertical clips" in logs or "person crop" in logs or "streamer stack" in logs:
        return "Mengekspor video vertikal"
    if "scoring candidate" in logs or "agent scoring" in logs:
        return "Menyeleksi momen terbaik"
    if "transcribed" in logs:
        return "Menyusun kandidat clip"
    if "loading model" in logs or "transcrib" in logs:
        return "Mentranskripsi percakapan"
    if "fetching video" in logs:
        return "Mengunduh video sumber"
    if "fetching metadata" in logs:
        return "Membaca informasi video"
    return "Menyiapkan proses clipping"


def clip_title(clip: dict[str, Any], index: int) -> str:
    title = clip.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    name = str(clip.get("name") or f"clip_{index:02d}")
    stem = Path(name).stem
    stem = stem.split("_", 2)[-1] if stem.startswith("clip_") else stem
    return stem.replace("-", " ").replace("_", " ").strip().title() or f"Clip {index}"


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.reason
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            detail = error_payload.get("detail") or error_payload.get("description") or detail
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        raise ServiceError(str(detail)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ServiceError(str(exc)) from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ServiceError("Respons service bukan JSON yang valid") from exc


def _multipart_body(
    fields: dict[str, Any], file_field: str, file_path: Path
) -> tuple[bytes, str]:
    boundary = f"----ClipForge{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    safe_name = file_path.name.replace('"', "")
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{safe_name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


class BackendClient:
    def __init__(self, base_url: str = BACKEND_API_BASE):
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return _json_request(f"{self.base_url}/api/health", timeout=5)

    def list_jobs(self) -> list[dict[str, Any]]:
        result = _json_request(f"{self.base_url}/api/jobs", timeout=15)
        return result if isinstance(result, list) else []

    def get_job(self, job_id: str) -> dict[str, Any]:
        result = _json_request(f"{self.base_url}/api/jobs/{job_id}", timeout=15)
        if not isinstance(result, dict):
            raise ServiceError("Data job tidak valid")
        return result

    def create_job(self, url: str, settings: dict[str, Any]) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs",
            method="POST",
            payload=build_job_payload(url, settings),
            timeout=90,
        )
        if not isinstance(result, dict):
            raise ServiceError("Backend tidak mengembalikan job")
        return result

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        result = _json_request(
            f"{self.base_url}/api/jobs/{job_id}/cancel",
            method="POST",
            payload={},
            timeout=20,
        )
        return result if isinstance(result, dict) else {}


class TelegramApi:
    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
        file_field: str | None = None,
        file_path: Path | None = None,
    ) -> Any:
        url = f"{self.base_url}/{method}"
        if file_field and file_path:
            body, boundary = _multipart_body(payload or {}, file_field, file_path)
            request = Request(
                url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                try:
                    detail = json.loads(exc.read().decode("utf-8")).get("description", exc.reason)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    detail = exc.reason
                raise ServiceError(str(detail)) from exc
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                raise ServiceError(str(exc)) from exc
        else:
            result = _json_request(url, method="POST", payload=payload or {}, timeout=timeout)

        if not isinstance(result, dict) or not result.get("ok"):
            detail = result.get("description", "Telegram API gagal") if isinstance(result, dict) else "Telegram API gagal"
            raise ServiceError(str(detail))
        return result.get("result")


def button(text: str, callback_data: str) -> dict[str, str]:
    return {"text": text, "callback_data": callback_data}


def keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def main_menu_keyboard() -> dict[str, Any]:
    return keyboard(
        [
            [button("🎬 Mulai Clipping", "menu:new")],
            [button("📊 Status", "menu:status"), button("📚 Riwayat", "menu:history")],
            [button("⚙️ Pengaturan", "menu:settings"), button("❓ Bantuan", "menu:help")],
        ]
    )


def settings_summary(settings: dict[str, Any]) -> str:
    clean = normalize_settings(settings)
    top = "Otomatis" if clean["top"] is None else str(clean["top"])
    quality = {"standard": "Standar", "high": "Jernih", "max": "Maksimal"}[clean["video_quality"]]
    crop = {"center": "Center", "person": "Follow Person", "streamer": "Streamer"}[clean["crop_mode"]]
    position = {"upper": "Atas", "center": "Tengah", "bottom": "Bawah"}[clean["caption_position"]]
    return (
        f"Target clip: {top}\n"
        f"Durasi: {clean['min_duration']}–{clean['max_duration']} detik\n"
        f"Kualitas: {quality}\n"
        f"Mode crop: {crop}\n"
        f"Subtitle: {'Aktif' if clean['burn_subtitles'] else 'Nonaktif'}\n"
        f"AI: {'Aktif' if clean['ai_enabled'] else 'Nonaktif'}\n"
        f"Caption: {position}, {clean['caption_font_size']}px"
    )


def settings_keyboard(settings: dict[str, Any], *, has_pending_url: bool = False) -> dict[str, Any]:
    clean = normalize_settings(settings)
    top = "auto" if clean["top"] is None else clean["top"]
    rows = [
            [button(f"Jumlah Clip · {top}", "settings:top")],
            [button(f"Durasi · {clean['min_duration']}–{clean['max_duration']}d", "settings:duration")],
            [button(f"Kualitas · {clean['video_quality']}", "settings:quality")],
            [button(f"Crop · {clean['crop_mode']}", "settings:crop")],
            [
                button(f"Subtitle · {'ON' if clean['burn_subtitles'] else 'OFF'}", "set:subtitles:toggle"),
                button(f"AI · {'ON' if clean['ai_enabled'] else 'OFF'}", "set:ai:toggle"),
            ],
            [button("Tampilan Caption", "settings:caption")],
        ]
    if has_pending_url:
        rows.append([button("✅ Kembali ke Konfirmasi", "pending:review")])
    rows.append([button("⬅️ Menu Utama", "menu:home")])
    return keyboard(rows)


def confirmation_keyboard() -> dict[str, Any]:
    return keyboard(
        [
            [button("✅ Proses Sekarang", "job:confirm")],
            [button("⚙️ Ubah Pengaturan", "menu:settings"), button("❌ Batal", "pending:cancel")],
        ]
    )


class ClipForgeTelegramBot:
    def __init__(self, token: str, owner_id: int):
        self.telegram = TelegramApi(token)
        self.backend = BackendClient()
        self.owner_id = owner_id
        self.state = load_state()
        self.running = True
        self.last_backend_warning = 0.0

    def persist(self) -> None:
        save_state(self.state)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = self.telegram.call("sendMessage", payload)
        return result if isinstance(result, dict) else {}

    def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            self.telegram.call("editMessageText", payload)
        except ServiceError as exc:
            if "message is not modified" not in str(exc).lower():
                raise

    def answer_callback(self, callback_id: str, text: str = "", alert: bool = False) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id, "show_alert": alert}
        if text:
            payload["text"] = text[:200]
        try:
            self.telegram.call("answerCallbackQuery", payload, timeout=10)
        except ServiceError:
            pass

    def send_long_message(self, chat_id: int, text: str) -> None:
        for chunk in split_text(text):
            self.send_message(chat_id, chunk)

    def show_home(self, chat_id: int, first_name: str = "") -> None:
        greeting = f"Halo {first_name}, " if first_name else "Halo, "
        self.send_message(
            chat_id,
            greeting
            + "Fendy Clipper siap digunakan.\n\n"
            "Kirim link YouTube langsung ke chat ini, atau gunakan tombol di bawah.",
            main_menu_keyboard(),
        )

    def show_settings(self, chat_id: int, message_id: int | None = None) -> None:
        text = "Pengaturan clipping saat ini\n\n" + settings_summary(self.state["settings"])
        markup = settings_keyboard(
            self.state["settings"],
            has_pending_url=is_supported_video_url(str(self.state.get("pending_url", ""))),
        )
        if message_id:
            self.edit_message(chat_id, message_id, text, markup)
        else:
            self.send_message(chat_id, text, markup)

    def show_pending(self, chat_id: int) -> None:
        url = self.state.get("pending_url", "")
        self.send_message(
            chat_id,
            "Link siap diproses\n\n"
            f"{url}\n\n"
            + settings_summary(self.state["settings"])
            + "\n\nTekan Proses Sekarang untuk memulai.",
            confirmation_keyboard(),
        )

    def show_help(self, chat_id: int) -> None:
        self.send_message(
            chat_id,
            "Cara menggunakan Fendy Clipper\n\n"
            "1. Kirim link YouTube ke bot.\n"
            "2. Periksa pengaturan yang ditampilkan.\n"
            "3. Tekan Proses Sekarang.\n"
            "4. Bot akan mengirim seluruh hasil saat selesai.\n\n"
            "Perintah: /clip, /status, /settings, /history, /cancel, /menu",
            main_menu_keyboard(),
        )

    def job_status_text(self, job: dict[str, Any]) -> str:
        status = str(job.get("status", "unknown"))
        status_label = {
            "queued": "Menunggu worker",
            "running": "Sedang diproses",
            "completed": "Selesai",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
        }.get(status, status)
        title = str(job.get("source_title") or job.get("request", {}).get("url") or "Video")[:500]
        lines = [
            f"Status: {status_label}",
            f"Sumber: {title}",
            f"Job: {str(job.get('id', ''))[:10]}",
            f"Durasi proses: {format_duration(elapsed_for_job(job))}",
        ]
        if status in ACTIVE_STATUSES:
            lines.insert(2, f"Tahap: {progress_stage(job)}")
        if status == "completed":
            lines.append(f"Hasil: {len(job.get('clips', []))} clip")
        if status in {"failed", "cancelled"} and job.get("error"):
            lines.append(f"Keterangan: {str(job['error'])[:2000]}")
        return "\n".join(lines)

    def job_keyboard(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("id", ""))
        status = job.get("status")
        rows: list[list[dict[str, str]]] = []
        if status in ACTIVE_STATUSES:
            rows.append([button("🔄 Perbarui", f"refresh:{job_id}"), button("⏹ Batalkan", f"cancelask:{job_id}")])
        elif status == "completed" and job.get("clips"):
            rows.append([button("📤 Kirim Semua Hasil", f"deliver:{job_id}")])
        rows.append([button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")])
        return keyboard(rows)

    def show_job(self, chat_id: int, job: dict[str, Any], message_id: int | None = None) -> None:
        text = self.job_status_text(job)
        markup = self.job_keyboard(job)
        if message_id:
            self.edit_message(chat_id, message_id, text, markup)
        else:
            self.send_message(chat_id, text, markup)

    def current_active_job(self) -> dict[str, Any] | None:
        active_job_id = self.state.get("active_job_id")
        if isinstance(active_job_id, str) and active_job_id:
            try:
                job = self.backend.get_job(active_job_id)
                if job.get("status") in ACTIVE_STATUSES:
                    return job
                self.state["active_job_id"] = None
                self.persist()
            except ServiceError:
                pass
        for job in self.backend.list_jobs():
            if job.get("status") in ACTIVE_STATUSES:
                return job
        return None

    def show_status(self, chat_id: int) -> None:
        try:
            active = self.current_active_job()
        except ServiceError as exc:
            self.send_message(chat_id, f"Backend belum dapat dihubungi: {exc}", main_menu_keyboard())
            return
        if active:
            self.show_job(chat_id, active)
            return
        self.send_message(chat_id, "Tidak ada proses clipping yang sedang berjalan.", main_menu_keyboard())

    def show_history(self, chat_id: int) -> None:
        try:
            jobs = self.backend.list_jobs()[:8]
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memuat riwayat: {exc}", main_menu_keyboard())
            return
        if not jobs:
            self.send_message(chat_id, "Riwayat clipping masih kosong.", main_menu_keyboard())
            return
        labels = {
            "queued": "Menunggu",
            "running": "Diproses",
            "completed": "Selesai",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
        }
        lines = ["Riwayat clipping terbaru"]
        rows: list[list[dict[str, str]]] = []
        for index, job in enumerate(jobs, start=1):
            title = job.get("source_title") or job.get("request", {}).get("url") or "Video"
            title = str(title).replace("\n", " ")[:60]
            status = labels.get(str(job.get("status")), str(job.get("status")))
            lines.append(f"\n{index}. {status} · {len(job.get('clips', []))} clip\n{title}")
            rows.append([button(f"Lihat #{index} · {status}", f"view:{job.get('id')}")])
        rows.append([button("🏠 Menu Utama", "menu:home")])
        self.send_message(chat_id, "\n".join(lines), keyboard(rows))

    def receive_url(self, chat_id: int, value: str) -> None:
        url = value.strip()
        if not is_supported_video_url(url):
            self.send_message(
                chat_id,
                "Link belum dikenali. Kirim link YouTube lengkap, misalnya https://youtu.be/...",
                main_menu_keyboard(),
            )
            return
        self.state["pending_url"] = url
        self.state["waiting_for_url"] = False
        self.persist()
        self.show_pending(chat_id)

    def start_job(self, chat_id: int) -> None:
        url = str(self.state.get("pending_url", ""))
        if not is_supported_video_url(url):
            self.send_message(chat_id, "Link belum tersedia. Kirim link YouTube terlebih dahulu.", main_menu_keyboard())
            return
        try:
            active = self.current_active_job()
            if active:
                self.send_message(
                    chat_id,
                    "Masih ada proses clipping aktif. Tunggu sampai selesai atau batalkan terlebih dahulu.",
                    self.job_keyboard(active),
                )
                return
            job = self.backend.create_job(url, self.state["settings"])
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memulai clipping: {exc}", main_menu_keyboard())
            return

        job_id = str(job["id"])
        self.state["active_job_id"] = job_id
        self.state["pending_url"] = ""
        self.state["waiting_for_url"] = False
        self.state["jobs"][job_id] = {
            "chat_id": chat_id,
            "terminal_notified": False,
            "delivery": {"summary": False, "clips": {}},
        }
        self.persist()
        status_message = self.send_message(
            chat_id,
            "Proses clipping berhasil dimulai. Bot akan mengirim semua hasil secara otomatis saat selesai.",
            self.job_keyboard(job),
        )
        self.state["jobs"][job_id]["status_message_id"] = status_message.get("message_id")
        self.persist()

    def clip_metadata_text(self, clip: dict[str, Any], index: int, total: int) -> str:
        parts = [f"Detail Clip {index}/{total}", f"Judul:\n{clip_title(clip, index)}"]
        social_caption = clip.get("social_caption")
        if isinstance(social_caption, str) and social_caption.strip():
            parts.append("Caption sosial:\n" + social_caption.strip())
        thumbnail_prompt = clip.get("thumbnail_prompt")
        if isinstance(thumbnail_prompt, str) and thumbnail_prompt.strip():
            parts.append("Prompt thumbnail:\n" + thumbnail_prompt.strip())
        return "\n\n".join(parts)

    def send_media_file(
        self,
        chat_id: int,
        method: str,
        field: str,
        path: Path,
        caption: str,
    ) -> None:
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            public_url = ""
            try:
                relative = path.resolve().relative_to(OUTPUTS_DIR.resolve()).as_posix()
                if PUBLIC_OUTPUT_BASE_URL:
                    public_url = f"{PUBLIC_OUTPUT_BASE_URL}/outputs/{relative}"
            except ValueError:
                pass
            message = (
                f"{caption}\n\nFile {format_size(path.stat().st_size)} melebihi batas upload Telegram "
                f"{format_size(MAX_UPLOAD_BYTES)}."
            )
            if public_url:
                message += f"\nUnduh: {public_url}"
            else:
                message += "\nFile tetap tersedia di dashboard Fendy Clipper."
            self.send_message(chat_id, message)
            return
        self.telegram.call(
            "sendChatAction",
            {"chat_id": chat_id, "action": "upload_video" if method == "sendVideo" else "upload_photo"},
            timeout=10,
        )
        fields: dict[str, Any] = {"chat_id": chat_id, "caption": caption[:1024]}
        if method == "sendVideo":
            fields["supports_streaming"] = True
        try:
            self.telegram.call(
                method,
                fields,
                timeout=240,
                file_field=field,
                file_path=path,
            )
        except ServiceError:
            if method != "sendVideo":
                raise
            self.telegram.call(
                "sendDocument",
                {"chat_id": chat_id, "caption": caption[:1024]},
                timeout=240,
                file_field="document",
                file_path=path,
            )

    def delivery_record(self, job_id: str, chat_id: int) -> dict[str, Any]:
        record = self.state["jobs"].setdefault(
            job_id,
            {
                "chat_id": chat_id,
                "terminal_notified": False,
                "delivery": {"summary": False, "clips": {}},
            },
        )
        record["chat_id"] = chat_id
        delivery = record.setdefault("delivery", {"summary": False, "clips": {}})
        delivery.setdefault("summary", False)
        delivery.setdefault("clips", {})
        return record

    def deliver_job(self, chat_id: int, job: dict[str, Any], *, force: bool = False) -> None:
        job_id = str(job["id"])
        record = self.delivery_record(job_id, chat_id)
        if force:
            record["terminal_notified"] = False
            record["delivery"] = {"summary": False, "clips": {}}
            self.persist()
        delivery = record["delivery"]
        clips = job.get("clips", [])
        if not delivery["summary"]:
            source = job.get("source_title") or job.get("request", {}).get("url") or "Video"
            uploader = job.get("source_uploader")
            summary = (
                "Clipping selesai\n\n"
                f"Sumber: {source}\n"
                + (f"Channel: {uploader}\n" if uploader else "")
                + f"Jumlah hasil: {len(clips)} clip\n"
                + f"Durasi proses: {format_duration(job.get('duration_seconds'))}\n\n"
                + "Bot mulai mengirim video dan materi pendukung satu per satu."
            )
            self.send_message(chat_id, summary)
            delivery["summary"] = True
            self.persist()

        for index, clip in enumerate(clips, start=1):
            clip_url = str(clip.get("url", ""))
            artifact = delivery["clips"].setdefault(
                clip_url, {"video": False, "thumbnail": False, "metadata": False}
            )
            path = output_path_from_url(clip_url)
            title = clip_title(clip, index)
            if not artifact["video"]:
                if path is None or not path.is_file():
                    self.send_message(chat_id, f"Clip {index}/{len(clips)} tidak ditemukan di penyimpanan: {title}")
                else:
                    self.send_media_file(
                        chat_id,
                        "sendVideo",
                        "video",
                        path,
                        f"Clip {index}/{len(clips)}\n{title}\n{format_size(path.stat().st_size)}",
                    )
                artifact["video"] = True
                self.persist()

            thumbnail_url = clip.get("thumbnail_url")
            if not artifact["thumbnail"]:
                thumb_path = output_path_from_url(str(thumbnail_url)) if thumbnail_url else None
                if thumb_path is not None and thumb_path.is_file():
                    self.send_media_file(
                        chat_id,
                        "sendPhoto",
                        "photo",
                        thumb_path,
                        f"Thumbnail Clip {index}/{len(clips)} · {title}",
                    )
                artifact["thumbnail"] = True
                self.persist()

            if not artifact["metadata"]:
                self.send_long_message(chat_id, self.clip_metadata_text(clip, index, len(clips)))
                artifact["metadata"] = True
                self.persist()

        record["terminal_notified"] = True
        self.persist()
        self.send_message(
            chat_id,
            f"Semua hasil job {job_id[:10]} sudah dikirim.",
            keyboard(
                [
                    [button("🎬 Clipping Baru", "menu:new")],
                    [button("📚 Riwayat", "menu:history"), button("🏠 Menu", "menu:home")],
                ]
            ),
        )

    def notify_terminal_job(self, job_id: str, record: dict[str, Any], job: dict[str, Any]) -> None:
        if record.get("terminal_notified"):
            return
        chat_id = int(record.get("chat_id") or self.owner_id)
        status = job.get("status")
        status_message_id = record.get("status_message_id")
        if isinstance(status_message_id, int):
            try:
                self.show_job(chat_id, job, status_message_id)
            except ServiceError:
                pass
        if status == "completed":
            self.deliver_job(chat_id, job)
        else:
            self.send_message(chat_id, self.job_status_text(job), self.job_keyboard(job))
            record["terminal_notified"] = True
            self.persist()

    def monitor_jobs(self) -> None:
        for job_id, record in list(self.state.get("jobs", {}).items()):
            if not isinstance(record, dict) or record.get("terminal_notified"):
                continue
            try:
                job = self.backend.get_job(job_id)
            except ServiceError:
                continue
            if job.get("status") in ACTIVE_STATUSES:
                updated_at = float(record.get("last_status_update", 0) or 0)
                status_message_id = record.get("status_message_id")
                if isinstance(status_message_id, int) and time.time() - updated_at >= 30:
                    try:
                        self.show_job(int(record.get("chat_id") or self.owner_id), job, status_message_id)
                        record["last_status_update"] = time.time()
                        self.persist()
                    except ServiceError:
                        pass
                continue
            if job.get("status") in TERMINAL_STATUSES:
                if self.state.get("active_job_id") == job_id:
                    self.state["active_job_id"] = None
                    self.persist()
                try:
                    self.notify_terminal_job(job_id, record, job)
                except ServiceError as exc:
                    now = time.monotonic()
                    if now - self.last_backend_warning > 60:
                        print(f"Pengiriman hasil Telegram tertunda: {exc}", flush=True)
                        self.last_backend_warning = now

    def handle_message(self, message: dict[str, Any]) -> None:
        sender_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        if sender_id != self.owner_id or chat_type != "private" or not isinstance(chat_id, int):
            if isinstance(chat_id, int):
                try:
                    self.send_message(chat_id, "Bot ini bersifat privat dan hanya dapat digunakan oleh owner.")
                except ServiceError:
                    pass
            return

        text = str(message.get("text") or "").strip()
        first_name = str(message.get("from", {}).get("first_name") or "")
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text.startswith("/") else ""
        if command in {"/start", "/menu"}:
            self.show_home(chat_id, first_name)
        elif command == "/clip":
            self.state["waiting_for_url"] = True
            self.persist()
            self.send_message(chat_id, "Kirim link YouTube yang ingin diproses.", keyboard([[button("❌ Batal", "pending:cancel")]]))
        elif command == "/settings":
            self.show_settings(chat_id)
        elif command == "/status":
            self.show_status(chat_id)
        elif command == "/history":
            self.show_history(chat_id)
        elif command == "/help":
            self.show_help(chat_id)
        elif command == "/cancel":
            self.request_cancel(chat_id)
        elif is_supported_video_url(text):
            self.receive_url(chat_id, text)
        elif self.state.get("waiting_for_url"):
            self.receive_url(chat_id, text)
        elif text:
            self.send_message(chat_id, "Kirim link YouTube atau pilih salah satu menu di bawah.", main_menu_keyboard())

    def request_cancel(self, chat_id: int, job_id: str | None = None) -> None:
        try:
            job = self.backend.get_job(job_id) if job_id else self.current_active_job()
        except ServiceError as exc:
            self.send_message(chat_id, f"Gagal memeriksa job: {exc}", main_menu_keyboard())
            return
        if not job or job.get("status") not in ACTIVE_STATUSES:
            self.send_message(chat_id, "Tidak ada proses aktif yang dapat dibatalkan.", main_menu_keyboard())
            return
        selected_id = str(job["id"])
        self.send_message(
            chat_id,
            "Batalkan proses clipping ini? Output sementara akan dibersihkan oleh backend.",
            keyboard(
                [
                    [button("Ya, Batalkan", f"cancel:{selected_id}")],
                    [button("Kembali", f"refresh:{selected_id}")],
                ]
            ),
        )

    def apply_setting_callback(self, data: str) -> bool:
        parts = data.split(":")
        if len(parts) < 3 or parts[0] != "set":
            return False
        name, value = parts[1], parts[2]
        settings = self.state["settings"]
        if name == "top":
            if value == "auto":
                settings["top"] = None
            elif value.isdigit() and int(value) in ALLOWED_TOP:
                settings["top"] = int(value)
            else:
                return False
        elif name == "duration" and len(parts) == 4:
            if not value.isdigit() or not parts[3].isdigit():
                return False
            duration = (int(value), int(parts[3]))
            if duration not in ALLOWED_DURATION_PRESETS:
                return False
            settings["min_duration"], settings["max_duration"] = duration
        elif name == "quality" and value in ALLOWED_QUALITY:
            settings["video_quality"] = value
        elif name == "crop" and value in ALLOWED_CROP:
            settings["crop_mode"] = value
        elif name == "subtitles" and value == "toggle":
            settings["burn_subtitles"] = not settings["burn_subtitles"]
        elif name == "ai" and value == "toggle":
            settings["ai_enabled"] = not settings["ai_enabled"]
        elif name == "position" and value in ALLOWED_CAPTION_POSITIONS:
            settings["caption_position"] = value
        elif name == "fontsize" and value.isdigit() and int(value) in {14, 18, 24}:
            settings["caption_font_size"] = int(value)
        else:
            return False
        self.state["settings"] = normalize_settings(settings)
        self.persist()
        return True

    def handle_callback(self, callback: dict[str, Any]) -> None:
        sender_id = callback.get("from", {}).get("id")
        callback_id = str(callback.get("id") or "")
        if sender_id != self.owner_id:
            self.answer_callback(callback_id, "Akses ditolak.", alert=True)
            return
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        message_id = message.get("message_id")
        if chat_type != "private" or not isinstance(chat_id, int):
            self.answer_callback(callback_id)
            return
        data = str(callback.get("data") or "")
        self.answer_callback(callback_id)

        def show_panel(text: str, reply_markup: dict[str, Any]) -> None:
            if isinstance(message_id, int):
                self.edit_message(chat_id, message_id, text, reply_markup)
            else:
                self.send_message(chat_id, text, reply_markup)

        if data == "menu:home":
            self.show_home(chat_id, str(callback.get("from", {}).get("first_name") or ""))
        elif data == "menu:new":
            self.state["waiting_for_url"] = True
            self.persist()
            self.send_message(chat_id, "Kirim link YouTube yang ingin diproses.", keyboard([[button("❌ Batal", "pending:cancel")]]))
        elif data == "menu:settings":
            self.show_settings(chat_id, message_id if isinstance(message_id, int) else None)
        elif data == "menu:status":
            self.show_status(chat_id)
        elif data == "menu:history":
            self.show_history(chat_id)
        elif data == "menu:help":
            self.show_help(chat_id)
        elif data == "pending:cancel":
            self.state["waiting_for_url"] = False
            self.state["pending_url"] = ""
            self.persist()
            self.send_message(chat_id, "Input link dibatalkan.", main_menu_keyboard())
        elif data == "pending:review":
            if is_supported_video_url(str(self.state.get("pending_url", ""))):
                self.show_pending(chat_id)
            else:
                self.send_message(chat_id, "Link belum tersedia. Kirim link YouTube terlebih dahulu.", main_menu_keyboard())
        elif data == "job:confirm":
            self.start_job(chat_id)
        elif data == "settings:top":
            show_panel(
                "Pilih target jumlah clip",
                keyboard(
                    [
                        [button("Otomatis", "set:top:auto"), button("3", "set:top:3"), button("5", "set:top:5")],
                        [button("8", "set:top:8"), button("10", "set:top:10"), button("12", "set:top:12")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:duration":
            show_panel(
                "Pilih rentang durasi setiap clip",
                keyboard(
                    [
                        [button("15–60 detik", "set:duration:15:60")],
                        [button("35–180 detik", "set:duration:35:180")],
                        [button("60–180 detik", "set:duration:60:180")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:quality":
            show_panel(
                "Pilih kualitas output",
                keyboard(
                    [
                        [button("Standar", "set:quality:standard")],
                        [button("Jernih", "set:quality:high")],
                        [button("Maksimal", "set:quality:max")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:crop":
            show_panel(
                "Pilih mode crop",
                keyboard(
                    [
                        [button("Center", "set:crop:center")],
                        [button("Follow Person", "set:crop:person")],
                        [button("Streamer", "set:crop:streamer")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif data == "settings:caption":
            show_panel(
                "Atur tampilan caption",
                keyboard(
                    [
                        [button("Atas", "set:position:upper"), button("Tengah", "set:position:center"), button("Bawah", "set:position:bottom")],
                        [button("14px", "set:fontsize:14"), button("18px", "set:fontsize:18"), button("24px", "set:fontsize:24")],
                        [button("⬅️ Kembali", "menu:settings")],
                    ]
                ),
            )
        elif self.apply_setting_callback(data):
            self.show_settings(chat_id, message_id if isinstance(message_id, int) else None)
        elif data.startswith("view:") or data.startswith("refresh:"):
            job_id = data.split(":", 1)[1]
            try:
                job = self.backend.get_job(job_id)
                if isinstance(message_id, int) and data.startswith("refresh:"):
                    self.show_job(chat_id, job, message_id)
                else:
                    self.show_job(chat_id, job)
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal membuka job: {exc}", main_menu_keyboard())
        elif data.startswith("cancelask:"):
            self.request_cancel(chat_id, data.split(":", 1)[1])
        elif data.startswith("cancel:"):
            job_id = data.split(":", 1)[1]
            try:
                self.backend.cancel_job(job_id)
                self.send_message(chat_id, "Permintaan pembatalan sudah dikirim.", main_menu_keyboard())
            except ServiceError as exc:
                self.send_message(chat_id, f"Gagal membatalkan job: {exc}", main_menu_keyboard())
        elif data.startswith("deliver:"):
            job_id = data.split(":", 1)[1]
            try:
                job = self.backend.get_job(job_id)
                if job.get("status") != "completed":
                    self.send_message(chat_id, "Hasil belum siap dikirim.", self.job_keyboard(job))
                else:
                    self.deliver_job(chat_id, job, force=True)
            except ServiceError as exc:
                self.send_message(chat_id, f"Pengiriman hasil gagal: {exc}", main_menu_keyboard())

    def handle_update(self, update: dict[str, Any]) -> None:
        if isinstance(update.get("callback_query"), dict):
            self.handle_callback(update["callback_query"])
        elif isinstance(update.get("message"), dict):
            self.handle_message(update["message"])

    def wait_for_backend(self) -> None:
        while self.running:
            try:
                self.backend.health()
                return
            except ServiceError as exc:
                print(f"Menunggu backend ClipForge: {exc}", flush=True)
                time.sleep(3)

    def setup(self) -> None:
        self.telegram.call("deleteWebhook", {"drop_pending_updates": False}, timeout=15)
        self.telegram.call(
            "setMyCommands",
            {
                "commands": [
                    {"command": "clip", "description": "Mulai clipping dari link YouTube"},
                    {"command": "status", "description": "Lihat proses yang sedang berjalan"},
                    {"command": "settings", "description": "Atur hasil clipping"},
                    {"command": "history", "description": "Lihat riwayat dan kirim ulang hasil"},
                    {"command": "cancel", "description": "Batalkan proses aktif"},
                    {"command": "menu", "description": "Buka menu utama"},
                ]
            },
            timeout=15,
        )
        identity = self.telegram.call("getMe", timeout=15)
        username = identity.get("username", "unknown") if isinstance(identity, dict) else "unknown"
        print(f"Telegram bot @{username} aktif untuk owner {self.owner_id}.", flush=True)

    def run(self) -> None:
        self.wait_for_backend()
        self.setup()
        while self.running:
            try:
                updates = self.telegram.call(
                    "getUpdates",
                    {
                        "offset": self.state["update_offset"],
                        "timeout": POLL_TIMEOUT_SECONDS,
                        "allowed_updates": ["message", "callback_query"],
                    },
                    timeout=POLL_TIMEOUT_SECONDS + 10,
                )
                for update in updates if isinstance(updates, list) else []:
                    if not isinstance(update, dict):
                        continue
                    try:
                        self.handle_update(update)
                    except (ServiceError, ValueError, TypeError, KeyError) as exc:
                        print(f"Gagal menangani update Telegram: {exc}", flush=True)
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self.state["update_offset"] = update_id + 1
                        self.persist()
                self.monitor_jobs()
            except ServiceError as exc:
                print(f"Koneksi Telegram tertunda: {exc}", flush=True)
                time.sleep(3)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    owner_raw = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN belum diatur")
    try:
        owner_id = int(owner_raw)
    except ValueError as exc:
        raise SystemExit("TELEGRAM_OWNER_ID harus berupa angka") from exc

    bot = ClipForgeTelegramBot(token, owner_id)

    def stop(_signum: int, _frame: object) -> None:
        bot.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    bot.run()


if __name__ == "__main__":
    main()
