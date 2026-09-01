import base64
import io
import json

import long_animate
from llm import AIConfig
from long_animate import _fallback_storyboard, _motion_expression, build_storyboard


SCRIPT = (
    "Banyak orang mengira perubahan besar harus dimulai dengan langkah yang besar. "
    "Padahal kebiasaan kecil yang dilakukan setiap hari sering menentukan arah hidup. "
    "Saat semangat menurun, sistem yang sederhana membantu kita tetap bergerak. "
    "Mulailah dari satu tindakan yang bisa diselesaikan hari ini, lalu evaluasi hasilnya. "
    "Konsistensi bukan tentang sempurna, tetapi tentang kembali melangkah setelah berhenti."
)


def test_fallback_storyboard_has_story_arc_without_duplicate_filler():
    storyboard = _fallback_storyboard(SCRIPT)

    assert len(storyboard.scenes) >= 3
    assert storyboard.scenes[0].narrative_role == "cold_open"
    assert storyboard.scenes[-1].narrative_role == "payoff_conclusion"
    assert all(scene.duration_hint >= 6 for scene in storyboard.scenes)
    assert all("Do not add unrequested writing" in scene.visual_prompt for scene in storyboard.scenes)
    assert "exactly five naturally separated fingers" in storyboard.scenes[0].visual_prompt
    assert "hijab as her sole head covering" not in storyboard.scenes[0].visual_prompt
    assert "Indonesian people only" not in storyboard.scenes[0].visual_prompt
    assert len({scene.narration for scene in storyboard.scenes}) == len(storyboard.scenes)


def test_explicit_nonhuman_story_keeps_requested_subject_and_visual_style():
    script = """
    KARAKTER KONSISTEN: Robot penjelajah kecil berwarna jingga dengan satu antena biru.
    GAYA VISUAL: Animasi 3D clay stop-motion, tekstur tanah liat, cahaya biru dingin.

    ### ADEGAN 1 — Tiba di Europa
    VISUAL: Robot jingga turun dari wahana di permukaan es Europa yang retak.
    NARASI: Robot penjelajah tiba di Europa untuk mencari tanda samudra bawah tanah.

    ### ADEGAN 2 — Memindai Es
    VISUAL: Robot yang sama menempelkan pemindai biru pada retakan es bercahaya.
    NARASI: Pemindainya menangkap getaran air jauh di bawah lapisan es.

    ### ADEGAN 3 — Mengirim Temuan
    VISUAL: Antena robot menyala saat sinyal biru melesat menuju wahana di orbit.
    NARASI: Data penemuan dikirim ke wahana sebelum badai partikel tiba.
    """

    storyboard = _fallback_storyboard(script)

    assert storyboard.art_bible.startswith("Animasi 3D clay stop-motion")
    assert "Robot penjelajah kecil berwarna jingga" in storyboard.character_bible
    assert "robot jingga turun" in storyboard.scenes[0].visual_prompt.casefold()
    assert "permukaan es europa" in storyboard.scenes[0].visual_prompt.casefold()
    assert all("hijab" not in scene.visual_prompt.casefold() for scene in storyboard.scenes)
    assert all(not long_animate._has_any(scene.visual_prompt, ("peci",)) for scene in storyboard.scenes)
    assert all("indonesian people only" not in scene.visual_prompt.casefold() for scene in storyboard.scenes)


def test_ai_storyboard_removes_unrequested_stock_islamic_child(monkeypatch):
    script = (
        "Sebuah rover beroda enam mendarat di planet tandus saat matahari kembar terbit. "
        "Rover memindai bebatuan hitam untuk menemukan mineral yang menyimpan air. "
        "Badai debu mendekat dan menutup jalur kembali menuju kapsul. "
        "Mesin bor rover membuka jalan melalui lapisan batu yang rapuh. "
        "Sampel mineral akhirnya tersimpan aman sebelum badai mencapai lokasi."
    )
    payload = {
        "title": "Misi Planet Tandus",
        "hook": "Misi berpacu dengan badai.",
        "core_message": "Rover menyelamatkan sampel.",
        "art_bible": "cinematic 3D animation with ochre dust",
        "character_bible": "A Muslim boy wearing a white peci accompanies the rover",
        "scenes": [
            {
                "title": f"Misi {index}",
                "narration": narration,
                "visual_prompt": "A Muslim boy in a white peci stands beside the rover",
                "on_screen_text": "",
                "camera_motion": "push_in",
                "color_mood": "ochre and cobalt",
                "narrative_role": role,
            }
            for index, (narration, role) in enumerate(
                [
                    ("Rover beroda enam mendarat ketika dua matahari terbit di planet tandus.", "cold_open"),
                    ("Pemindai rover menemukan mineral penyimpan air di antara bebatuan hitam.", "context"),
                    ("Mesin bor rover menembus batu rapuh sebelum badai debu tiba.", "payoff_conclusion"),
                ],
                start=1,
            )
        ],
    }
    monkeypatch.setattr(long_animate, "chat_completion", lambda config, messages: json.dumps(payload))

    storyboard = build_storyboard(
        script,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
    )

    assert "Muslim boy" not in storyboard.character_bible
    assert all("muslim boy" not in scene.visual_prompt.casefold() for scene in storyboard.scenes)
    assert all(not long_animate._has_any(scene.visual_prompt, ("peci",)) for scene in storyboard.scenes)
    assert all("rover" in scene.visual_prompt.casefold() for scene in storyboard.scenes)


