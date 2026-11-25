"""Owner-supplied references: discovery hints and editorial structure, never rights grants."""
from __future__ import annotations

from copy import deepcopy

VERSION = 1
CHECKED_ON = "2026-11-25"
REFERENCES = (
    {
        "key": "kartun_acing_moral_story",
        "url": "https://www.youtube.com/watch?v=lJ7iSTmoAdc",
        "title": "AZAB PENJUAL AYAM GEPREK DZALIM - LICIK!! AYAM BUSUK DIJUAL DEMI JADI KAYA RAYA!!",
        "creator": "Kartun Acing", "handle": "@petualanganacing",
        "channel_id": "UCRsbWgKYa7WyhgogHzfZwTw",
        "theme_key": "moral_animation_story", "duration_seconds": 1297,
        "evidence": "youtube_metadata_oembed_and_thumbnail",
        "youtube_channel_verified": True, "channel_search_enabled": True,
        "adaptation": "Pelajari keputusan -> konsekuensi -> pelajaran pada animasi fiksi; labeli fiksi, jangan menyatakan azab nyata atau meniru karakter/voice kreator. Episode yang belum tuntas tidak boleh diberi akhir karangan.",
    },
    {
        "key": "uah_contextual_sermon_short",
        "url": "https://www.youtube.com/shorts/rzABQCp9YY4",
        "title": "Ustadz Adi Hidayat", "creator": "Ngaji Quran",
        "handle": "@ngajialquran37", "channel_id": "UC11EU3mqj375wJXNE4rCntw",
        "theme_key": "lecture_wisdom", "duration_seconds": 35,
        "evidence": "youtube_metadata_oembed_and_thumbnail",
        "youtube_channel_verified": True, "channel_search_enabled": False,
        "adaptation": "Pelajari kemasan satu nasihat singkat dengan caption stabil dan atribusi pembicara. Cari kajian lengkap untuk konteks pertanyaan/dalil/pengecualian; gambar atau judul belum memverifikasi kutipan, identitas suara, atau kelengkapan jawaban. Jangan memperpanjang Short 35 detik menjadi Long.",
    },
    {
        "key": "zamanemas_indonesia_1980",
        "url": "https://www.youtube.com/watch?v=-v5mR_d0XGM",
        "title": "Bikin NANGISS😭, Ternyata Begini Hidup Tahun 1980 di Indonesia",
        "creator": "ZamanEmas", "handle": "@ZamanEmasID",
        "channel_id": "UCtou1nUKZ-hNxXK4HIhp-6w",
        "theme_key": "nostalgia_indonesia", "duration_seconds": 2186,
        "evidence": "youtube_metadata_oembed_and_thumbnail",
        "youtube_channel_verified": True, "channel_search_enabled": True,
        "adaptation": "Pelajari nostalgia lewat rumah, sekolah, makanan, permainan dan kehidupan masyarakat. Beri konteks tempat/waktu, periksa asal visual dan pisahkan arsip asli, ilustrasi atau rekonstruksi; jangan menggeneralisasi pengalaman satu keluarga menjadi fakta seluruh Indonesia.",
    },
    {
        "key": "dunia_sjr_history_reference",
        "url": "", "title": "Dunia Sejarah — handle supplied by owner",
        "creator": "Dunia Sejarah", "handle": "@dunia.sjr", "channel_id": "",
        "theme_key": "nostalgia_indonesia", "duration_seconds": None,
        "evidence": "owner_handle_youtube_404_external_search_context",
        "youtube_channel_verified": False, "channel_search_enabled": False,
        "adaptation": "Gunakan arah topik sejarah dan kehidupan tempo dulu sebagai ide pencarian. Handle @dunia.sjr belum terverifikasi sebagai channel YouTube; jangan mengarang channel ID atau memperlakukan unggahan ulang sebagai bukti arsip atau izin penggunaan.",
    },
    {
        "key": "sensasi_trends_film_story_reference",
        "url": "https://www.youtube.com/@sensasitrends9553",
        "title": "Sensasi Trends — recap alur cerita film",
        "creator": "Sensasi Trends", "handle": "@sensasitrends9553",
        "channel_id": "UCb_er1PINGlJ_H6d9nfSjKA",
        "theme_key": "film_story_lesson", "duration_seconds": None,
        "evidence": "youtube_channel_metadata_and_public_atom_feed_2026_11_25",
        # Verified for editorial direction only. Exact-channel search stays off:
        # these are third-party film recaps with spoilers and no reuse licence.
        "youtube_channel_verified": True, "channel_search_enabled": False,
        "adaptation": ("Pakai hanya pola alur pilihan tokoh -> konflik -> akibat -> akhir sebagai arah "
                       "pencarian dan ukuran minat penonton. Kanal ini merangkum film pihak ketiga: "
                       "jangan pakai footage, dialog, judul film, pemeran, atau spoiler, dan jangan "
                       "jadikan sumber produksi. Ciptakan tokoh dan naskah RYUUNDY yang orisinal."),
    },
)


def reference_catalog() -> dict:
    return {
        "version": VERSION, "checked_on": CHECKED_ON,
        "scope": "scheduled_ryuundy_discovery_and_editorial",
        "references": deepcopy(list(REFERENCES)),
        "reference_count": len(REFERENCES), "transcripts_verified": False,
        "full_audiovisual_review_verified": False, "retention_verified": False,
        "grants_source_rights": False, "automatic_reference_reupload": False,
    }


def channel_search_specs(theme_key: str) -> list[tuple[str, str]]:
    """Only verified YouTube channels may enter exact-channel searches."""
    return list(dict.fromkeys(
        ("", row["channel_id"]) for row in REFERENCES
        if row["theme_key"] == theme_key and row["youtube_channel_verified"]
        and row["channel_search_enabled"] and row["channel_id"]
    ))


def editorial_brief(theme_key: str) -> str:
    parts = [row["adaptation"] for row in REFERENCES if row["theme_key"] == theme_key]
    if not parts:
        return ""
    import visual_style_hints
    hint = visual_style_hints.prompt_hint(theme_key)
    return ("Referensi pemilik channel, hanya struktur editorial: " + " ".join(parts)
            + " " + hint["text"])
