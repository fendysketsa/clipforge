"""The bounded News Hot series; metadata is discovery evidence, never proof."""

import re

NEWS_HOT_THEME = "news_hot"
NEWS_HOT_TOPIC_SIGNALS = {
    "berita", "politik", "indonesia", "kebijakan", "pemerintah", "dpr", "dprd",
    "menteri", "presiden", "pemilu", "pilkada", "apbn", "apbd", "kpk", "ruu",
    "wawancara", "penjelasan", "analisis", "dialog", "diskusi", "konteks", "dampak",
}
NEWS_HOT_QUERIES = [
    "berita politik indonesia terbaru kebijakan dampak masyarakat penjelasan",
    "politik indonesia hari ini wawancara kebijakan publik",
    "berita dpr ri pemerintah indonesia terbaru konteks masyarakat",
]
NEWS_HOT_TONE = (
    "News Hot RYUUNDY: story-first, hangat, tenang, empatik, dan berimbang; "
    "jelaskan konflik, sebab-akibat, dampak bagi masyarakat, dan satu pelajaran utuh; "
    "tanpa provokasi, penghinaan, dukungan partisan, atau dramatisasi tuduhan"
)
NEWS_HOT_ROLE = (
    "Satu isu politik Indonesia, satu mikro-cerita tuntas. Sebutkan sumber dan tanggal unggah; "
    "tanggal unggah bukan bukti tanggal kejadian. Pisahkan fakta terverifikasi, opini pembicara, "
    "dan tuduhan yang belum terbukti. Jangan sebut berita terkini bila kejadian belum diverifikasi. "
    "Tampilkan bukti tulisan dan konteks bila tersedia; bila belum ada, nyatakan belum terverifikasi. "
    "Judul, thumbnail, subtitle, dan visual wajib setia pada sumber; tanpa kutipan atau bukti rekaan. "
    "Pertahankan konteks landscape dalam portrait, subtitle stabil, dan audio terukur. "
    "Review manusia atas fakta, konteks, hak penggunaan, dan tanggal kejadian wajib sebelum upload"
)


def news_hot_topic_rejection_reason(info: dict) -> str:
    text = " ".join(str(info.get(key) or "") for key in ("title", "description"))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())

    def has(*markers: str) -> bool:
        return any(re.search(r"\b" + re.escape(marker) + r"\b", text) for marker in markers)

    if not has("indonesia", "dpr ri", "dpr", "dprd", "bumn", "apbn", "apbd", "kpk", "istana negara"):
        return "News Hot membutuhkan konteks Indonesia yang jelas"
    if not has("politik", "kebijakan", "pemerintah", "dpr", "dprd", "menteri", "presiden", "pemilu", "pilkada", "apbn", "apbd", "kpk", "ruu"):
        return "News Hot khusus politik dan kebijakan publik Indonesia"
    if not has("berita", "wawancara", "penjelasan", "analisis", "dialog", "diskusi", "konteks", "dampak", "kebijakan", "konferensi pers"):
        return "News Hot membutuhkan konteks berita atau pembahasan yang menjelaskan isu"
    return ""
