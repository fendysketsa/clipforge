#!/usr/bin/env python3
"""Create dynamic, vertical-safe ASS subtitles from JSON or SRT segments."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def parse_time(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", ".")
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw):
        return float(raw)
    parts = raw.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"invalid timestamp: {value!r}")


def extract_json_segments(payload: object) -> list[Segment]:
    if isinstance(payload, dict):
        for key in ("segments", "transcript", "items", "words"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("JSON must be a list or contain segments/transcript/items/words")

    segments: list[Segment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("word") or "").strip()
        if not text or "start" not in item or "end" not in item:
            continue
        start = parse_time(item["start"])
        end = parse_time(item["end"])
        if end > start:
            segments.append(Segment(start, end, text))
    return segments


def extract_srt_segments(content: str) -> list[Segment]:
    pattern = re.compile(
        r"(?:^|\n)\s*(?:\d+\s*\n)?"
        r"(\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[,.]\d{3})[^\n]*\n"
        r"(.*?)(?=\n\s*\n|\Z)",
        re.DOTALL,
    )
    segments: list[Segment] = []
    for match in pattern.finditer(content.replace("\r\n", "\n")):
        text = re.sub(r"\s+", " ", match.group(3)).strip()
        if text:
            segments.append(Segment(parse_time(match.group(1)), parse_time(match.group(2)), text))
    return segments


def load_segments(path: Path) -> list[Segment]:
    content = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        return extract_json_segments(json.loads(content))
    if path.suffix.lower() == ".srt":
        return extract_srt_segments(content)
    raise ValueError("input must be .json or .srt")


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cents = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cents:02d}"


def ass_color(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError(f"invalid color: {hex_color!r}; use #RRGGBB")
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"&H00{blue}{green}{red}&".upper()


def escape_ass(text: str) -> str:
    return (
        re.sub(r"\s+", " ", text).strip()
        .replace("\\", "＼")
        .replace("{", "｛")
        .replace("}", "｝")
    )


def word_chunks(words: list[str], maximum_words: int, maximum_chars: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for word in words:
        extra_chars = len(word) + (1 if current else 0)
        if current and (
            len(current) >= maximum_words or current_chars + extra_chars > maximum_chars
        ):
            chunks.append(current)
            current = []
            current_chars = 0
            extra_chars = len(word)
        current.append(word)
        current_chars += extra_chars
    if current:
        chunks.append(current)
    return chunks


def clip_segments(segments: list[Segment], offset: float, duration: float | None) -> list[Segment]:
    clip_end = float("inf") if duration is None else offset + duration
    clipped: list[Segment] = []
    for segment in segments:
        start = max(segment.start, offset)
        end = min(segment.end, clip_end)
        if end > start:
            clipped.append(Segment(start - offset, end - offset, segment.text))
    return clipped


def dialogue_events(
    segments: list[Segment], maximum_words: int, maximum_chars: int,
    highlight: str, keywords: set[str]
) -> list[str]:
    events: list[str] = []
    for segment in segments:
        words = escape_ass(segment.text).split()
        if not words:
            continue
        chunks = word_chunks(words, maximum_words, maximum_chars)
        total_weight = sum(max(1, len("".join(chunk))) for chunk in chunks)
        cursor = segment.start
        for chunk_index, chunk in enumerate(chunks):
            chunk_weight = max(1, len("".join(chunk)))
            if chunk_index == len(chunks) - 1:
                chunk_end = segment.end
            else:
                chunk_end = cursor + (segment.end - segment.start) * chunk_weight / total_weight
            word_weights = [max(1, len(re.sub(r"\W", "", word))) for word in chunk]
            word_cursor = cursor
            for word_index, _ in enumerate(chunk):
                if word_index == len(chunk) - 1:
                    word_end = chunk_end
                else:
                    word_end = word_cursor + (chunk_end - cursor) * word_weights[word_index] / sum(word_weights)
                rendered: list[str] = []
                for index, word in enumerate(chunk):
                    normalized = re.sub(r"[^\w']+", "", word.casefold())
                    if index == word_index:
                        rendered.append(f"{{\\c{highlight}\\b1}}{word}{{\\r}}")
                    elif normalized in keywords:
                        rendered.append(f"{{\\b1}}{word}{{\\r}}")
                    else:
                        rendered.append(word)
                events.append(
                    "Dialogue: 0,"
                    f"{ass_time(word_cursor)},{ass_time(max(word_cursor + 0.04, word_end))},"
                    "Shorts,,0,0,0,," + " ".join(rendered)
                )
                word_cursor = word_end
            cursor = chunk_end
    return events


def build_ass(args: argparse.Namespace, segments: list[Segment]) -> str:
    primary = ass_color(args.text_color)
    highlight = ass_color(args.highlight_color)
    outline = ass_color(args.outline_color)
    keywords = {
        re.sub(r"[^\w']+", "", item.casefold())
        for item in args.keywords.split(",")
        if item.strip()
    }
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Shorts,{args.font_name},{args.font_size},{primary},{primary},{outline},&H78000000,-1,0,0,0,100,100,0,0,1,{args.outline},1,2,80,160,{args.margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    return header + "\n".join(
        dialogue_events(segments, args.max_words, args.max_chars, highlight, keywords)
    ) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="ClipForge transcript JSON or SRT")
    parser.add_argument("--output", required=True, type=Path, help="Destination .ass file")
    parser.add_argument("--offset", type=float, default=0.0, help="Source start time to subtract")
    parser.add_argument("--duration", type=float, help="Clip duration; later subtitles are omitted")
    parser.add_argument("--max-words", type=int, default=5, help="Maximum words visible at once")
    parser.add_argument("--max-chars", type=int, default=26, help="Approximate character limit per caption")
    parser.add_argument("--font-name", default="DejaVu Sans")
    parser.add_argument("--font-size", type=int, default=72)
    parser.add_argument("--margin-v", type=int, default=330)
    parser.add_argument("--text-color", default="#FFFFFF")
    parser.add_argument("--highlight-color", default="#FFD400")
    parser.add_argument("--outline-color", default="#000000")
    parser.add_argument("--outline", type=float, default=4.0)
    parser.add_argument("--keywords", default="", help="Comma-separated words to keep bold")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input does not exist: {args.input}")
    if args.output.suffix.lower() != ".ass":
        raise SystemExit("output must use the .ass extension")
    if args.offset < 0 or (args.duration is not None and args.duration <= 0):
        raise SystemExit("offset must be non-negative and duration must be positive")
    if not 1 <= args.max_words <= 12:
        raise SystemExit("max-words must be between 1 and 12")
    if not 10 <= args.max_chars <= 42:
        raise SystemExit("max-chars must be between 10 and 42")
    if not 24 <= args.font_size <= 140 or not 0 <= args.outline <= 12:
        raise SystemExit("font-size or outline is outside the safe range")

    segments = clip_segments(load_segments(args.input), args.offset, args.duration)
    if not segments:
        raise SystemExit("no subtitle segments overlap the requested clip interval")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    args.output.write_text(build_ass(args, segments), encoding="utf-8")
    print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