def test_ai_storyboard_keeps_scene_specific_direction(monkeypatch):
    payload = {
        "title": "Langkah Kecil Mengubah Arah",
        "hook": "Mengapa langkah kecil justru menentukan hidup?",
        "core_message": "Sistem sederhana menjaga konsistensi saat motivasi turun.",
        "art_bible": "layered Indonesian paper-cut cinema",
        "scenes": [
            {
                "title": f"Scene {index}",
                "narration": narration,
                "visual_prompt": f"Symbolic composition number {index} with layered depth",
                "on_screen_text": f"Langkah {index}",
                "camera_motion": motion,
                "color_mood": "emerald and warm gold",
                "narrative_role": role,
            }
            for index, (narration, motion, role) in enumerate(
                [
                    ("Perubahan besar tidak selalu dimulai dengan tindakan yang besar dan sulit dilakukan.", "push_in", "cold_open"),
                    ("Kebiasaan kecil yang diulang setiap hari perlahan membentuk arah dan keputusan hidup kita.", "pan_right", "context"),
                    ("Sistem sederhana menjaga langkah tetap berjalan ketika semangat dan motivasi mulai menurun.", "drift_up", "development"),
                    ("Mulailah dari satu tindakan hari ini lalu evaluasi hasilnya tanpa menuntut kesempurnaan.", "pull_out", "payoff_conclusion"),
                ],
                start=1,
            )
        ],
    }
    monkeypatch.setattr(
        long_animate,
        "chat_completion",
        lambda config, messages: json.dumps(payload),
    )

    storyboard = build_storyboard(
        SCRIPT,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
    )

    assert storyboard.title == "Langkah Kecil Mengubah Arah"
    assert "3D" in storyboard.art_bible
    assert [scene.camera_motion for scene in storyboard.scenes] == [
        "push_in",
        "pan_right",
        "drift_up",
        "pull_out",
    ]
    assert storyboard.scenes[-1].narrative_role == "payoff_conclusion"
    assert all("original fictional" in scene.visual_prompt for scene in storyboard.scenes)


def test_three_minute_script_rejects_an_undersegmented_ai_storyboard(monkeypatch):
    long_script = " ".join(
        f"Bagian {index} menjelaskan perubahan, sebab, contoh, dan akibat yang berbeda."
        for index in range(1, 37)
    )
    payload = {
        "title": "Terlalu Sedikit Scene",
        "hook": "Hook",
        "core_message": "Pesan",
        "art_bible": "polished animated-film still",
        "character_bible": "No recurring character",
        "scenes": [
            {
                "title": f"Scene {index}",
                "narration": "Narasi pendek.",
                "visual_prompt": "Satu objek berubah di lingkungan yang relevan.",
                "shots": ["Satu objek berubah di lingkungan yang relevan."],
                "camera_motion": "push_in",
                "narrative_role": "development",
            }
            for index in range(1, 4)
        ],
    }
    monkeypatch.setenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", "180")
    monkeypatch.setattr(
        long_animate,
        "chat_completion",
        lambda config, messages: json.dumps(payload),
    )

    storyboard = build_storyboard(
        long_script,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
    )

    assert storyboard.title != "Terlalu Sedikit Scene"
    assert len(storyboard.scenes) >= 9


def test_motion_expression_varies_direction_without_static_slideshow():
    storyboard = _fallback_storyboard(SCRIPT)
    scene = storyboard.scenes[0]
    scene.camera_motion = "pan_right"

    zoom, x, y = _motion_expression(scene, 300)

    assert "on/300" in zoom
    assert "on/300" in x
    assert "iw-iw/zoom" in x
    assert "ih-ih/zoom" in y
    assert "sin(2*PI*on" in zoom


def test_long_animate_default_target_is_three_minutes(monkeypatch):
    monkeypatch.delenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", raising=False)

    assert long_animate._target_duration_seconds() == 180.0


