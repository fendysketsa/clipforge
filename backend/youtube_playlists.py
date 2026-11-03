"""Content routing for the channel's YouTube playlists (Shorts and long videos)."""

import re


def classify_youtube_playlist(*values: str) -> str:
    """Choose a topic, using whole words so incidental substrings cannot match.

    Game names take priority over in-game horror/religious dialogue. Generic
    descriptions, attribution and channel-wide hashtags should not be supplied.
    Unknown topics belong in the channel's general playlist, never in Islam.
    """
    text = " ".join(value for value in values if isinstance(value, str)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    def contains(*markers: str) -> bool:
        return any(re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", text) for marker in markers)

    if contains(
        "roblox", "minecraft", "gameplay", "gaming", "mabar", "obby",
        "mobile legends", "free fire", "valorant", "pubg", "gta", "bangjblox",
    ):
        return "Gaming"
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
