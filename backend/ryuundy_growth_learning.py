"""Learn bounded cron preferences from measured, public Shorts only."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import math
import re
from statistics import median
from urllib.parse import urlparse, parse_qs

from ryuundy_reference_learning import clean_topic_text
from cron_drama import DRAMA_THEME_SIGNALS

CHARACTERS = re.compile(r"\b(?:yuta|kayuta|mio|baby (?:selin|celin|celine|celen))\b", re.I)
CHARACTER_QUERIES = [
    "roblox kak yuta mio baby selin cerita konflik dan penyelesaian bahasa indonesia",
    "kak yuta mio cerita roblox pilihan tokoh dan akibat indonesia",
    "mio baby celine roblox kerja sama tantangan cerita indonesia",
]
CHARACTER_EDITOR_BRIEF = (
    "Pelajaran pertumbuhan RYUUNDY: penonton merespons cerita karakter yang mudah dikenali. "
    "Mulai dari masalah atau tindakan tokoh dalam dua detik pertama, buang salam dan setup kosong, "
    "jelaskan siapa menginginkan apa, lalu tuntaskan satu perubahan atau akibat dalam klip yang sama. "
    "Gunakan nama dan konflik yang benar-benar ada di sumber; jangan menyisipkan Yuta/Mio pada cerita lain. "
    "Pertahankan identitas seri yang sesuai karakter sumber, judul spesifik tokoh + masalah, "
    "caption stabil dan gambar ekspresi/aksi yang terbaca. Jangan menggantungkan jawaban untuk part berikutnya, "
    "menambah durasi demi target, atau menyalin hashtag agama ke cerita game/fiksi. "
    "Uji pembuka terhadap baseline seri yang sama; views publik tidak membuktikan retensi atau sebab kenaikan."
)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def remote_video_id(value):
    parsed = urlparse(value or "")
    if parsed.scheme != "https" or parsed.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return None
    if parsed.hostname == "youtu.be":
        candidate = parsed.path.strip("/")
    elif parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.path.startswith("/shorts/"):
        candidate = parsed.path.removeprefix("/shorts/").strip("/")
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None


def content_theme(text, signals, enabled_themes):
    text = " " + re.sub(r"[^a-z0-9]+", " ", clean_topic_text(text)).strip() + " "
    for key, origins in DRAMA_THEME_SIGNALS.items():
        if any(" " + re.sub(r"[^a-z0-9]+", " ", origin).strip() + " " in text for origin in origins):
            return (key, None) if key in enabled_themes else ("unclassified", None)
    # Names identify the proven roleplay series even when old uploads carried
    # the wrong playlist/hashtag. Do not learn content identity from hashtags.
    if CHARACTERS.search(text) and "gaming_story" in enabled_themes:
        return "gaming_story", "character_roleplay"
    scores = {}
    for key in enabled_themes:
        hits = sum(" " + re.sub(r"[^a-z0-9]+", " ", phrase.casefold()).strip() + " " in text
                   for phrase in signals.get(key, set()))
        if hits:
            scores[key] = hits
    if not scores:
        return "unclassified", None
    best = max(scores.values())
    winners = [key for key, hits in scores.items() if hits == best]
    if set(winners) == {"gaming_story", "famous_game_reaction"} and not re.search(r"\b(?:reaction|reaksi)\b", text):
        return "gaming_story", None
    # Ambiguous topic labels provide a baseline, not false niche attribution.
    return (winners[0], None) if len(winners) == 1 else ("unclassified", None)


def performance_report(uploads, *, signals, enabled_themes, now=None, lookback_days=28,
                       minimum_samples=3, minimum_views=1000, minimum_lift=1.5,
                       minimum_age_hours=24, target_channel="ryuundyofficial"):
    now = now or datetime.now(timezone.utc)
    samples, excluded, seen = [], Counter(), set()
    for row in sorted(uploads, key=lambda item: timestamp(item.updated_at) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        if row.status != "completed" or not row.upload_confirmed or row.dry_run:
            excluded["unconfirmed_or_dry_run"] += 1
            continue
        if row.target_channel.casefold().lstrip("@") != target_channel.casefold().lstrip("@"):
            excluded["other_channel"] += 1
            continue
        if row.clip_name.casefold().startswith(("highlight_5menit_", "resume_cerita_", "long_animate_")):
            excluded["long_format"] += 1
            continue
        # An exact remote identity is required, and retries cannot multiply votes.
        identity = remote_video_id(row.video_url)
        if not identity or identity in seen:
            excluded["missing_or_duplicate_remote_id"] += 1
            continue
        seen.add(identity)
        if row.visibility != "public":
            excluded["not_public"] += 1
            continue
        published = timestamp(row.publish_at or row.finished_at or row.created_at)
        if not published or not now - timedelta(days=lookback_days) <= published <= now - timedelta(hours=minimum_age_hours):
            excluded["outside_mature_publication_window"] += 1
            continue
        if not row.performance_snapshots:
            excluded["unmeasured"] += 1
            continue
        latest = row.performance_snapshots[-1]
        captured = timestamp(latest.captured_at)
        if not captured or captured < published + timedelta(hours=minimum_age_hours) or not now - timedelta(days=3) <= captured <= now + timedelta(minutes=5):
            excluded["stale_or_immature_measurement"] += 1
            continue
        if latest.source not in {"youtube_public", "youtube_analytics"} or not math.isfinite(latest.views):
            excluded["unsupported_measurement"] += 1
            continue
        if row.playlist.casefold() == "news":
            excluded["independent_news_lane"] += 1
            continue
        # Remove hashtags before classifying old misplaced #Islam metadata.
        text = re.sub(r"#\w+", " ", row.title + " " + row.clip_name)
        theme, series = content_theme(text, signals, enabled_themes)
        age_days = (captured - published).total_seconds() / 86400
        bucket = "1-3d" if age_days < 3 else "3-7d" if age_days < 7 else "7-14d" if age_days < 14 else "14d+"
        samples.append(dict(theme=theme, series=series, views=max(0, int(latest.views)),
            age_bucket=bucket, video_url=row.video_url, title=row.title,
            retained=latest.average_view_percentage is not None,
            stayed=latest.stayed_to_watch_percentage is not None))
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample["theme"]].append(sample)
    cohorts, candidates = {}, []
    for theme, rows in grouped.items():
        baseline = [sample for sample in samples if sample["theme"] != theme]
        lifts, character_lifts = [], []
        for sample in rows:
            peers = [peer["views"] for peer in baseline if peer["age_bucket"] == sample["age_bucket"]]
            if len(peers) >= minimum_samples:
                sample_lift = sample["views"] / max(1, median(peers))
                lifts.append(sample_lift)
                if sample["series"] == "character_roleplay":
                    character_lifts.append(sample_lift)
        measured_median = median([sample["views"] for sample in rows])
        lift = median(lifts) if lifts else None
        characters = [sample for sample in rows if sample["series"] == "character_roleplay"]
        character_median = median([sample["views"] for sample in characters]) if characters else 0
        character_lift = median(character_lifts) if character_lifts else 0
        evidence = dict(samples=len(rows), median_views=measured_median,
            age_matched_samples=len(lifts), median_age_matched_lift=round(lift, 3) if lift is not None else None,
            character_series_samples=len(characters), character_series_median_views=character_median,
            character_series_age_matched_lift=round(character_lift, 3),
            character_series_qualified=(len(character_lifts) >= minimum_samples
                and character_median >= minimum_views and character_lift >= minimum_lift),
            retention_samples=sum(sample["retained"] for sample in rows),
            stayed_to_watch_samples=sum(sample["stayed"] for sample in rows))
        cohorts[theme] = evidence
        if (theme in enabled_themes and len(rows) >= minimum_samples and len(lifts) >= minimum_samples
                and measured_median >= minimum_views and lift >= minimum_lift):
            candidates.append((lift, measured_median, theme))
    winner = max(candidates)[2] if candidates else None
    return dict(version=1, basis="measured_public_short_views", causal_claim=False,
        actual_retention_verified=False, lookback_days=lookback_days, minimum_age_hours=minimum_age_hours,
        eligible_samples=len(samples), excluded=dict(excluded), cohorts=cohorts, winner=winner,
        top_examples=sorted(samples, key=lambda item: item["views"], reverse=True)[:5])