def test_people_prompt_uses_restrained_story_action_instead_of_stock_hands():
    prompt = long_animate._compose_visual_prompt(
        "Seorang guru berjalan perlahan melewati halaman sekolah",
        "Ia mengamati perubahan suasana sebelum menjelaskan pelajarannya.",
        "polished animated-film still",
        "One recurring adult teacher",
    )

    assert "Keep hands below shoulder level" in prompt
    assert "No waving, raised palms" in prompt
    assert "hands dominating the foreground" in prompt


def test_ai_visual_cannot_authorize_raised_hands_or_a_crowd():
    prompt = long_animate._compose_visual_prompt(
        "A cheering worship crowd with raised hands and palms facing camera",
        "Saya ingin mengajak kalian memahami makna amanah dalam kehidupan sehari-hari.",
        "polished cinematic 3D animated-film still",
        "One recurring adult narrator",
    )

    assert "Visible moment: Saya ingin mengajak kalian" in prompt
    assert "VISIBLE HUMAN LIMIT: 1" in prompt
    assert "ABSTRACT ADDRESS RULE" in prompt
    assert "The requested hand action may appear once" not in prompt


def test_user_locked_visual_can_explicitly_request_one_hand_action():
    prompt = long_animate._compose_visual_prompt(
        "Seorang guru mengangkat tangan untuk menunjukkan contoh gerakan",
        "Guru memperagakan gerakan yang disebutkan dalam pelajaran.",
        "polished cinematic 3D animated-film still",
        "One recurring adult teacher",
        visual_locked=True,
    )

    assert "Visible moment: Seorang guru mengangkat tangan" in prompt
    assert "The requested hand action may appear once" in prompt


def test_default_unrequested_visual_style_is_3d_animation(monkeypatch):
    monkeypatch.delenv("LONG_ANIMATE_DEFAULT_VISUAL_STYLE", raising=False)

    storyboard = _fallback_storyboard(SCRIPT)

    assert "3D" in storyboard.art_bible


def test_child_bathing_scene_gets_modest_3d_safety_and_water_camera_plan():
    prompt = long_animate._compose_visual_prompt(
        "Anak kecil mandi dan bermain air di kali dangkal",
        "Anak kecil mandi di kali yang dangkal pada pagi hari.",
        "polished cinematic 3D animated-film still",
        "One recurring young child",
        visual_locked=True,
    )
    motion, camera = long_animate._narrative_camera_plan(
        "Anak kecil mandi di kali yang dangkal"
    )

    assert "CHILD-SAFE WATER SCENE" in prompt
    assert "fully covered" in prompt
    assert "no nudity" in prompt
    assert "NARRATIVE ACTION CONTRACT" in prompt
    assert "3D animated-film" in prompt
    assert motion == "pan_right"
    assert "water action" in camera


def test_camera_motion_is_selected_from_each_scene_action():
    assert long_animate._narrative_camera_plan("Anak berjalan menuju sekolah")[0] == "pan_right"
    assert long_animate._narrative_camera_plan("Anak pergi ke sungai")[0] == "pan_right"
    assert long_animate._narrative_camera_plan("Ia membaca buku di meja")[0] == "push_in"
    assert long_animate._narrative_camera_plan("Ia melihat ikan dekat kakinya")[0] == "tilt_down"
    assert long_animate._narrative_camera_plan("Pesawat terbang menuju langit")[0] == "drift_up"
    assert long_animate._narrative_camera_plan("Akhirnya hasilnya terlihat jelas")[0] == "pull_out"


def test_each_narration_sentence_gets_a_distinct_3d_scene_contract():
    script = (
        "Pagi itu, seorang anak kecil pergi ke sungai. "
        "Ia mandi dan bermain air dengan gembira. "
        "Tiba-tiba ia melihat seekor ikan kecil berenang di dekat kakinya."
    )

    storyboard = _fallback_storyboard(script)

    assert [scene.narration for scene in storyboard.scenes] == [
        "Pagi itu, seorang anak kecil pergi ke sungai.",
        "Ia mandi dan bermain air dengan gembira.",
        "Tiba-tiba ia melihat seekor ikan kecil berenang di dekat kakinya.",
    ]
    assert len({scene.visual_prompt for scene in storyboard.scenes}) == 3
    assert [scene.transition for scene in storyboard.scenes] == [
        "hard_cut",
        "match_action",
        "match_object",
    ]
    assert "natural gait cycle" in storyboard.scenes[0].animation_direction
    assert "flowing water" in storyboard.scenes[1].animation_direction
    assert [scene.camera_motion for scene in storyboard.scenes] == [
        "pan_right",
        "pan_right",
        "tilt_down",
    ]
    assert "CHILD-SAFE WATER SCENE" in storyboard.scenes[1].visual_prompt
    assert "CHILD-SAFE WATER SCENE" in storyboard.scenes[2].visual_prompt
    assert "same recurring identity" in storyboard.scenes[2].continuity_anchor
    assert "Never reset character design" in storyboard.scenes[2].continuity_anchor
    assert all("SCENE ANIMATION DIRECTION" in scene.visual_prompt for scene in storyboard.scenes)
    assert all("SCENE CONTINUITY ANCHOR" in scene.visual_prompt for scene in storyboard.scenes)


