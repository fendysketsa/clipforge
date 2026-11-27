"""Additional RYUUNDY cron topics, with distinct source-grounded Long roles."""
from __future__ import annotations

import re

PROFILES = {
    "practical_knowledge": {
        "label": "Sains, Teknologi & Pengetahuan Praktis",
        "tone": "penasaran, jelas dan berbasis sumber; bedakan demonstrasi, hasil uji, opini dan janji; jangan mengarang statistik atau klaim kesehatan/keuntungan",
        "short_role": "jawab satu masalah sains atau teknologi dengan contoh atau demonstrasi yang tersedia dan satu hasil atau batasan utuh",
        "long_role": "susun pertanyaan, mekanisme atau langkah, bukti yang tersedia, keterbatasan dan kesimpulan yang membantu penonton memahami topik",
        "duration_filter": "any",
        "queries": ["sains teknologi indonesia penjelasan praktis", "inovasi kecerdasan buatan indonesia contoh dan batasan", "eksperimen pengetahuan praktis indonesia cara kerja"],
    },
    "moral_animation_story": {
        "label": "Animasi Cerita Moral & Konsekuensi Pilihan",
        "tone": "cerita fiksi Indonesia yang hangat dan menarik; bedakan fiksi dari kejadian nyata, ikuti pilihan tokoh dan akibatnya; istilah azab dalam judul sumber bukan bukti hukuman Tuhan dan bukan dasar klaim agama; jangan meniru suara, karakter, atau desain kreator",
        "short_role": "pilih satu keputusan tokoh, akibat yang terlihat dan satu pelajaran utuh; beri konteks bahwa ini cerita fiksi, tanpa adegan mengerikan atau cliffhanger yang menyesatkan",
        "long_role": "susun kebutuhan tokoh, godaan atau konflik, keputusan, akibat dan penyelesaian yang tersedia pada sumber; jangan menyambung episode dengan akhir karangan atau mengubah fiksi menjadi kisah nyata",
        "duration_filter": "any",
        "queries": [
            "animasi cerita moral indonesia pedagang jujur konsekuensi pilihan",
            "kartun indonesia cerita kehidupan kejujuran akibat keserakahan",
            "cerita fiksi animasi indonesia pelajaran hidup alur lengkap",
            "Kartun Acing cerita moral animasi indonesia",
        ],
    },
    "nostalgia_indonesia": {
        "label": "Nostalgia, Arsip & Kehidupan Indonesia Tempo Dulu",
        "tone": "hangat, informatif dan berbasis sumber; bedakan ingatan pribadi, arsip bertanggal, interpretasi, ilustrasi dan rekonstruksi; pengalaman masa lalu berbeda menurut tempat dan keluarga, jangan menganggap semua orang dahulu hidup lebih baik",
        "short_role": "angkat satu benda, kebiasaan atau perubahan kehidupan tempo dulu; tunjukkan konteks waktu/tempat dari sumber dan satu jawaban atau perbandingan yang tuntas; visual ilustrasi atau rekonstruksi wajib dikenali sebagai ilustrasi",
        "long_role": "bangun perjalanan kehidupan pada satu masa atau tempat melalui rumah, sekolah, permainan, pasar atau teknologi; jelaskan perubahan dan sumber arsip, pisahkan nostalgia dari fakta sejarah, dan simpulkan tanpa mengarang tanggal, lokasi, harga atau asal rekaman",
        "duration_filter": "any",
        "queries": [
            "nostalgia kehidupan indonesia tahun 1980 an dokumenter",
            "indonesia tempo dulu arsip kehidupan sehari hari sejarah",
            "sejarah permainan tradisional sekolah pasar indonesia zaman dulu",
            "ZamanEmas kehidupan indonesia tahun 1980 nostalgia",
            "Dunia Sejarah arsip indonesia tempo dulu konteks sejarah",
        ],
    },
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
    "film_story_lesson": {
        "label": "Pelajaran dari Alur Cerita Film",
        "tone": "story-first dan orisinal: ambil hanya struktur pilihan tokoh, konflik, akibat, dan akhir yang tuntas; jangan memakai footage, dialog, judul film, pemeran, atau spoiler pihak ketiga",
        "short_role": "ambil satu keputusan tokoh dan akibat yang terlihat dalam satu momen utuh; tokoh dan naskah RYUUNDY sendiri, tanpa klaim kisah nyata",
        "long_role": "susun konteks, motif, keputusan, konsekuensi, perubahan hubungan, dan akhir dari naskah orisinal; tiap bagian memberi informasi baru dan tidak mengulang Short",
        "duration_filter": "any",
        "queries": [
            "cerita film keluarga pilihan tokoh dan konsekuensi alur lengkap",
            "kisah animasi orisinal kejujuran pengorbanan dan akibat pilihan",
            "cerita moral anak dari alur film yang menginspirasi naskah baru",
        ],
    },
    "game_story_competitive": {
        "label": "Game Kompetitif: MLBB & Free Fire",
        "tone": "energik, ringkas, dan berbasis momen nyata; utamakan keputusan, kerja tim, kegagalan, comeback, atau reaksi spontan; jangan menjanjikan menang atau memberi tutorial klaim",
        "short_role": "ambil satu momen pertandingan dengan taruhan jelas, perubahan situasi, dan payoff yang tuntas; karakter dan naskah orisinal",
        "long_role": "susun setup tim, keputusan, konsekuensi, reaksi, dan hasil akhir dari sumber yang sama; tiap bagian memberi informasi baru",
        "duration_filter": "any",
        "queries": [
            "mobile legends indonesia cerita pertandingan comeback lucu",
            "free fire indonesia cerita mabar teamwork plot twist",
            "mlbb indonesia momen kalah menang obrolan pemain",
            "free fire indonesia reaksi pemain cerita seru terbaru",
            "game kompetitif indonesia cerita pemain singkat berkesan",
        ],
    },
    "podcast_kisah_hidup": {
        "label": "Podcast Kisah Hidup & Pilihan",
        "tone": "hangat, reflektif, dan jujur; bedakan pengalaman narasumber, opini, dan fakta; labeli sebagai cerita, jangan mengarang kutipan atau klaim",
        "short_role": "ambil satu pengalaman atau keputusan dengan makna yang jelas dan akhir yang tuntas, tanpa nama atau kutipan palsu",
        "long_role": "rangkai konteks, keputusan, konsekuensi, perubahan, dan makna dari naskah orisinal; jangan menyalin dialog podcast pihak ketiga",
        "duration_filter": "any",
        "queries": [
            "podcast kisah hidup indonesia obrolan jujur pilihan",
            "cerita kehidupan indonesia pengalaman kerja pertama dan pelajaran",
            "podcast indonesia dialog Refleksi kebiasaan baik sehari hari",
        ],
    },
    # Public YouTube search measured on 2026-11-27: top results for recent
    # Indonesian podcast conversations reached 7,699,814 and 7,044,229 views.
    # That clears the 5,000K demand bar; it is evidence of interest, not a
    # forecast for RYUUNDY.
    "podcast_trend_terkini": {
        "label": "Podcast Tren Terkini & Perbincangan Hangat",
        "tone": "aktual, hangat, dan jujur; bicarakan topik yang benar-benar sedang ramai tanpa mengarang angka, kutipan, atau jaminan viral; bedakan fakta, opini narasumber, dan perkiraan",
        "short_role": "ambil satu topik yang sedang ramai dari percakapan podcast, jelaskan pemicunya dalam dua detik pertama, lalu tutup dengan satu jawaban atau batasan yang utuh tanpa memotong makna",
        "long_role": "rangkai konteks topik, pertanyaan dan jawaban narasumber, bukti yang tersedia, serta simpulan yang tidak berlebihan; jangan menyalin dialog podcast pihak ketiga atau mengubah opini menjadi fakta",
        "duration_filter": "any",
        "queries": [
            "podcast indonesia terbaru topik hangat perbincangan",
            "podcast indonesia obrolan tren terkini dan konteksnya",
            "podcast indonesia bahas topik viral minggu ini",
            "wawancara podcast indonesia topik ramai dibicarakan",
        ],
    },
    "measured_trend_lesson": {
        "label": "Topik Ramai Terukur",
        "tone": "berbasis sinyal publik yang benar-benar teramati; jelaskan konteks dan makna, jangan mengklaim FYP, jaminan viral, atau angka yang tidak diukur",
        "short_role": "ambil satu sudut dari topik yang sedang ramai dan beri penjelasan singkat yang jujur serta batasan yang jelas",
        "long_role": "rangkai sebab-akibat, konteks, bukti yang tersedia, dan simpulan yang tidak berlebihan dari topik yang sama",
        "duration_filter": "any",
        "queries": [
            "topik sedang ramai dibicarakan orang indonesia penjelasan konteks singkat",
            "perbincangan hangat minggu ini penjelasan fakta dan batasannya",
            "tren cerita dan kebiasaan yang sedang dibahas orang indonesia sekarang",
        ],
    },
}

