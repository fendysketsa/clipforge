from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import imageio_ffmpeg
from rich.console import Console
from rich.table import Table
from slugify import slugify
from yt_dlp import YoutubeDL


console = Console()


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class ClipCandidate:
    index: int
    start: float
    end: float
    duration: float
    score: int
    title: str
    reason: str
    text: str


HOOK_WORDS = {
    "intinya",
    "ternyata",
    "masalahnya",
    "kenapa",
    "gimana",
    "bagaimana",
    "cara",
    "jangan",
    "harus",
    "penting",
    "rahasia",
    "bedanya",
    "salah",
    "benar",
    "tips",
    "trik",
    "jadi",
    "kalau",
    "misalnya",
}

WEAK_STARTS = {
    "dan",
    "terus",
    "lalu",
    "nah",
    "jadi",
    "itu",
    "ini",
    "em",
    "eh",
    "ya",
}


def run(command: list[str], cwd: Path | None = None) -> None:
    process = subprocess.run(command, cwd=cwd, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {process.returncode}: {' '.join(command)}")


def ffmpeg_path() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def seconds_to_stamp(seconds: float, srt: bool = False) -> str:
    seconds = max(0, seconds)
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    whole = int(math.floor(seconds))
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    sep = "," if srt else "."
    return f"{h:02}:{m:02}:{s:02}{sep}{millis:03}"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_metadata(url: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        return sanitize_metadata(ydl.extract_info(url, download=False))


def download_video(url: str, work_dir: Path, force: bool = False) -> tuple[Path, dict]:
    info_path = work_dir / "metadata.json"
    existing = sorted(work_dir.glob("source.*"))
    if existing and info_path.exists() and not force:
        return existing[0], load_json(info_path)

    ydl_opts = {
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=1080]+bestaudio/"
            "best[height<=1080]/best"
        ),
        "outtmpl": str(work_dir / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_path(),
    }

    work_dir.mkdir(parents=True, exist_ok=True)
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = Path(ydl.prepare_filename(info))

    if not file_path.exists():
        downloaded = sorted(work_dir.glob("source.*"))
        if not downloaded:
            raise FileNotFoundError("Downloaded video was not found.")
        file_path = downloaded[0]

    save_json(info_path, sanitize_metadata(info))
    return file_path, sanitize_metadata(info)


def sanitize_metadata(info: dict) -> dict:
    keys = ["id", "title", "uploader", "duration", "webpage_url", "ext"]
    return {key: info.get(key) for key in keys}


def extract_audio(video_path: Path, audio_path: Path, force: bool = False, limit_seconds: float | None = None) -> Path:
    if audio_path.exists() and not force:
        return audio_path

    audio_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
    ]
    if limit_seconds:
        command.extend(["-t", f"{limit_seconds:.3f}"])
    command.append(str(audio_path))
    run(command)
    return audio_path


def transcribe(audio_path: Path, transcript_path: Path, model_name: str, language: str, force: bool = False) -> list[TranscriptSegment]:
    if transcript_path.exists() and not force:
        return [TranscriptSegment(**item) for item in load_json(transcript_path)]

    from faster_whisper import WhisperModel

    console.print(f"[bold]Loading model:[/bold] {model_name}")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        beam_size=1,
        best_of=1,
    )

    rows: list[TranscriptSegment] = []
    for segment in segments:
        text = re.sub(r"\s+", " ", segment.text).strip()
        if text:
            rows.append(TranscriptSegment(float(segment.start), float(segment.end), text))

    save_json(transcript_path, [asdict(item) for item in rows])
    console.print(f"[green]Transcribed[/green] {len(rows)} segments. Detected language: {getattr(info, 'language', language)}")
    return rows