def test_long_plain_script_keeps_the_last_sentence_when_scene_count_is_capped():
    sentences = [f"Kalimat {index} menjelaskan peristiwa yang berbeda." for index in range(1, 19)]

    chunks = long_animate._sentence_chunks(" ".join(sentences), max_chunks=14)

    assert len(chunks) <= 14
    assert "Kalimat 1" in chunks[0]
    assert "Kalimat 18" in chunks[-1]


def test_tts_duration_allocator_hits_exact_twenty_seconds():
    scenes = _fallback_storyboard(SCRIPT).scenes[:3]

    long_animate.allocate_scene_durations(scenes, [2.0, 3.0, 4.0], 20.0)

    assert sum(scene.duration for scene in scenes) == 20.0
    assert scenes[0].duration < scenes[1].duration < scenes[2].duration


def test_complex_scene_expands_to_multiple_gapless_shots(monkeypatch):
    script = """
    ### ADEGAN 1 — Keluar Rumah
    VISUAL: Seorang teknisi membuka pintu lalu berjalan menuju kendaraan di halaman.
    NARASI: Teknisi bergegas memeriksa kendaraan sebelum badai datang.

    ### ADEGAN 2 — Pemeriksaan
    VISUAL: Teknisi menempelkan pemindai pada mesin kendaraan.
    NARASI: Pemindai menemukan kabel utama yang hampir terputus.

    ### ADEGAN 3 — Perbaikan
    VISUAL: Teknisi mengunci kabel baru pada mesin yang kembali menyala.
    NARASI: Kabel pengganti membuat kendaraan siap menghadapi badai.
    """
    storyboard = _fallback_storyboard(script)
    long_animate.allocate_scene_durations(storyboard.scenes, [3.0, 3.0, 3.0], 20.0)
    monkeypatch.setenv("LONG_ANIMATE_TRANSITION_SECONDS", "0.12")

    shots = long_animate.plan_storyboard_shots(storyboard)
    effective_duration = sum(shot.duration for shot in shots) - 0.12 * (len(shots) - 1)

    assert len(shots) == 4
    assert shots[0].scene_index == shots[1].scene_index == 1
    assert "membuka pintu" in shots[0].visual_prompt
    assert "berjalan menuju kendaraan" in shots[1].visual_prompt
    assert round(effective_duration, 3) == 20.0


def test_long_scene_gets_an_alternate_story_shot_without_repeating_voice(monkeypatch):
    storyboard = _fallback_storyboard(SCRIPT)
    storyboard.scenes = storyboard.scenes[:1]
    storyboard.scenes[0].duration = 18.0
    storyboard.scenes[0].shot_prompts = storyboard.scenes[0].shot_prompts[:1]
    monkeypatch.setenv("LONG_ANIMATE_TRANSITION_SECONDS", "0")

    shots = long_animate.plan_storyboard_shots(storyboard)

    assert len(shots) == 2
    assert sum(shot.duration for shot in shots) == 18.0
    assert shots[0].narration == shots[1].narration
    assert shots[0].visual_prompt != shots[1].visual_prompt


def test_assemble_shots_uses_each_scene_transition(monkeypatch, tmp_path):
    shots = [
        long_animate.AnimateShot(
            index=index,
            scene_index=index,
            shot_index=1,
            shot_count=1,
            title=f"Shot {index}",
            narration=f"Narasi {index}",
            visual_prompt=f"Visual {index}",
            on_screen_text="",
            camera_motion="push_in",
            color_mood="blue",
            transition=transition,
            duration=3.0,
        )
        for index, transition in enumerate(
            ("hard_cut", "match_action", "match_object"),
            start=1,
        )
    ]
    paths = []
    for index in range(1, 4):
        path = tmp_path / f"shot_{index}.mp4"
        path.write_bytes(b"video")
        paths.append(path)
    captured = {}
    monkeypatch.setenv("LONG_ANIMATE_TRANSITION_SECONDS", "0.2")
    monkeypatch.setattr(
        long_animate,
        "_run",
        lambda command, cwd=None: captured.update(command=command, cwd=cwd),
    )

    long_animate.assemble_shot_videos(paths, shots, tmp_path)

    filters = captured["command"][captured["command"].index("-filter_complex") + 1]
    assert "transition=smoothleft" in filters
    assert "transition=dissolve" in filters


