"""Transcript-led research and visible source attribution for editorial clips.

Search results are leads, never proof. Only a locally reviewed source record
with an intact snapshot may become a source insert. Missing evidence remains
visible to viewers and in the production handoff.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import textwrap
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


REFERENCE_PATTERNS = (
    ("written_source", re.compile(
        r"\b(?:paragraf|artikel|berita|headline|judul berita|tulisan itu|"
        r"unggahan|postingan|caption)\b", re.I)),
    ("social_source", re.compile(r"\b(?:instagram|tiktok|twitter|facebook|akun resmi)\b", re.I)),
    ("spoken_source", re.compile(r"\b(?:dia bilang|dia mengatakan|perkataannya|ucapannya|"
        r"katanya begitu|pernyataan itu)\b", re.I)),
    ("allegation", re.compile(r"\b(?:admin punya masalah|motifnya apa|menipu|"
        r"fitnah|hoaks|memalsukan|dituduh|menuduh)\b", re.I)),
)
MEDIA_NAMES = ("Astro Awani", "Stadium Astro", "Kompas", "Detik", "Tempo", "CNN", "BBC", "Reuters")
LABELS = {
    "written_source": ("SUMBER TULISAN BELUM TERVERIFIKASI", "Periksa artikel lengkap dan paragraf yang dimaksud."),
    "social_source": ("UNGGAHAN ASLI BELUM TERVERIFIKASI", "Periksa akun, tanggal, dan unggahan aslinya."),
    "spoken_source": ("UCAPAN ASLI BELUM TERVERIFIKASI", "Periksa rekaman lengkap dan konteks ucapannya."),
    "allegation": ("PENILAIAN PEMBICARA", "Tuduhan atau motif belum dibuktikan oleh klip ini."),
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized(value: object) -> str:
    return _clean(value).casefold()


def _public_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").casefold()
    except ValueError:
        return False
    # URLs are attribution only; this module never fetches candidate URLs.
    return bool(parsed.scheme == "https" and "." in host and not parsed.username
                and not host.endswith((".local", ".localhost"))
                and not re.fullmatch(r"[\d.:]+", host))


class _SearchLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "a" and "result__a" in data.get("class", "").split():
            href = data.get("href", "")
            href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
            self.current = {"url": href, "title": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            if _public_url(self.current["url"]):
                self.current["title"] = _clean(self.current["title"])[:200]
                self.results.append(self.current)
            self.current = None


def search_source_leads(query: str) -> dict:
    """Bounded public search; never promote a title/snippet into verification."""
    request = urllib.request.Request(
        "https://html.duckduckgo.com/html/?q=" + quote(query[:300]),
        headers={"User-Agent": "Mozilla/5.0 (compatible; ClipForge source research)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            html = response.read(512_000).decode("utf-8", errors="replace")
        parser = _SearchLinks()
        parser.feed(html)
        results = parser.results[:4]
        blocked = any(word in html.casefold() for word in ("anomaly.js", "challenge-form", "captcha"))
        return {"status": "candidates_only" if results else "search_blocked" if blocked else "no_results",
                "candidates": results, "facts_verified": False}
    except (OSError, ValueError) as exc:
        return {"status": "search_unavailable", "candidates": [],
                "error_type": type(exc).__name__, "facts_verified": False}


def _reviewed_record(record: object, beat: dict, root: Path) -> dict | None:
    if not isinstance(record, dict) or record.get("review_status") != "source_checked":
        return None
    required = ("source_url", "publisher", "published_at", "checked_at", "reviewed_by", "excerpt")
    if any(not isinstance(record.get(key), str) or not _clean(record[key]) for key in required):
        return None
    if (not _public_url(record["source_url"])
            or _normalized(record.get("utterance")) != _normalized(beat["utterance"])
            or record.get("kind") != beat["kind"]
            or record.get("relationship") != "exact_reference"):
        return None
    # A short exact quotation, backed by captured source text. A related article
    # cannot silently stand in for the particular post being discussed.
    excerpt = _clean(record["excerpt"])
    if len(excerpt.split()) > 25 or len(excerpt) > 240:
        return None
    assets = {}
    for field, digest_field, suffixes in (
        ("snapshot_text", "snapshot_text_sha256", {".txt"}),
        ("image", "image_sha256", {".png", ".jpg", ".jpeg"}),
    ):
        if field == "image" and not record.get(field):
            continue
        try:
            path = (root / str(record.get(field) or "")).resolve()
            path.relative_to(root.resolve())
            if (path.suffix.casefold() not in suffixes or not path.is_file()
                    or path.stat().st_size > 10_000_000
                    or hashlib.sha256(path.read_bytes()).hexdigest() != record.get(digest_field)):
                return None
            if field == "image":
                with path.open("rb") as stream:
                    header = stream.read(8)
                if not (header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff")):
                    return None
        except (OSError, ValueError, RuntimeError):
            return None
        assets[field] = str(path)
    try:
        if _normalized(excerpt) not in _normalized(Path(assets["snapshot_text"]).read_text(encoding="utf-8")):
            return None
    except (OSError, UnicodeError):
        return None
    return {**{key: record[key] for key in required}, **assets,
            "excerpt": excerpt, "relationship": "exact_reference",
            "review_status": "source_checked", "facts_verified": False}


def build_evidence_plan(clip, segments, *, source_segments=None,
                        manifest_path: Path | None = None, research: bool | None = None) -> dict:
    """Identify timed references, research leads, and choose honest treatments."""
    duration = float(clip.end - clip.start)
    context_rows = [s for s in (source_segments or segments)
                    if clip.start - 120 <= s.start <= clip.end + 30]
    context = " ".join(s.text for s in context_rows)
    media = [name for name in MEDIA_NAMES if name.casefold() in context.casefold()]
    names = re.findall(r"\b[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){1,2}\b", clip.text)
    names = [name for name in names if not name.startswith(("Admin ", "Kalau ", "Coba ", "Dari "))]
    subject = " ".join(dict.fromkeys(names))[:120]
    beats = []
    for segment in sorted(segments, key=lambda s: s.start):
        if segment.end <= clip.start or segment.start >= clip.end:
            continue
        kind = next((kind for kind, pattern in REFERENCE_PATTERNS if pattern.search(segment.text)), None)
        if kind is None:
            continue
        start = max(0.0, float(segment.start - clip.start))
        if not math.isfinite(start) or duration - start < 1.5:
            continue
        if any(b["kind"] == kind and start - b["start"] < 18 for b in beats):
            continue
        utterance = _clean(segment.text)
        identity = f"{segment.start:.3f}|{kind}|{utterance}"
        beat = {
            "id": hashlib.sha256(identity.encode()).hexdigest()[:16],
            "kind": kind, "start": round(start, 3),
            "end": round(min(duration, start + 5.5), 3), "utterance": utterance,
            "source_start": round(segment.start, 3),
            "query": _clean((" ".join(media) if kind == "written_source" else "") + " " + subject + " " +
                            {"written_source": "berita artikel", "social_source": "Instagram unggahan akun resmi",
                             "spoken_source": "pernyataan video lengkap", "allegation": ""}[kind]),
            "named_source": ", ".join(media) if kind == "written_source" else "",
            "status": "opinion_only" if kind == "allegation" else "unresolved",
            "label": LABELS[kind][0], "note": LABELS[kind][1],
            "source": None, "search": {"status": "not_attempted", "candidates": []},
            "treatment": "single_accent_then_readable_hold", "rendered": False,
        }
        beats.append(beat)
        if len(beats) == 4:
            break
    for previous, following in zip(beats, beats[1:]):
        previous["end"] = min(previous["end"], round(following["start"] - 0.15, 3))
    beats = [b for b in beats if b["end"] - b["start"] >= 1.2]

    manifest = {}
    manifest_error = None
    if manifest_path and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("references", {}), dict):
                raise ValueError("invalid evidence manifest")
        except (OSError, ValueError, UnicodeError):
            manifest, manifest_error = {}, "invalid_manifest"
    research = (os.environ.get("SHORTS_EVIDENCE_RESEARCH_ENABLED", "true").casefold()
                in {"1", "true", "yes", "on"}) if research is None else research
    search_budget = 2
    searches = {}
    for beat in beats:
        if beat["kind"] == "allegation":
            continue  # A quote or a screenshot cannot establish someone's motive.
        record = manifest.get("references", {}).get(beat["id"])
        source = _reviewed_record(record, beat, manifest_path.parent) if record and manifest_path else None
        if source:
            beat.update(source=source, status="source_checked", label="SUMBER ASLI DIPERIKSA",
                        note="Kutipan sumber; penilaian pembicara tetap perlu dibedakan.")
        elif research:
            query = beat["query"]
            if query not in searches and search_budget:
                searches[query] = search_source_leads(query)
                search_budget -= 1
            beat["search"] = searches.get(query, {"status": "budget_exhausted", "candidates": []})
        else:
            beat["search"]["status"] = "disabled"
    unresolved = [b["id"] for b in beats if b["status"] != "source_checked"]
    return {"version": 1, "enabled": bool(beats), "beats": beats,
            "source_context": context[:7000], "media_named_in_transcript": media,
            "manifest_error": manifest_error, "unresolved_reference_ids": unresolved,
            "manual_context_review_required": bool(unresolved),
            "search_results_are_evidence": False, "facts_verified": False,
            "roles": {"truth_researcher": "find_exact_source_and_preserve_context",
                      "creative_team": "highlight_relevant_excerpt_and_show_attribution",
                      "director": "insert_on_spoken_reference_then_hold_for_reading"}}


def evidence_overlay_filter(plan: dict, output_dir: Path, stem: str) -> str:
    """Render source panels above captions; one accent followed by a steady hold.

    Call after reframing and decorative overlays, before captions. Asset names
    and textfile inputs are generated locally, never interpolated source text.
    """
    filters = []
    stem = re.sub(r"[^a-zA-Z0-9_.-]", "_", stem)[:100]
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    for index, beat in enumerate(plan.get("beats", [])):
        start, end = float(beat["start"]), float(beat["end"])
        active = f"enable='between(t,{start:.3f},{end:.3f})'"
        source = beat.get("source") or {}
        checked = beat["status"] == "source_checked"
        color = "0x40DECC" if checked else "0xF7C65E"
        image = source.get("image")
        panel_height = 680 if image else 336
        filters.extend([
            f"drawbox=x=64:y=250:w=900:h={panel_height}:color=0x071817@0.96:t=fill:{active}",
            f"drawbox=x=64:y=250:w=8:h={panel_height}:color={color}:t=fill:{active}",
            # The border appears once; captions and evidence do not blink.
            f"drawbox=x=64:y=250:w=900:h={panel_height}:color={color}@0.9:t=3:"
            f"enable='between(t,{start:.3f},{min(end, start + .35):.3f})'",
        ])
        rows = [(beat["label"], 32, 276, color, 42)]
        if checked:
            attribution = f"{source['publisher']} | {source['published_at']}"
            host_path = unquote(urlparse(source["source_url"]).netloc + urlparse(source["source_url"]).path)
            rows.extend([(attribution, 29, 330, "white", 49),
                         (host_path[:94], 22, 377, "0xA3BDB8", 66)])
            if image:
                asset_name = f"{stem}.evidence_{index}{Path(image).suffix.casefold()}"
                if Path(image).resolve() != (output_dir / asset_name).resolve():
                    shutil.copyfile(image, output_dir / asset_name)
                filters.append(
                    f"split[evbase{index}][evclock{index}];"
                    f"[evclock{index}]nullsink;movie=filename='{asset_name}',"
                    "scale=840:350:force_original_aspect_ratio=decrease,"
                    "pad=840:350:(ow-iw)/2:(oh-ih)/2:color=0x071817,setsar=1"
                    f"[evimg{index}];[evbase{index}][evimg{index}]overlay=x=94:y=438:"
                    f"eof_action=repeat:{active}"
                )
            rows.append((source["excerpt"], 31, 806 if image else 426, "white", 44))
        else:
            quote_text = " ".join(beat["utterance"].split()[:15])[:138]
            rows.extend([(f'Pembicara: "{quote_text}"', 30, 342, "white", 46),
                         (("Disebut pembicara: " + beat["named_source"] + ". " if beat.get("named_source") else "")
                          + beat["note"], 27, 470, "0xE2C78D", 52)])
        for row_index, (value, size, y, ink, width) in enumerate(rows):
            # Exact text lives in files, so punctuation cannot become FFmpeg code.
            filename = f"{stem}.evidence_{index}_{row_index}.txt"
            wrapped = textwrap.fill(_clean(value), width=width, break_long_words=True)
            (output_dir / filename).write_text(wrapped + "\n", encoding="utf-8")
            filters.append(f"drawtext=fontfile={font}:textfile='{filename}':expansion=none:"
                           f"fontcolor={ink}:fontsize={size}:line_spacing=10:x=96:y={y}:{active}")
        beat["rendered"] = True
    plan["overlays_rendered"] = bool(filters)
    return ",".join(filters)