SIGNALS = {
    "practical_knowledge": {"sains", "teknologi", "kecerdasan buatan", "eksperimen", "astronomi", "inovasi", "produktivitas", "cara kerja", "keterampilan"},
    "moral_animation_story": {"cerita moral", "animasi azab", "kartun acing", "cerita fiksi", "pedagang curang", "keserakahan", "kejujuran"},
    "nostalgia_indonesia": {"nostalgia", "tempo dulu", "zaman dulu", "jaman dulu", "1980", "1980 an", "arsip", "permainan tradisional", "kehidupan masa lalu"},
    "legend_folklore": {"legenda", "cerita rakyat", "folklor", "folklore", "dongeng", "asal usul"},
    "domestic_politics": {"politik", "kebijakan", "pemerintah", "dpr", "pemilu", "pilkada", "kpk", "apbn", "menteri", "presiden"},
    "food_healthy_review": {"makanan sehat", "menu sehat", "bekal sehat", "gizi", "nutrisi", "sayuran", "porsi", "cara masak"},
    "food_taste_review": {"kuliner", "makanan", "masakan", "warung", "restoran", "rasa", "tekstur", "jajanan"},
    "film_story_lesson": {"alur cerita film", "recap film", "ringkasan film", "cerita film", "tokoh film", "ending film", "plot twist", "konflik tokoh"},
    "measured_trend_lesson": {"sedang ramai", "tren", "viral", "topik hangat", "ramai dibicarakan", "perbincangan", "fyp", "trending"},
    "game_story_competitive": {"mobile legends", "mlbb", "free fire", "game kompetitif", "ranked", "push rank"},
    "podcast_kisah_hidup": {"podcast", "kisah hidup", "pengalaman", "obrolan", "narasumber", "refleksi", "cerita hidup"},
    "podcast_trend_terkini": {"podcast", "tren terkini", "topik hangat", "topik viral", "perbincangan", "ramai dibicarakan", "wawancara"},
}