def test_render_shot_has_no_black_fade_or_audio_padding(monkeypatch, tmp_path):
    shot = long_animate.AnimateShot(
        index=1,
        scene_index=1,
        shot_index=1,
        shot_count=1,
        title="Shot",
        narration="Narasi",
        visual_prompt="Visual",
        on_screen_text="",
        camera_motion="push_in",
        color_mood="blue",
        duration=2.0,
    )
    captured = {}
    monkeypatch.setattr(long_animate, "_run", lambda command, cwd=None: captured.update(command=command, cwd=cwd))

    long_animate.render_shot_video(shot, tmp_path / "shot.png", tmp_path)

    command_text = " ".join(captured["command"])
    assert "fade=t=in" not in command_text
    assert "fade=t=out" not in command_text
    assert "apad" not in command_text
    assert "-an" in captured["command"]
    assert "sin(2*PI*on" in command_text
    assert "sin(2*PI*t/7)" in command_text


def test_markdown_scene_script_is_parsed_without_production_labels():
    script = """
    # Prompt Video
    Buat video edukasi Islami dalam format 16:9.

    ### Scene 1 — Bersiap Mengaji (0:00–0:20)
    Seorang anak laki-laki Muslim berusia 9 tahun mengenakan baju koko putih dan peci,
    sedang merapikan pakaian di ruang belajar yang bersih.
    Teks layar: “Bersih sebelum mengaji”
    Narasi: “Sebelum mengaji, rapikan pakaian dan bersihkan tempat belajar.”

    ### Scene 2 — Membuka Al-Qur'an (0:20–0:40)
    Anak yang sama duduk sopan dan membuka Al-Qur'an di atas rehal kayu.
    Teks layar: “Duduk dengan sopan”
    Narasi: “Letakkan Al-Qur'an dengan hormat dan duduklah dengan tenang.”

    ### Scene 3 — Belajar Bersama Guru (0:40–1:00)
    Seorang ustaz ramah berbaju krem duduk di samping anak dan menyimak bacaannya.
    Teks layar: “Baca perlahan”
    Narasi: “Bacalah perlahan, kemudian perbaiki pelafalan bersama guru.”
    """

    storyboard = _fallback_storyboard(script)

    assert len(storyboard.scenes) == 3
    assert storyboard.scenes[0].title == "Bersiap Mengaji"
    assert storyboard.scenes[0].on_screen_text == "Bersih sebelum mengaji"
    assert "merapikan pakaian" in storyboard.scenes[0].visual_prompt
    assert "Teks layar" not in storyboard.scenes[0].visual_prompt
    assert "Narasi:" not in storyboard.scenes[0].visual_prompt
    assert "Scene 2" not in storyboard.scenes[0].visual_prompt
    assert "baju koko putih" in storyboard.character_bible
    assert all("Continuity bible:" in scene.visual_prompt for scene in storyboard.scenes)


def test_structured_ai_art_direction_is_flattened_to_plain_prompt():
    assert long_animate._clean_text(
        {"pakaian_koko_putih": {}, "ruangan": {"cahaya_hangat": {}}}, 200
    ) == "pakaian koko putih, ruangan: cahaya hangat"

    assert long_animate._clean_text(
        "{'subject': 'anak', 'action': 'membaca', 'setting': 'ruang belajar'}", 200
    ) == "subject: anak, action: membaca, setting: ruang belajar"


def test_prose_director_prompt_voices_only_explicit_narrator_copy():
    script = """
    Karakter utama adalah seorang anak laki-laki berusia 9 tahun mengenakan koko putih.

    Awali video dengan anak menghentikan mainannya di dekat jendela. Tampilkan teks: “Saatnya Mengaji”.
    Narator berkata, “Al-Qur'an adalah petunjuk kehidupan bagi umat Islam.”

    Anak membasuh kedua tangan di tempat wudu yang bersih. Tampilkan teks: “Bersuci”.
    Narator menjelaskan bahwa sebelum mengaji, bersihkan diri dan berwudulah dengan tenang.

    Anak duduk di samping ustaz dan membuka buku di atas rehal. Tampilkan teks: “Baca Perlahan”.
    Narator menutup dengan kalimat, “Bacalah perlahan dan dengarkan koreksi guru dengan sabar.”
    """

    storyboard = _fallback_storyboard(script)

    assert [scene.narration for scene in storyboard.scenes] == [
        "Al-Qur'an adalah petunjuk kehidupan bagi umat Islam.",
        "sebelum mengaji, bersihkan diri dan berwudulah dengan tenang.",
        "Bacalah perlahan dan dengarkan koreksi guru dengan sabar.",
    ]
    assert "menghentikan mainannya" in storyboard.scenes[0].visual_prompt
    assert "Narator" not in storyboard.scenes[0].visual_prompt
    assert "Narrative context" not in storyboard.scenes[0].visual_prompt
    assert storyboard.scenes[0].on_screen_text == "Saatnya Mengaji"


