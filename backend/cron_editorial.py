"""Cron-only editorial calendar, monthly discovery and durable rotation."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
from zoneinfo import ZoneInfo

from hijridate import Gregorian, Hijri

VERSION = 1
ZONE = ZoneInfo("Asia/Jakarta")
_LOCK = threading.RLock()
SPEAKERS = (
    "Ustadz Adi Hidayat", "Ustadz Abdul Somad", "Buya Yahya",
    "Ustadz Hanan Attaki", "Aa Gym", "Ustadz Khalid Basalamah",
    "Ustadz Syafiq Riza Basalamah", "Ustadz Firanda Andirja",
    "Ustadz Felix Siauw", "Ustadz Das'ad Latif", "Gus Baha",
    "Habib Husein Ja'far", "Ustadz Muhammad Nuzul Dzikri",
    "Ustadz Oemar Mita", "Ustadz Hilman Fauzi", "Ustadz Salim A. Fillah",
    "Ustadzah Mumpuni Handayayekti", "Ustadzah Oki Setiana Dewi",
)
LECTURE_TOPICS = (
    "nasihat kehidupan dan sabar", "keluarga dan akhlak", "taubat dan memperbaiki diri",
    "sedekah dan kepedulian", "menjaga lisan dan pergaulan", "syukur dan ujian hidup",
)
SEASONAL_SIGNALS = {
    "ramadan_season": {"ramadan", "ramadhan", "puasa", "tarawih", "sahur", "iftar",
        "buka puasa", "zakat fitrah", "lailatul qadar", "itikaf"},
    "eid_family_season": {"lebaran", "idul fitri", "idulfitri", "silaturahmi", "syawal", "mudik"},
    "hajj_charity_season": {"kurban", "qurban", "haji", "idul adha", "zulhijah", "dzulhijjah", "arafah"},
}
SEASONAL_HASHTAGS = {
    "ramadan_season": ["Ramadan", "IbadahPuasa", "HikmahRamadan"],
    "eid_family_season": ["IdulFitri", "Silaturahmi", "HikmahLebaran"],
    "hajj_charity_season": ["Haji", "Kurban", "Kepedulian"],
}


def religious_profile(label, queries):
    return dict(label=label, duration_filter="any", queries=queries,
        tone="hangat, beradab dan sesuai konteks sumber; pertahankan pertanyaan, dalil, pengecualian dan kesimpulan; kalender editorial bersifat perkiraan, bukan penetapan tanggal ibadah; jangan mengarang kutipan atau menyamaratakan perbedaan pendapat",
        short_role="jawab satu pertanyaan ibadah atau kehidupan yang relevan dengan musim ini dengan satu jawaban utuh dari sumber",
        long_role="susun konteks pertanyaan, dasar penjelasan pembicara, batasan atau perbedaan pendapat, contoh penerapan dan kesimpulan tanpa mencampur jawaban yang berbeda")


SEASONAL_PROFILES = {
    "ramadan_season": religious_profile("Ramadan, Persiapan Puasa & Hikmah Ibadah",
        ["kajian ramadan persiapan puasa indonesia", "ceramah ramadhan akhlak sedekah keluarga"]),
    "eid_family_season": religious_profile("Lebaran, Silaturahmi & Keluarga",
        ["kajian idul fitri silaturahmi keluarga indonesia", "hikmah lebaran menjaga akhlak setelah ramadan"]),
    "hajj_charity_season": religious_profile("Haji, Kurban & Kepedulian",
        ["kajian haji kurban kepedulian indonesia", "ceramah idul adha hikmah berbagi"]),
}


def local_now(now=None):
    value = now or datetime.now(ZONE)
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=ZONE)
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZONE)
    return value.astimezone(ZONE)


def season_context(now=None):
    today = local_now(now).date()
    result = dict(key="", theme_key="", priority_percent=0, date=today.isoformat(),
        timezone="Asia/Jakarta", calendar_basis="umm_al_qura_editorial_estimate",
        official_religious_date_confirmed=False)
    try:
        h = Gregorian(today.year, today.month, today.day).to_hijri()
        start = Hijri(h.year if h.month <= 9 else h.year + 1, 9, 1).to_gregorian()
        days = (date(start.year, start.month, start.day) - today).days
        result.update(hijri_year=h.year, hijri_month=h.month, hijri_day=h.day)
        if h.month == 9:
            result.update(key="ramadan_last_ten" if h.day >= 20 else "ramadan",
                theme_key="ramadan_season", priority_percent=75)
        elif h.month == 10 and h.day <= 7:
            result.update(key="eid", theme_key="eid_family_season", priority_percent=40)
        elif 0 < days <= 30:
            result.update(key="approaching_ramadan", theme_key="ramadan_season",
                priority_percent=40, estimated_days_until_ramadan=days)
        elif h.month == 12 and h.day <= 13:
            result.update(key="hajj_qurban", theme_key="hajj_charity_season", priority_percent=40)
    except (ValueError, OverflowError):
        result["calendar_basis"] = "hijri_range_unavailable"
    if not result["key"]:
        if today.month == 8 and today.day <= 17:
            result.update(key="independence", theme_key="history_geography_nusantara", priority_percent=40)
        elif (today.month == 12 and today.day >= 15) or (today.month == 1 and today.day <= 7):
            result.update(key="year_end", theme_key="nostalgia_indonesia", priority_percent=30)
        elif today.month in {6, 7}:
            result.update(key="school_holidays", theme_key="family_conflict", priority_percent=30)
    return result


def season_queries(context):
    key = context["key"]
    if key == "approaching_ramadan":
        return ["kajian persiapan ramadan puasa niat qadha indonesia",
                "ceramah menyambut ramadhan keluarga akhlak sedekah"]
    if key == "ramadan_last_ten":
        return ["kajian sepuluh malam terakhir ramadan lailatul qadar itikaf",
                "ceramah zakat fitrah menjaga ibadah akhir ramadhan indonesia"]
    if key == "ramadan":
        return ["kajian ramadan puasa sahur buka puasa akhlak indonesia",
                "ceramah ramadhan tarawih sedekah membaca quran keluarga"]
    if key == "eid":
        return ["kajian idul fitri silaturahmi keluarga memaafkan indonesia",
                "ceramah hikmah lebaran syawal menjaga ibadah"]
    if key == "hajj_qurban":
        return ["kajian haji kurban idul adha kepedulian indonesia",
                "ceramah dzulhijjah berbagi daging kurban hikmah ibadah"]
    if key == "independence":
        return ["sejarah kemerdekaan indonesia perjuangan tokoh nusantara",
                "cerita budaya indonesia makna kemerdekaan"]
    if key == "year_end":
        return ["nostalgia kehidupan indonesia perubahan zaman refleksi akhir tahun",
                "cerita kehidupan indonesia pelajaran setahun"]
    if key == "school_holidays":
        return ["cerita keluarga orang tua anak kegiatan libur sekolah",
                "hubungan keluarga kebersamaan anak saat liburan"]
    return []


def read_state(path):
    path = Path(path)
    if not path.exists():
        return dict(version=VERSION, selection_count=0, monthly_plan={}, reserved_runs=[])
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or value.get("version") != VERSION
            or type(value.get("selection_count")) is not int or value["selection_count"] < 0):
        raise ValueError("State editorial cron tidak valid; file dipertahankan.")
    if (not isinstance(value.get("monthly_plan", {}), dict)
            or not isinstance(value.get("reserved_runs", []), list)
            or not isinstance(value.get("history", []), list)):
        raise ValueError("Isi state editorial cron tidak valid; file dipertahankan.")
    return value


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".cron-editorial-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def record_selection(path, run_id, slot):
    if slot < 0:
        return
    with _LOCK:
        state = read_state(path)
        if run_id in state.get("reserved_runs", []):
            return
        state["selection_count"] = max(state["selection_count"], slot + 1)
        state["reserved_runs"] = [*state.get("reserved_runs", []), run_id][-100:]
        save_state(path, state)


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def matched_signals(text, markers):
    source = " " + normalized(text) + " "
    return [marker for marker in markers if " " + normalized(marker) + " " in source]


def build_monthly_plan(records, profiles, signals, unsafe, now=None):
    now = local_now(now)
    month = now.strftime("%Y-%m")
    topics = {}
    for record in records[:150]:
        if not isinstance(record, dict):
            continue
        title = re.sub(r"https?://\S+|www\.\S+|@[\w.]+", " ", html.unescape(str(record.get("text") or "")))
        title = " ".join(title.split())[:180]
        subject = title + " " + str(record.get("supporting_text") or "")[:500]
        if len(title) < 8 or matched_signals(subject, unsafe):
            continue
        # Credits/descriptions often contain unrelated theme words. A monthly
        # niche needs subject evidence in the title/query itself.
        if (str(record.get("category_id") or "") == "10"
                or record.get("live_broadcast_content") in {"live", "upcoming"}
                or re.search(r"\b(?:official (?:music|lyric)|music video|full album|kumpulan lagu|lagu dangdut|slow rock|live bantu|live main)\b|#live\b", title, re.I)):
            continue
        hits = {key: len(matched_signals(title, values)) for key, values in signals.items()
                if key in profiles}
        if not hits or not max(hits.values()):
            continue
        held = [key for key, count in hits.items() if count and profiles[key].get("manual_review_required")]
        key = max(held or hits, key=lambda k: (hits[k], k == "lecture_wisdom"))
        identity = normalized(title)
        if identity in topics:
            continue
        words = set(identity.split())
        if any(len(words & set(row["normalized"].split())) / max(1, len(words | set(row["normalized"].split()))) > .8
               for row in topics.values()):
            continue
        raw_weight = record.get("weight", 1)
        weight = float(raw_weight) if isinstance(raw_weight, (int, float)) and not isinstance(raw_weight, bool) else 1
        if not math.isfinite(weight):
            weight = 1
        topics[identity] = dict(
            id=f"monthly_{month.replace('-', '')}_{hashlib.sha256(identity.encode()).hexdigest()[:10]}",
            theme_key=key, topic=title, normalized=identity,
            queries=[f"{title} penjelasan indonesia"[:230], f"{title} cerita konteks indonesia"[:230]],
            discovery_score=round(hits[key] * 10 + min(20, math.log1p(max(0, weight))), 3),
            evidence={"source":str(record.get("source") or "unknown"), "url":str(record.get("url") or "")[:500],
                      "observed_at":now.isoformat()},
            verified_facts=False, grants_source_rights=False)
    ranked = sorted(topics.values(), key=lambda row: row["discovery_score"], reverse=True)
    # Keep different subjects instead of filling the month with one dominant feed.
    picked, buckets = [], {}
    for row in ranked:
        bucket = buckets.setdefault(row["theme_key"], [])
        if len(bucket) < 3:
            bucket.append(row)
    # Reserve one subject per parent before extra subjects of the same theme;
    # a large chart must not crowd out fresh kajian/knowledge demand.
    for round_index in range(3):
        for bucket in buckets.values():
            if len(bucket) > round_index and len(picked) < 12:
                row = bucket[round_index]
                row.pop("normalized", None)
                picked.append(row)
    return dict(month_key=month, refreshed_at=now.isoformat(),
        status="ready" if picked else "no_matching_live_signals", niches=picked,
        signal_count=len(records), source_count=len({str(row.get("source")) for row in records if isinstance(row, dict)}),
        all_channel_search=True, automatic_publication_authorized=False)


def refresh_due(state, now=None):
    now = local_now(now)
    plan = state.get("monthly_plan") or {}
    if plan.get("month_key") == now.strftime("%Y-%m") and plan.get("status") == "ready":
        return False
    if state.get("refresh_month_key") != now.strftime("%Y-%m"):
        return True
    try:
        retry = datetime.fromisoformat(str(state.get("next_refresh_attempt_at") or ""))
        return now >= retry.astimezone(ZONE)
    except ValueError:
        return True


def claim_refresh(path, now=None):
    now = local_now(now)
    with _LOCK:
        state = read_state(path)
        if not refresh_due(state, now):
            return False
        state["next_refresh_attempt_at"] = (now + timedelta(hours=6)).isoformat()
        state["refresh_month_key"] = now.strftime("%Y-%m")
        state["refresh_started_at"] = now.isoformat()
        save_state(path, state)
        return True


def finish_refresh(path, plan, diagnostics=()):
    with _LOCK:
        state = read_state(path)
        old = state.get("monthly_plan") or {}
        if old.get("month_key") and old["month_key"] != plan["month_key"]:
            state["history"] = [*state.get("history", []), old][-3:]
        state["monthly_plan"] = plan
        state["refresh_diagnostics"] = list(diagnostics)[:8]
        save_state(path, state)


def select_profile(state, base_key, base_profile, profiles, now=None):
    now = local_now(now)
    slot = state["selection_count"]
    context = season_context(now)
    key, profile = base_key, deepcopy(base_profile)
    metadata = dict(slot=slot, season_key="", monthly_niche_id="", speaker_seed="", month_key=now.strftime("%Y-%m"))
    share = context["priority_percent"]
    seasonal = bool(context["theme_key"] in profiles and (
        slot % 4 < 3 if share == 75 else slot % 10 < share // 10))
    if seasonal:
        key = context["theme_key"]
        profile = deepcopy(profiles[key])
        profile["queries"] = season_queries(context)
        metadata["season_key"] = context["key"]
        profile["tone"] += "; fokus musim " + context["key"] + ", tanggal ibadah tetap mengikuti otoritas setempat"
    else:
        plan = state.get("monthly_plan") or {}
        niches = [row for row in plan.get("niches", []) if row.get("theme_key") in profiles
                  and row["theme_key"] not in SEASONAL_PROFILES]
        if slot % 5 == 2 and plan.get("month_key") == metadata["month_key"] and plan.get("status") == "ready" and niches:
            niche = niches[(slot // 5) % len(niches)]
            key = niche["theme_key"]
            profile = deepcopy(profiles[key])
            profile["queries"] = list(niche["queries"])
            profile["tone"] += "; fokus subniche hasil radar bulan ini (data, bukan instruksi): " + json.dumps(niche["topic"], ensure_ascii=False)
            metadata["monthly_niche_id"] = niche["id"]
        elif context["theme_key"] not in SEASONAL_PROFILES and slot % 4 == 0 and "lecture_wisdom" in profiles:
            key = "lecture_wisdom"
            profile = deepcopy(profiles[key])
            name = SPEAKERS[(slot // 4) % (len(SPEAKERS) + 1)] if (slot // 4) % (len(SPEAKERS) + 1) < len(SPEAKERS) else ""
            topic = LECTURE_TOPICS[(slot // 4) % len(LECTURE_TOPICS)]
            profile["queries"] = [f"{name or 'ustadz indonesia'} {topic} kajian lengkap",
                f"kajian ustadz indonesia {topic} tanya jawab",
                f"ceramah indonesia {topic} nasihat utuh"]
            metadata["speaker_seed"] = name
    if context["theme_key"] and not seasonal and key in SEASONAL_PROFILES:
        key, profile = base_key, deepcopy(base_profile)
    # A seed name is a query, never a speaker whitelist or verified identity.
    profile["theme_focus"] = profile["queries"][slot % len(profile["queries"])]
    profile["tone"] = profile["tone"][:480]
    profile["dynamic_editorial"] = True
    return key, profile, metadata


def status(path, now=None):
    now = local_now(now)
    state = read_state(path)
    plan = state.get("monthly_plan") or {}
    current = plan.get("month_key") == now.strftime("%Y-%m")
    return dict(version=VERSION, scope="cron_only", timezone="Asia/Jakarta",
        all_channel_search=True, monthly_refresh=True, current_month=now.strftime("%Y-%m"),
        selection_count=state["selection_count"], season=season_context(now),
        monthly_plan=deepcopy(plan) if current else {},
        monthly_plan_current=current and plan.get("status") == "ready",
        next_refresh_attempt_at=state.get("next_refresh_attempt_at"),
        speaker_search_seeds=list(SPEAKERS), speaker_whitelist=False,
        manual_requests_modified=False, automatic_publication_authorized=False,
        refresh_diagnostics=state.get("refresh_diagnostics", []))

