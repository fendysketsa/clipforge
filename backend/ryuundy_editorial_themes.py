"""Additional RYUUNDY cron topics, with distinct source-grounded Long roles."""
from __future__ import annotations

PROFILES = {
    "legend_folklore": {
        "label": "Legenda, Cerita Rakyat & Asal-Usul Nusantara",
        "tone": "sinematik dan penasaran; nyatakan legenda sebagai cerita rakyat, bedakan versi cerita dan fakta sejarah; jangan mengarang bukti atau kepastian gaib",
        "short_role": "pilih satu kejadian atau pilihan tokoh yang utuh dari legenda, dengan penanda cerita rakyat",
        "long_role": "ikuti latar budaya, tujuan tokoh, pilihan, akibat dan akhir cerita; jelaskan makna serta versi sumber tanpa mengubah legenda menjadi fakta sejarah",
        "duration_filter": "any",
        "queries": [
            "cerita rakyat legenda nusantara alur lengkap bahasa indonesia",
            "legenda asal usul danau gunung nusantara cerita rakyat",
            "dokumenter cerita rakyat nusantara budaya dan makna legenda",
        ],
    },
    "domestic_politics": {
        "label": "Politik Dalam Negeri, Kronologi & Dampak Kebijakan",
        "tone": "tenang, berimbang dan berbasis sumber; pisahkan fakta, opini, tuduhan dan putusan; identifikasi sumber dan tanggal kejadian, jangan menyimpulkan bersalah dari tuduhan",
        "short_role": "jelaskan satu pertanyaan politik Indonesia secara utuh dan berimbang; hasil disimpan untuk review manusia",
        "long_role": "susun pertanyaan publik, kronologi bertanggal yang terverifikasi, bukti dan atribusi, tanggapan pihak terkait serta dampak bagi masyarakat; akhiri dengan apa yang diketahui dan belum diketahui; wajib review fakta dan konteks sebelum upload",
        "duration_filter": "any",
        "manual_review_required": True,
        "queries": [
            "analisis kasus politik indonesia kronologi bukti dan tanggapan",
            "penjelasan kebijakan publik indonesia dampak masyarakat wawancara",
            "diskusi politik dalam negeri indonesia fakta opini konteks",
        ],
    },
    "food_healthy_review": {
        "label": "Review Makanan Sehat & Pilihan Menu",
        "tone": "praktis, jujur dan menyenangkan; jelaskan bahan, porsi dan cara masak yang benar-benar terlihat atau disebut; jangan menyebut makanan menyembuhkan penyakit atau mengarang angka gizi",
        "short_role": "jawab satu pertanyaan tentang bahan, porsi atau cara masak dengan contoh sumber dan batasannya",
        "long_role": "mulai dari kebutuhan memilih menu, periksa bahan/porsi/cara masak, bandingkan pilihan yang benar-benar diuji, rangkum rasa dan komprominya; pisahkan pengalaman makan, label gizi dan klaim kesehatan yang memerlukan bukti",
        "duration_filter": "any",
        "queries": [
            "review makanan sehat indonesia bahan porsi rasa cara masak",
            "ulasan menu sehat sehari hari indonesia perbandingan rasa bahan",
            "review bekal makanan sehat indonesia praktis dan enak",
        ],
    },
    "food_taste_review": {
        "label": "Review Makanan Enak & Cerita Kuliner",
        "tone": "hangat, menggugah selera dan jujur; rasa adalah pengalaman pengulas, bukan kepastian bagi semua orang; harga/lokasi/tanggal hanya bila tersedia pada sumber",
        "short_role": "angkat satu pengalaman rasa atau temuan kuliner yang spesifik dengan penilaian jujur sesuai sumber",
        "long_role": "bangun pertanyaan apakah sajian layak dicoba, tunjukkan cerita tempat/proses memasak yang tersedia, bandingkan rasa/tekstur/porsi/harga sesuai bukti, lalu simpulkan untuk siapa sajian itu cocok beserta kekurangannya",
        "duration_filter": "any",
        "queries": [
            "review kuliner indonesia rasa tekstur porsi harga jujur",
            "cerita kuliner nusantara proses masak dan review makanan",
            "review makanan enak indonesia warung lokal pengalaman rasa",
        ],
    },
}

SIGNALS = {
    "legend_folklore": {"legenda", "cerita rakyat", "folklor", "folklore", "dongeng", "asal usul"},
    "domestic_politics": {"politik", "kebijakan", "pemerintah", "dpr", "pemilu", "pilkada", "kpk", "apbn", "menteri", "presiden"},
    "food_healthy_review": {"makanan sehat", "menu sehat", "bekal sehat", "gizi", "nutrisi", "sayuran", "porsi", "cara masak"},
    "food_taste_review": {"kuliner", "makanan", "masakan", "warung", "restoran", "rasa", "tekstur", "jajanan"},
}

HASHTAGS = {
    "legend_folklore": ["LegendaNusantara", "CeritaRakyat", "BudayaNusantara"],
    "domestic_politics": ["PolitikIndonesia", "KebijakanPublik", "KonteksIndonesia"],
    "food_healthy_review": ["ReviewMakanan", "MenuSehat", "PilihanMenu"],
    "food_taste_review": ["ReviewKuliner", "KulinerNusantara", "CeritaMakanan"],
}


def requires_manual_review(theme_key: str) -> bool:
    return bool(PROFILES.get(theme_key, {}).get("manual_review_required"))