def test_explicit_silent_scene_has_no_automatic_voice_or_title_copy():
    script = """
    ### ADEGAN 1 — Pagi
    VISUAL: Anak berdiri di dekat jendela dan menatap halaman.
    NARASI: Pagi yang tenang menjadi awal untuk belajar.

    ### ADEGAN 2 — Jeda
    VISUAL: Cahaya bergerak perlahan di atas rehal kayu.
    NARASI: -

    ### ADEGAN 3 — Belajar
    VISUAL: Anak duduk di samping guru dengan sikap rapi.
    NARASI: Ia mulai membaca perlahan bersama gurunya.
    """

    storyboard = _fallback_storyboard(script)

    assert storyboard.scenes[1].narration == ""
    assert storyboard.scenes[1].on_screen_text == ""
    assert storyboard.scenes[1].duration_hint == 4.5


def test_islamic_indonesian_tts_profile_normalizes_pronunciation_only(monkeypatch):
    original = (
        "QS. Al-Qur'an mengajarkan seorang Ustadz memperbaiki makhraj setelah wudhu, "
        "kemudian berdzikir kepada Allah SWT dan mengikuti Rasulullah SAW."
    )
    monkeypatch.setenv("LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian")

    spoken = long_animate._tts_pronunciation_text(original)

    assert "Surah Al Quran" in spoken
    assert "ustaz" in spoken
    assert "makhroj" in spoken
    assert "wudu" in spoken
    assert "zikir" in spoken
    assert "Alloh subhaanahu wa ta'aalaa" in spoken
    assert "shallallaahu alaihi wasallam" in spoken
    assert "Al-Qur'an" in original


def test_islamic_indonesian_tts_profile_pronounces_allah_consistently(monkeypatch):
    original = "Allah, allah, ALLAH, dan الله adalah tulisan yang tidak boleh dieja per huruf."
    monkeypatch.setenv("LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian")

    spoken = long_animate._tts_pronunciation_text(original)

    assert spoken == (
        "Alloh, Alloh, Alloh, dan Alloh adalah tulisan yang tidak boleh dieja per huruf."
    )
    assert original.startswith("Allah, allah, ALLAH")


def test_islamic_tts_expands_allah_and_muhamad_honorifics(monkeypatch):
    original = "ALLAH SWT mengutus Muhamad SAW sebagai teladan. Allah ﷻ dan Muhammad ﷺ dimuliakan."
    monkeypatch.setenv("LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian")

    spoken = long_animate._tts_pronunciation_text(original)

    assert spoken.count("Alloh subhaanahu wa ta'aalaa") == 2
    assert spoken.count("Muhammad shallallaahu alaihi wasallam") == 2
    assert "SWT" not in spoken
    assert "SAW" not in spoken
    assert original.startswith("ALLAH SWT")