def first_sentence(text: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .,!?:;-")
    words = cleaned.split()
    return " ".join(words[:max_words]).capitalize() or "Auto clip"


def score_window(items: list[TranscriptSegment], duration: float) -> tuple[int, list[str]]:
    text = " ".join(item.text for item in items)
    words = re.findall(r"[\w']+", text.lower())
    first_word = words[0] if words else ""
    hook_hits = sorted(HOOK_WORDS.intersection(words))

    score = 35
    reasons: list[str] = []

    if 45 <= duration <= 120:
        score += 18
        reasons.append("durasi pas")
    elif 35 <= duration <= 180:
        score += 12
        reasons.append("durasi masih oke")

    if hook_hits:
        bump = min(24, len(hook_hits) * 6)
        score += bump
        reasons.append("ada keyword hook: " + ", ".join(hook_hits[:4]))

    word_count = len(words)
    density = word_count / max(duration, 1)
    if density >= 1.8:
        score += 12
        reasons.append("speech padat")
    elif density >= 1.1:
        score += 6
        reasons.append("speech cukup padat")

    if text.rstrip().endswith((".", "!", "?")):
        score += 5
        reasons.append("ending terasa selesai")

    if first_word in WEAK_STARTS:
        score -= 10
        reasons.append("awal agak menggantung")

    if word_count < 55:
        score -= 12
        reasons.append("terlalu sedikit konteks")

    return max(1, min(100, score)), reasons


def build_candidates(
    segments: list[TranscriptSegment],
    min_duration: float,
    max_duration: float,
    limit: int,
) -> list[ClipCandidate]:
    candidates: list[ClipCandidate] = []
    if not segments:
        return candidates

    for start_idx, first in enumerate(segments):
        window: list[TranscriptSegment] = []
        for item in segments[start_idx:]:
            window.append(item)
            duration = window[-1].end - first.start
            if duration < min_duration:
                continue
            if duration > max_duration:
                break

            text = " ".join(part.text for part in window)
            score, reasons = score_window(window, duration)
            candidates.append(
                ClipCandidate(
                    index=0,
                    start=max(0, first.start - 0.35),
                    end=window[-1].end + 0.25,
                    duration=duration,
                    score=score,
                    title=first_sentence(text),
                    reason=", ".join(reasons) or "segmen stabil",
                    text=text,
                )
            )

    candidates.sort(key=lambda item: (item.score - abs(item.duration - 85) * 0.04), reverse=True)
    picked: list[ClipCandidate] = []
    remaining = candidates[:]
    while remaining and len(picked) < limit:
        best: ClipCandidate | None = None
        best_adjusted = -1_000.0
        for candidate in remaining:
            overlaps = any(not (candidate.end < item.start or candidate.start > item.end) for item in picked)
            if overlaps:
                continue
            duration_similarity = min((abs(candidate.duration - item.duration) for item in picked), default=999)
            diversity_bonus = 8 if duration_similarity > 18 else 0
            adjusted = candidate.score - abs(candidate.duration - 85) * 0.04 + diversity_bonus
            if adjusted > best_adjusted:
                best = candidate
                best_adjusted = adjusted

        if best is None:
            break
        best.index = len(picked) + 1
        picked.append(best)
        remaining.remove(best)

    picked.sort(key=lambda item: item.start)
    for idx, candidate in enumerate(picked, start=1):
        candidate.index = idx
    return picked


def segments_for_clip(segments: Iterable[TranscriptSegment], clip: ClipCandidate) -> list[TranscriptSegment]:
    return [item for item in segments if item.end > clip.start and item.start < clip.end]


def wrap_subtitle(text: str, max_chars: int = 32, max_lines: int = 2) -> str:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word]).strip()
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) == max_lines:
                break
        else:
            current.append(word)

    if current and len(lines) < max_lines:
        lines.append(" ".join(current))

    return "\n".join(lines)


