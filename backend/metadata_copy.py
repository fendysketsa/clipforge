from __future__ import annotations

import hashlib
import re


def _stable_choice(seed: str, values: list[str], *, offset: int = 0) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return values[digest[offset % len(digest)] % len(values)]


def _topic_from_title(title: str) -> str:
    clean = re.sub(r"#[\w\d_]+", "", title, flags=re.UNICODE)
    clean = re.sub(r"\s+", " ", clean).strip(" .,:;!?-_—")
    words = clean.split()
    if len(words) > 9:
        clean = " ".join(words[:9]).rstrip(" .,:;!?-_—")
    return clean or "situasi dalam video ini"


def contextual_engagement_copy(
    *,
    title: str,
    context: str,
    islamic: bool = False,
    mystery: bool = False,
) -> tuple[str, str, list[str]]:
    """Return truthful, deterministic discussion copy derived from clip context.

    The function deliberately uses only broad situations evidenced by the title
    and transcript. It varies wording per clip without inventing names, events,
    or conclusions that are absent from the source.
    """
    searchable = f"{title} {context}".casefold()
    seed = f"{title}|{context[:800]}"

    if re.search(r"\b(waris|warisan|pewaris|ahli waris|takziah)\b", searchable):
        return (
            "Mari diskusikan:",
            "Bagian aturan warisan mana yang paling sering disalahpahami?",
            [
                "Simpan video ini sebagai pengingat sebelum membahas hak keluarga.",
                "Bagikan pembahasan ini kepada keluarga yang mungkin membutuhkannya.",
                "Tulis bagian aturan warisan yang menurutmu perlu dijelaskan lebih lanjut.",
            ],
        )

    if re.search(
        r"\b(cemburu|privasi|nomor hp|batasan|pacar|pasangan|hubungan|pertemanan|selingkuh)\b",
        searchable,
    ):
        questions = [
            "Menurutmu, reaksi dalam situasi ini masih wajar atau sudah melewati batas?",
            "Kalau kamu berada di posisi ini, batas apa yang perlu dibicarakan lebih dulu?",
            "Mana yang lebih penting dalam situasi ini: keterbukaan atau menjaga privasi?",
        ]
        ctas = [
            "Kirim ke teman yang punya sudut pandang berbeda soal batas dalam hubungan.",
            "Simpan jika kamu ingin membahas lagi soal kepercayaan dan privasi.",
            "Tulis batas yang menurutmu tetap perlu dijaga dalam situasi seperti ini.",
        ]
        return "Kalau menurutmu:", _stable_choice(seed, questions), ctas

    if re.search(
        r"\b(game|gaming|mabar|player|rank|clutch|gameplay|match|tim|kalah|menang)\b",
        searchable,
    ):
        questions = [
            "Keputusan mana yang paling menentukan hasil momen ini?",
            "Kalau kamu yang bermain, strategi apa yang akan kamu ubah?",
            "Menurutmu ini lebih dipengaruhi strategi, refleks, atau kerja sama tim?",
        ]
        ctas = [
            "Kirim ke teman mabar yang pasti punya analisis berbeda.",
            "Simpan momen ini untuk melihat lagi keputusan yang paling menentukan.",
            "Tulis strategi yang akan kamu pilih kalau menghadapi situasi yang sama.",
        ]
        return "Bahas momennya:", _stable_choice(seed, questions), ctas

    if re.search(
        r"\b(kampus|sekolah|kelas|dosen|guru|belajar|mahasiswa|siswa|ujian|pendidikan)\b",
        searchable,
    ):
        questions = [
            "Pelajaran apa yang paling relevan dari kejadian ini di lingkungan belajar?",
            "Kalau kejadian ini muncul di kelas atau kampusmu, apa yang sebaiknya dilakukan?",
            "Bagian mana yang paling menggambarkan dinamika di sekolah atau kampus?",
        ]
        ctas = [
            "Kirim ke teman sekolah atau kampus yang pernah melihat situasi serupa.",
            "Simpan sebagai bahan obrolan tentang batas dan sikap di lingkungan belajar.",
            "Tulis cara yang menurutmu paling sehat untuk menyelesaikan situasi ini.",
        ]
        return "Coba bayangkan:", _stable_choice(seed, questions), ctas

    if re.search(
        r"\b(kerja|kantor|atasan|bos|rekan kerja|karier|bisnis|pelanggan)\b",
        searchable,
    ):
        questions = [
            "Kalau ini terjadi di tempat kerja, langkah mana yang paling profesional?",
            "Menurutmu, siapa yang perlu memulai komunikasi lebih dulu dalam situasi ini?",
            "Batas profesional apa yang paling penting dari kejadian ini?",
        ]
        ctas = [
            "Kirim ke rekan yang suka membahas dinamika kerja secara terbuka.",
            "Simpan untuk mengingat kembali batas profesional dalam situasi serupa.",
            "Tulis langkah yang menurutmu paling masuk akal jika ini terjadi di tempat kerja.",
        ]
        return "Kalau di tempat kerja:", _stable_choice(seed, questions), ctas

    if mystery and islamic:
        return (
            "Coba telaah:",
            "Bagian mana yang bersumber dari dalil, penafsiran, atau cerita?",
            [
                "Simpan untuk menelaah kembali konteks dan sumber pembahasannya.",
                "Bagikan jika ini membantu membedakan dalil, penafsiran, dan cerita.",
                "Tulis bagian yang menurutmu masih perlu diperiksa sumbernya.",
            ],
        )
    if mystery:
        questions = [
            "Bagian mana yang merupakan fakta, pengalaman, atau penafsiran?",
            "Menurutmu, klaim mana yang masih perlu diperiksa sumbernya?",
            "Setelah melihat konteksnya, ini lebih dekat ke fakta, mitos, atau pengalaman pribadi?",
        ]
        return (
            "Coba bedakan:",
            _stable_choice(seed, questions),
            [
                "Simpan untuk memeriksa lagi konteks sebelum mempercayai klaimnya.",
                "Kirim ke teman yang suka membedakan cerita, penafsiran, dan fakta.",
                "Tulis bagian yang menurutmu paling membutuhkan bukti tambahan.",
            ],
        )
    if islamic:
        questions = [
            "Hikmah mana yang paling relevan dengan keadaanmu saat ini?",
            "Bagian mana yang paling ingin kamu terapkan dalam keseharian?",
            "Apa satu pelajaran yang ingin kamu ingat setelah menonton ini?",
        ]
        return (
            "Untuk direnungkan:",
            _stable_choice(seed, questions),
            [
                "Simpan jika kamu ingin merenungkan kembali pesan utamanya.",
                "Kirim kepada orang yang sedang membutuhkan pengingat seperti ini.",
                "Tulis satu hikmah yang paling ingin kamu bawa ke keseharian.",
            ],
        )

    topic = _topic_from_title(title)
    questions = [
        f"Dari “{topic}”, keputusan mana yang paling masuk akal menurutmu?",
        f"Bagian dari “{topic}” mana yang paling mengubah pandanganmu?",
        f"Kalau menghadapi situasi seperti “{topic}”, apa yang akan kamu lakukan?",
    ]
    ctas = [
        "Kirim ke teman yang mungkin melihat situasi ini dari sudut berbeda.",
        "Simpan untuk membandingkan lagi keputusan dan akibat dalam ceritanya.",
        "Tulis pendapatmu setelah melihat konteksnya sampai selesai.",
    ]
    return "Menurutmu:", _stable_choice(seed, questions), ctas


def choose_contextual_cta(seed: str, options: list[str]) -> str:
    return _stable_choice(seed, options, offset=1)