def test_long_animate_tts_honors_explicit_indonesian_prosody(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    scene.narration = "Bacalah Al-Qur'an bersama ustadz dan perbaiki makhraj setelah wudhu."
    captured = {}

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        captured["command"] = command
        output_path = command[command.index("--write-media") + 1]
        long_animate.Path(output_path).write_bytes(b"audio" * 200)
        return Result()

    monkeypatch.setenv("LONG_ANIMATE_VOICE", "id-ID-ArdiNeural")
    monkeypatch.setenv("LONG_ANIMATE_VOICE_RATE", "-6%")
    monkeypatch.setenv("LONG_ANIMATE_VOICE_PITCH", "-2Hz")
    monkeypatch.setenv("LONG_ANIMATE_VOICE_VOLUME", "+0%")
    monkeypatch.setenv("LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian")
    monkeypatch.setattr(long_animate.subprocess, "run", fake_run)

    output, provider = long_animate.synthesize_narration(scene, tmp_path)

    assert provider == "edge_neural"
    assert output.is_file()
    assert "--rate=-6%" in captured["command"]
    assert "--pitch=-2Hz" in captured["command"]
    assert "--volume=+0%" in captured["command"]
    spoken = captured["command"][captured["command"].index("--text") + 1]
    assert "Al Quran" in spoken
    assert "ustaz" in spoken
    assert "makhroj" in spoken
    assert "wudu" in spoken
    assert "Al-Qur'an" in scene.narration


def test_long_animate_tts_defaults_to_clear_natural_prosody(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    captured = {}

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        captured["command"] = command
        output_path = command[command.index("--write-media") + 1]
        long_animate.Path(output_path).write_bytes(b"audio" * 200)
        return Result()

    for name in (
        "LONG_ANIMATE_VOICE_RATE",
        "LONG_ANIMATE_VOICE_PITCH",
        "LONG_ANIMATE_VOICE_VOLUME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(long_animate.subprocess, "run", fake_run)

    output, provider = long_animate.synthesize_narration(scene, tmp_path)

    assert provider == "edge_neural"
    assert output.is_file()
    assert "--rate=+8%" in captured["command"]
    assert "--pitch=+2Hz" in captured["command"]
    assert "--volume=+8%" in captured["command"]


def test_short_narration_shrinks_timeline_instead_of_slurring(monkeypatch):
    scenes = _fallback_storyboard(SCRIPT).scenes[:3]
    monkeypatch.delenv("LONG_ANIMATE_MAX_SPEECH_TEMPO", raising=False)
    monkeypatch.delenv("LONG_ANIMATE_SCENE_BREATH_SECONDS", raising=False)

    duration = long_animate._effective_timeline_duration(scenes, [4.0, 5.0, 6.0], 180.0)

    assert duration == 16.05


def test_fit_voice_never_slows_narration_to_fill_scene(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    scene.duration = 30.0
    source = tmp_path / "voice.wav"
    source.write_bytes(b"voice")
    captured = {}

    monkeypatch.setattr(long_animate, "_media_duration", lambda path: 4.0)
    monkeypatch.setattr(
        long_animate,
        "_run",
        lambda command, **kwargs: captured.setdefault("command", command),
    )

    long_animate.fit_voice_to_scene(scene, source, tmp_path)

    audio_filter = captured["command"][captured["command"].index("-af") + 1]
    assert "atempo=1.000000" in audio_filter
    assert scene.speech_tempo == 1.0
    assert scene.voice_duration == 4.0


def test_subtitles_are_short_and_end_when_voice_ends(tmp_path):
    scenes = _fallback_storyboard(SCRIPT).scenes[:2]
    scenes[0].narration = "Bacalah perlahan agar setiap huruf terdengar jelas dan mudah diperbaiki oleh guru."
    scenes[0].duration = 8.0
    scenes[0].voice_duration = 5.2
    scenes[1].narration = ""
    scenes[1].duration = 4.0
    scenes[1].voice_duration = 0.0
    output = tmp_path / "story.srt"

    long_animate.write_story_subtitles(output, scenes)
    subtitle = output.read_text(encoding="utf-8")
    cue_text = [
        line
        for line in subtitle.splitlines()
        if line and "-->" not in line and not line.isdigit()
    ]

    assert cue_text
    assert all(len(line.split()) <= 7 for line in cue_text)
    assert "00:00:05,200" in subtitle
    assert "00:00:08" not in subtitle


def test_gemini_image_payload_uses_native_interactions_api(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "image",
                                    "mime_type": "image/jpeg",
                                    "data": base64.b64encode(b"x" * 2048).decode(),
                                }
                            ],
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv(
        "LONG_ANIMATE_IMAGE_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "gemini-3.1-flash-image")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_API_KEY", "test-gemini-key")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "2K")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_ASPECT_RATIO", "16:9")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_THINKING_LEVEL", "high")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_STRICT", "true")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "1")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.png") is True
    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert captured["payload"]["model"] == "gemini-3.1-flash-image"
    assert captured["payload"]["response_format"] == {
        "type": "image",
        "mime_type": "image/jpeg",
        "aspect_ratio": "16:9",
        "image_size": "2K",
    }
    assert captured["payload"]["generation_config"] == {"thinking_level": "high"}
    assert "Visible moment:" in captured["payload"]["input"]
    assert captured["headers"]["X-goog-api-key"] == "test-gemini-key"
    assert "Authorization" not in captured["headers"]


def test_gemini_receives_previous_character_reference(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"reference-image")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "image",
                                    "mime_type": "image/png",
                                    "data": base64.b64encode(b"x" * 2048).decode(),
                                }
                            ],
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode())
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "gemini-3.1-flash-image")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_API_KEY", "test-key")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "1")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.png", reference) is True
    blocks = captured["payload"]["input"]
    assert blocks[0]["type"] == "text"
    assert "immutable recurring-character" in blocks[0]["text"]
    assert blocks[1] == {
        "type": "image",
        "mime_type": "image/png",
        "data": base64.b64encode(b"reference-image").decode("ascii"),
    }