FILM_STORY_EDITOR_BRIEF = (
    "Lane alurfilm: pakai struktur cerita sebagai inspirasi, bukan materi. Jangan memakai footage film, "
    "dialog, judul film, pemeran, atau akhir/spoiler pihak ketiga. Tokoh, naskah, dan konteks harus "
    "orisinal RYUUNDY; fiksi diberi label jelas, satu pesan yang bisa dipahami, tanpa klaim kisah nyata."
)
MEASURED_TREND_EDITOR_BRIEF = (
    "Lane topik ramai: pakai hanya sinyal publik yang benar-benar teramati. Jangan mengarang angka "
    "penonton, menyebut FYP/jaminan viral, atau menjanjikan hasil. Jelaskan konteks, bukti yang tersedia, "
    "dan batasan pengetahuan; bedakan fakta, opini, dan perkiraan."
)

HASHTAGS = {
    "practical_knowledge": ["PengetahuanPraktis", "SainsTeknologi", "BelajarBersama"],
    "moral_animation_story": ["CeritaMoral", "AnimasiIndonesia", "CeritaFiksi"],
    "nostalgia_indonesia": ["NostalgiaIndonesia", "IndonesiaTempoDulu", "SejarahKehidupan"],
    "legend_folklore": ["LegendaNusantara", "CeritaRakyat", "BudayaNusantara"],
    "domestic_politics": ["PolitikIndonesia", "KebijakanPublik", "KonteksIndonesia"],
    "food_healthy_review": ["ReviewMakanan", "MenuSehat", "PilihanMenu"],
    "food_taste_review": ["ReviewKuliner", "KulinerNusantara", "CeritaMakanan"],
    "film_story_lesson": ["CeritaTokoh", "AlurPilihan", "KisahOrisinal"],
    "measured_trend_lesson": ["TopikRamai", "KonteksTerukur", "BukanJaminanViral"],
    "game_story_competitive": ["CeritaGame", "MLBB", "FreeFire", "ComebackTim"],
    "podcast_kisah_hidup": ["KisahHidup", "ObrolanJujur", "PilihanHidup"],
    "podcast_trend_terkini": ["PodcastTrenTerkini", "ObrolanHangat", "TopikTerkini"],
}


def requires_manual_review(theme_key: str) -> bool:
    return bool(PROFILES.get(theme_key, {}).get("manual_review_required"))


def source_rejection_reason(info: dict, theme_key: str) -> str:
    text = " ".join([str(info.get("title") or ""), str(info.get("description") or ""),
                     " ".join(map(str, info.get("tags") or []))]).casefold()
    if theme_key == "moral_animation_story":
        if not re.search(r"\b(?:animasi|kartun|animation|animated)\b", text):
            return "lane cerita moral membutuhkan sumber animasi/kartun fiksi, bukan tuduhan kejadian nyata"
    if theme_key == "film_story_lesson":
        # Only discussion/recap framing can inform an original scene. Raw
        # footage, full-film uploads and named casts are not source material.
        if re.search(r"\b(?:full movie|film penuh|full film|scene|adegan mentah|kompilasi adegan)\b", text):
            return "lane alurfilm menolak footage film mentah atau unggahan penuh"
        if not re.search(r"\b(?:alur cerita|recap|ringkasan|ulasan|pembahasan|bedah|narasi)\b", text):
            return "lane alurfilm hanya memakai sumber berupa pembahasan/recap alur, bukan cuplikan film"
    return ""