def write_srt(path: Path, segments: list[TranscriptSegment], offset: float) -> None:
    lines: list[str] = []
    for idx, item in enumerate(segments, start=1):
        start = max(0, item.start - offset)
        end = max(start + 0.2, item.end - offset)
        lines.extend(
            [
                str(idx),
                f"{seconds_to_stamp(start, srt=True)} --> {seconds_to_stamp(end, srt=True)}",
                wrap_subtitle(item.text),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_clip(video_path: Path, clip: ClipCandidate, clip_segments: list[TranscriptSegment], clips_dir: Path, burn_subtitles: bool) -> Path:
    clips_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"clip_{clip.index:02}_{slugify(clip.title)[:42] or 'auto'}"
    srt_path = clips_dir / f"{base_name}.srt"
    json_path = clips_dir / f"{base_name}.json"
    out_path = clips_dir / f"{base_name}.mp4"
    temp_video_path = clips_dir / f"{base_name}.video_tmp.mp4"
    temp_audio_path = clips_dir / f"{base_name}.audio_tmp.wav"

    write_srt(srt_path, clip_segments, clip.start)
    save_json(json_path, asdict(clip))

    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if burn_subtitles and clip_segments:
        style = (
            "FontName=Arial,FontSize=5,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=0.6,Shadow=0,"
            "Alignment=2,MarginV=42"
        )
        vf = f"{vf},subtitles='{srt_path.name}':force_style='{style}'"

    duration = clip.end - clip.start
    common_input = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{clip.start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(video_path.resolve()),
    ]

    run(
        [
            *common_input,
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-profile:v",
            "baseline",
            "-level",
            "4.0",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(temp_video_path.name),
        ],
        cwd=clips_dir,
    )
    run(
        [
            *common_input,
            "-map",
            "0:a:0?",
            "-vn",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(temp_audio_path.name),
        ],
        cwd=clips_dir,
    )
    run(
        [
            ffmpeg_path(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+genpts",
            "-y",
            "-i",
            str(temp_video_path.name),
            "-i",
            str(temp_audio_path.name),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-disposition:a:0",
            "default",
            "-shortest",
            "-brand",
            "mp42",
            "-tag:v",
            "avc1",
            "-tag:a",
            "mp4a",
            "-movflags",
            "+faststart",
            str(out_path.name),
        ],
        cwd=clips_dir,
    )
    temp_video_path.unlink(missing_ok=True)
    return out_path


def print_candidates(candidates: list[ClipCandidate]) -> None:
    table = Table(title="Clip candidates")
    table.add_column("#", justify="right")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Reason")

    for item in candidates:
        table.add_row(
            str(item.index),
            seconds_to_stamp(item.start),
            seconds_to_stamp(item.end),
            str(item.score),
            item.title,
            item.reason,
        )
    console.print(table)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local YouTube auto clipper for short vertical videos.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--top", type=int, default=5, help="Number of clips to export")
    parser.add_argument("--min", type=float, default=35, help="Minimum clip duration in seconds")
    parser.add_argument("--max", type=float, default=180, help="Maximum clip duration in seconds")
    parser.add_argument("--model", default="Systran/faster-whisper-small", help="faster-whisper model name")
    parser.add_argument("--language", default="id", help="Transcription language code")
    parser.add_argument("--output", default="outputs", help="Output directory")
    parser.add_argument("--analyze-seconds", type=float, help="Only transcribe the first N seconds; useful for quick tests")
    parser.add_argument("--no-burn-subtitles", action="store_true", help="Create SRT files but do not burn subtitles into MP4")
    parser.add_argument("--force", action="store_true", help="Redo download, audio extraction, and transcription")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.min <= 0 or args.max <= args.min:
        console.print("[red]Invalid duration range.[/red]")
        return 2

    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Fetching metadata...[/bold]")
    metadata = fetch_metadata(args.url)
    title = metadata.get("title") or metadata.get("id") or "youtube-video"
    work_dir = root / slugify(title)[:80]
    work_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Fetching video...[/bold]")
    final_video_path, metadata = download_video(args.url, work_dir, force=args.force)
    save_json(work_dir / "metadata.json", metadata)

    cache_suffix = f"_{int(args.analyze_seconds)}s" if args.analyze_seconds else ""
    audio_path = extract_audio(
        final_video_path,
        work_dir / f"audio{cache_suffix}.wav",
        force=args.force,
        limit_seconds=args.analyze_seconds,
    )
    transcript = transcribe(
        audio_path,
        work_dir / f"transcript{cache_suffix}.json",
        args.model,
        args.language,
        force=args.force,
    )

    console.print("[bold]Scoring candidate clips...[/bold]")
    candidates = build_candidates(transcript, args.min, args.max, args.top)
    if not candidates:
        console.print("[red]No clip candidates found. Try lowering --min or increasing --max.[/red]")
        return 1

    save_json(work_dir / f"candidates{cache_suffix}.json", [asdict(item) for item in candidates])
    print_candidates(candidates)

    console.print("[bold]Exporting vertical clips...[/bold]")
    clips_dir = work_dir / "clips"
    exported: list[Path] = []
    for candidate in candidates:
        clip_segments = segments_for_clip(transcript, candidate)
        exported.append(export_clip(final_video_path, candidate, clip_segments, clips_dir, not args.no_burn_subtitles))

    console.print("[green]Done.[/green] Exported:")
    for path in exported:
        console.print(f"  {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise SystemExit(130)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)