def test_gemini_strict_mode_rejects_missing_api_key(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    monkeypatch.setenv(
        "LONG_ANIMATE_IMAGE_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "gemini-3.1-flash-image")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_API_KEY", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_STRICT", "true")

    try:
        long_animate._remote_scene_image(scene, tmp_path / "scene.jpg")
    except long_animate.LongAnimateImageError as exc:
        assert "API key Gemini" in str(exc)
    else:
        raise AssertionError("strict mode harus menghentikan render tanpa API key")


def test_local_z_image_uses_sdcpp_openai_compatible_payload(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"data": [{"b64_json": base64.b64encode(b"z" * 2048).decode()}]}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_API_KEY", "")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "1024x576")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_TIMEOUT_SECONDS", "900")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "1")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.png") is True
    assert captured["url"] == "http://127.0.0.1:7860/v1/images/generations"
    assert captured["payload"]["size"] == "1024x576"
    assert captured["payload"]["output_format"] == "png"
    assert "fused fingers" in captured["payload"]["negative_prompt"]
    assert "disembodied hands" in captured["payload"]["negative_prompt"]
    assert "unrequested crowd" in captured["payload"]["negative_prompt"]
    assert "woman wearing peci" not in captured["payload"]["negative_prompt"]
    assert "verify natural hands and finger count" in captured["payload"]["prompt"]
    assert "model" not in captured["payload"]
    assert "quality" not in captured["payload"]
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 900
    assert long_animate._remote_provider_label(
        "http://127.0.0.1:7860/v1", "z-image-turbo-q3"
    ) == "local_z_image_turbo"


def test_local_z_image_retries_with_safer_resolutions(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    attempted_sizes = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"data": [{"b64_json": base64.b64encode(b"z" * 2048).decode()}]}
            ).encode()

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data.decode())
        attempted_sizes.append(payload["size"])
        if len(attempted_sizes) < 3:
            body = io.BytesIO(
                json.dumps({"error": {"message": "generate_image returned no results"}}).encode()
            )
            raise long_animate.urllib.error.HTTPError(
                request.full_url, 500, "generation failed", {}, body
            )
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "1536x864")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "3")
    monkeypatch.setattr(long_animate.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.png") is True
    assert attempted_sizes == ["1536x864", "1280x720", "1024x576"]


def test_local_z_image_waits_for_restart_and_downgrades_after_connection_refused(
    monkeypatch, tmp_path
):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    attempted_sizes = []
    sleeps = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"data": [{"b64_json": base64.b64encode(b"z" * 2048).decode()}]}
            ).encode()

    def fake_urlopen(request, timeout):
        attempted_sizes.append(json.loads(request.data.decode())["size"])
        if len(attempted_sizes) == 1:
            raise long_animate.urllib.error.URLError(
                ConnectionRefusedError(111, "Connection refused")
            )
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "1280x720")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "3")
    monkeypatch.setattr(long_animate.time, "sleep", sleeps.append)
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.png") is True
    assert attempted_sizes == ["1280x720", "1024x576"]
    assert sleeps == [6.0]


def test_normalize_accepts_valid_soft_image_and_applies_extra_sharpen(monkeypatch, tmp_path):
    path = tmp_path / "soft-scene.png"
    path.write_bytes(b"valid encoded image placeholder")
    image = long_animate.np.zeros((720, 1280, 3), dtype=long_animate.np.uint8)
    gray = long_animate.np.zeros((1080, 1920), dtype=long_animate.np.uint8)
    sharpen_passes = []

    monkeypatch.setattr(long_animate.cv2, "imdecode", lambda encoded, mode: image)
    monkeypatch.setattr(long_animate.cv2, "resize", lambda source, size, interpolation: image)
    monkeypatch.setattr(long_animate.cv2, "GaussianBlur", lambda source, kernel, sigma: source)
    monkeypatch.setattr(
        long_animate.cv2,
        "addWeighted",
        lambda source, alpha, blurred, beta, gamma: sharpen_passes.append(alpha) or source,
    )
    monkeypatch.setattr(long_animate.cv2, "cvtColor", lambda source, conversion: gray)
    monkeypatch.setattr(long_animate.cv2, "Laplacian", lambda source, depth: gray)
    monkeypatch.setattr(long_animate.cv2, "imwrite", lambda target, source, options: True)
    monkeypatch.setenv("LONG_ANIMATE_MIN_SHARPNESS", "30")

    assert long_animate._normalize_scene_image(path) is True
    assert sharpen_passes == [1.18, 1.32]
