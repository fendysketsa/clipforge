"""Content routing for the channel's YouTube playlists (Shorts and long videos)."""

import re


CRON_THEME_PLAYLISTS = {
    "chinese_drama_story": "Drama China",
    "korean_drama_story": "Drama Korea",
    "love_betrayal": "Cinta dan Hubungan",
    "family_conflict": "Keluarga dan Rumah Tangga",
    "friendship_twist": "Persahabatan",
    "life_comeback": "Inspiratif",
    "mystery_story": "Horor",
    "humor_interlude": "Lucu",
    "gaming_story": "Gaming",
    "famous_game_reaction": "Gaming",
    "quirky_animation": "Animasi",
    "reaction_clip_story": "Lucu",
    "islamic_animation_kids": "Islam",
    "islamic_animation_general": "Islam",
    "podcast_conversation": "Podcast",
    "football_story": "Sepak Bola",
    "history_geography_nusantara": "Sejarah, Geografi & Budaya Nusantara",
    "faith_life": "Islam",
    "lecture_wisdom": "Islam",
    "news_hot": "News",
}


def classify_youtube_playlist(*values: str, theme_key: str = "") -> str:
    """Choose a topic, using whole words so incidental substrings cannot match.

    Known cron niches take priority; otherwise game names take priority over
    in-game horror/religious dialogue. Generic descriptions, attribution and
    channel-wide hashtags should not be supplied.
    Unknown topics belong in the channel's general playlist, never in Islam.
    """
    text = " ".join(value for value in values if isinstance(value, str)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    def contains(*markers: str) -> bool:
        return any(re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", text) for marker in markers)

    # The scheduler's durable niche is stronger evidence than isolated words
    # in dialogue (e.g. a fictional drama character saying "ustadz").
    if theme_key in CRON_THEME_PLAYLISTS:
        return CRON_THEME_PLAYLISTS[theme_key]
    if contains("drama china", "drama cina", "drama tiongkok", "drama mandarin", "chinese drama", "cdrama", "dracin"):
        return "Drama China"
    if contains("drama korea", "korean drama", "kdrama", "drakor"):
        return "Drama Korea"
    if contains(
        "roblox", "minecraft", "gameplay", "gaming", "mabar", "obby",
        "mobile legends", "free fire", "valorant", "pubg", "gta", "bangjblox", "sakura school simulator",
    ):
        return "Gaming"
    if contains("news hot", "politik indonesia", "dpr ri", "kebijakan publik indonesia"):
        return "News"
    if contains("cerita rakyat", "folklor", "folklore", "dongeng nusantara"):
        return "Cerita Rakyat"
    if contains("legenda", "legend of", "asal usul"):
        return "Legenda"
    if contains(
        "islam", "islami", "muslim", "al quran", "alquran", "quran", "hadis",
        "hadits", "ustad", "ustadz", "ustaz", "kajian", "dakwah", "hijrah",
        "masjid", "sholat", "salat", "sedekah", "nabi", "rasulullah",
    ):
        return "Islam"
    if contains(
        "horor", "horror", "hantu", "gaib", "mistis", "angker", "kuntilanak",
        "pocong", "genderuwo", "penampakan", "kerasukan", "misteri",
    ):
        return "Horor"
    if contains("sains", "science", "fisika", "kimia", "biologi", "astronomi", "ilmiah"):
        return "Sains"
    if contains("tips", "tutorial", "cara membuat", "cara mengatasi", "cara memakai", "panduan"):
        return "Tips"
    if contains("adat", "tradisi", "budaya", "upacara adat", "warisan budaya"):
        return "Adat"
    if contains("lucu", "humor", "komedi", "kocak", "punchline", "stand up", "parodi"):
        return "Lucu"
    if contains("motivasi", "motivation", "inspiratif", "inspirasi", "bangkit", "pantang menyerah"):
        return "Inspiratif"
    if contains("renungan", "merenung", "refleksi"):
        return "Renungan"
    if contains("hikmah", "nasihat", "nasehat", "pelajaran hidup"):
        return "Hikmah dan Nasihat"
    return "Everythings"
