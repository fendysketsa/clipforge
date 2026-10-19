import base64
import io
import json
from pathlib import Path

import long_animate
from llm import AIConfig
from long_animate import (
    _fallback_storyboard,
    _motion_expression,
    build_storyboard,
    expand_story_outline,
)


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
    assert "cinematic realistic" in storyboard.art_bible
    assert [scene.camera_motion for scene in storyboard.scenes] == [
        "push_in",
        "pan_right",
        "drift_up",
        "pull_out",
    ]
    assert storyboard.scenes[-1].narrative_role == "payoff_conclusion"
    assert "original fictional" not in storyboard.scenes[0].visual_prompt
    assert "original fictional" in storyboard.scenes[1].visual_prompt


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


def test_local_image_prompt_keeps_exact_action_and_drops_later_crowd_language():
    shot = long_animate.AnimateShot(
        index=3,
        scene_index=1,
        shot_index=3,
        shot_count=3,
        title="Upacara Bendera",
        narration=(
            "Bagas adalah anak laki-laki berusia sepuluh tahun. Ia bangun kesiangan di kamar. "
            "Dengan terburu-buru, Bagas memasang dasi asal-asalan di depan cermin. "
            "Setelah tiba di sekolah, seluruh siswa memenuhi lapangan upacara dan mengangkat tangan."
        ),
        visual_prompt=long_animate._compose_visual_prompt(
            "Bagas memasang dasi asal-asalan di depan cermin kamar",
            "Bagas adalah anak laki-laki berusia sepuluh tahun. Ia bangun kesiangan di kamar. "
            "Dengan terburu-buru, Bagas memasang dasi asal-asalan di depan cermin. "
            "Setelah tiba di sekolah, seluruh siswa memenuhi lapangan upacara dan mengangkat tangan.",
            "cinematic realistic 3D animation",
            "Bagas, anak laki-laki berusia sepuluh tahun",
            visual_locked=True,
        ),
        on_screen_text="",
        camera_motion="push_in",
        color_mood="warm morning light",
        duration=6.0,
    )

    prompt = long_animate._focused_image_generation_prompt(shot)

    assert "Visible moment: Bagas memasang dasi asal-asalan" in prompt
    assert "seluruh siswa" not in prompt
    assert "mengangkat tangan" not in prompt
    assert "No waving" not in prompt
    assert len(prompt) < 1800


def test_tower_crane_prompt_stays_machine_only_without_hand_tokens():
    visual = "Tower crane bergerak mengangkat material konstruksi"
    shot = long_animate.AnimateShot(
        index=1,
        scene_index=1,
        shot_index=1,
        shot_count=1,
        title="Tower Crane",
        narration=visual,
        visual_prompt=long_animate._compose_visual_prompt(
            visual,
            visual,
            "cinematic realistic architecture",
            "No recurring character is defined",
            visual_locked=True,
        ),
        on_screen_text="",
        camera_motion="push_in",
        color_mood="natural daylight",
        duration=5.0,
    )

    compiled = shot.visual_prompt.casefold()
    focused = long_animate._focused_image_generation_prompt(shot).casefold()

    assert "hands below shoulder" not in compiled
    assert "hand" not in compiled
    assert "people" not in compiled
    assert "person" not in compiled
    assert "human" not in compiled
    assert "visible subject count" not in focused
    assert "hand" not in focused
    assert "anatomy" not in focused
    assert "architecture or machinery geometry" in focused


def test_eating_bakso_prompt_requires_food_spoon_mouth_table_and_stall():
    contract = long_animate._physical_action_contract(
        "Raka sedang makan bakso di warung bakso",
        "Raka duduk lapar setelah pulang sekolah.",
    )

    lowered = contract.casefold()
    assert "bowl of bakso" in lowered
    assert "spoon" in lowered
    assert "open mouth" in lowered
    assert "table" in lowered
    assert "warung bakso" in lowered
    assert "shoulders and elbows" in lowered


def test_tying_necktie_prompt_keeps_both_hands_on_the_tie():
    contract = long_animate._physical_action_contract(
        "Bagas memasang dasi asal-asalan",
        "Bagas berada di kamar tidur pada pagi hari.",
    )

    lowered = contract.casefold()
    assert "both hands" in lowered
    assert "shirt collar" in lowered
    assert "necktie knot" in lowered
    assert "elbows stay close to the torso" in lowered


def test_genre_label_is_not_accepted_as_character_identity():
    script = (
        "KARAKTER KONSISTEN: komedi sekolah, drama anak-anak, persahabatan.\n"
        "Bagas adalah seorang anak laki-laki berusia sepuluh tahun yang bertubuh pendek."
    )

    bible = long_animate._character_bible(script)

    assert "Bagas adalah seorang anak laki-laki" in bible
    assert "Script character facts: komedi sekolah" not in bible


def test_outline_chunks_do_not_speak_duration_metadata():
    outline = """
    # Cerita Bagas
    **Genre:** Komedi sekolah.
    **Durasi cerita:** 10-12 menit.

    Bagas bangun kesiangan lalu berlari ke sekolah. Ia mengikuti upacara bersama Dimas.
    Akhirnya mereka belajar untuk saling membantu dan tidak menertawakan teman.
    **TAMAT.**
    """

    chunks = long_animate._outline_narration_chunks(outline, 3)
    joined = " ".join(chunks).casefold()

    assert "durasi cerita" not in joined
    assert "10-12 menit" not in joined
    assert "tamat" not in joined


def test_long_animate_default_target_is_three_minutes(monkeypatch):
    monkeypatch.delenv("LONG_ANIMATE_TARGET_DURATION_SECONDS", raising=False)

    assert long_animate._target_duration_seconds() == 180.0


def test_story_outline_expands_into_directed_drama_scenes(monkeypatch):
    outline = (
        "Seorang satpam miskin menggantikan temannya untuk kencan buta dan diremehkan keluarga kaya. "
        "Ketika perusahaan disabotase, keahlian lamanya menyelamatkan semua orang dan mengubah penilaian mereka."
    )
    narration = " ".join(
        "Raka menjaga sikap tenang ketika konflik baru memaksanya memilih tindakan yang berisiko namun benar"
        for _ in range(5)
    )
    payload = {
        "title": "Satpam yang Diremehkan",
        "art_bible": "cinematic realistic original Indonesian drama",
        "character_bible": "Raka, satpam dewasa dengan seragam biru tua yang konsisten",
        "location_bible": "Gedung kantor modern pada malam hujan",
        "scenes": [
            {
                "title": f"Beat {index}",
                "narration": narration,
                "visual": (
                    "Raka berdiri di lobi saat alarm merah menyala; "
                    "Raka membuka panel keamanan dengan alat kecil; "
                    "Raka menuntun para pegawai menuju pintu aman"
                ),
                "on_screen_text": f"Pilihan {index}",
            }
            for index in range(1, 8)
        ],
    }
    monkeypatch.setattr(long_animate, "chat_completion", lambda config, messages: json.dumps(payload))

    script, audit = expand_story_outline(
        outline,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
        target_duration=300,
    )

    assert audit["expanded"] is True
    assert audit["scene_count"] == 7
    assert "### ADEGAN 1 — Beat 1" in script
    assert "NARASI:" in script
    assert "VISUAL:" in script
    assert len(long_animate._scene_sections(script)) == 7


def test_story_outline_accepts_safe_scene_count_instead_of_failing_exact_target(monkeypatch):
    outline = (
        "Raka dikenal sebagai anak paling nakal di desa, tetapi diam-diam ia membantu warga yang kesulitan. "
        "Setelah menyelamatkan seorang anak dari sungai, warga akhirnya memahami luka dan kebaikan hatinya."
    )
    narration = " ".join(
        "Raka menghadapi akibat dari pilihannya sambil berusaha melindungi orang lain dengan berani"
        for _ in range(5)
    )
    payload = {
        "title": "Anak Badung yang Membuat Desa Menangis",
        "art_bible": "cinematic realistic original Indonesian village drama",
        "character_bible": "Raka, anak laki-laki sebelas tahun dengan pakaian sederhana yang konsisten",
        "location_bible": "Desa kecil dengan sekolah, sungai, dan perbukitan",
        "scenes": [
            {
                "title": f"Bagian {index}",
                "narration": narration,
                "visual": (
                    "Raka berlari melewati jalan desa; "
                    "Raka berhenti untuk menolong seorang warga; "
                    "Raka menatap sungai yang meluap"
                ),
                "on_screen_text": f"Pilihan {index}",
            }
            for index in range(1, 9)
        ],
    }
    monkeypatch.setattr(long_animate, "chat_completion", lambda config, messages: json.dumps(payload))

    script, audit = expand_story_outline(
        outline,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
        target_duration=300,
    )

    assert audit["scene_count"] == 8
    assert audit["preferred_scene_count"] == 7
    assert len(long_animate._scene_sections(script)) == 8


def test_story_outline_repairs_thin_scene_from_original_story(monkeypatch):
    outline = " ".join(
        f"Bagian cerita {index} menjelaskan pilihan Raka yang berani, akibatnya bagi warga desa, dan perubahan sikap keluarganya."
        for index in range(1, 61)
    )
    full_narration = " ".join(
        "Raka memahami akibat tindakannya dan berusaha memperbaiki keadaan bersama warga desa"
        for _ in range(5)
    )
    payload = {
        "title": "Perubahan Raka",
        "art_bible": "cinematic realistic original Indonesian village drama",
        "character_bible": "Raka, anak laki-laki sebelas tahun dengan pakaian sederhana yang konsisten",
        "location_bible": "Desa kecil dengan sekolah, sungai, dan perbukitan",
        "scenes": [
            {
                "title": f"Bagian {index}",
                "narration": "Raka takut.",
                "visual": "Raka diam.",
                "on_screen_text": "Raka berubah",
            }
            if index == 2
            else {
                "title": f"Bagian {index}",
                "narration": full_narration,
                "visual": (
                    "Raka berjalan melewati jalan desa; "
                    "Raka membantu warga membawa barang; "
                    "Raka berbicara dengan ibunya di rumah"
                ),
                "on_screen_text": "Raka berubah",
            }
            for index in range(1, 7)
        ],
    }
    monkeypatch.setattr(long_animate, "chat_completion", lambda config, messages: json.dumps(payload))

    script, audit = expand_story_outline(
        outline,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
        target_duration=300,
    )

    sections = long_animate._scene_sections(script)
    assert audit["scene_count"] == 6
    assert len(sections) == 6
    assert len(str(sections[1]["narration"]).split()) >= 18
    assert len(str(sections[1]["visual"]).split()) >= 8


def test_directed_story_script_is_not_rewritten(monkeypatch):
    directed = """
    ### ADEGAN 1 — Hook
    VISUAL: Raka berlari menuju alarm.
    NARASI: Alarm berbunyi sebelum semua orang memahami bahayanya.
    ### ADEGAN 2 — Konflik
    VISUAL: Raka membuka panel keamanan.
    NARASI: Ia menemukan kabel yang sengaja diputus oleh penyabot.
    ### ADEGAN 3 — Payoff
    VISUAL: Raka menyalakan kembali sistem gedung.
    NARASI: Keahliannya menyelamatkan semua orang dan membuktikan siapa dirinya.
    """
    monkeypatch.setattr(
        long_animate,
        "chat_completion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("AI must not be called")),
    )

    script, audit = expand_story_outline(
        directed,
        AIConfig(enabled=False, base_url="", model=""),
        target_duration=300,
    )

    assert script == directed
    assert audit["expanded"] is False


def test_approved_directed_storyboard_is_not_rebuilt_by_ai(monkeypatch):
    directed = """
    GAYA VISUAL: cinematic realistic night thriller

    ### ADEGAN 1 — Alarm
    VISUAL: Raka berlari menuju panel alarm di lobi gelap.
    NARASI: Alarm berbunyi sebelum semua orang memahami bahayanya.
    ### ADEGAN 2 — Kabel
    VISUAL: Raka membuka panel dan menemukan kabel utama terputus.
    NARASI: Ia menemukan bukti sabotase di balik panel keamanan.
    ### ADEGAN 3 — Sistem Pulih
    VISUAL: Raka mengunci kabel baru saat lampu gedung kembali menyala.
    NARASI: Keahliannya menyelamatkan gedung dan membuktikan integritasnya.
    """
    monkeypatch.setattr(
        long_animate,
        "chat_completion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Approved storyboard must not be regenerated")
        ),
    )

    storyboard = build_storyboard(
        directed,
        AIConfig(enabled=True, base_url="http://localhost:11434/v1", model="local"),
    )

    assert [scene.title for scene in storyboard.scenes] == ["Alarm", "Kabel", "Sistem Pulih"]
    assert storyboard.scenes[0].narration.startswith("Alarm berbunyi")
    assert "Raka berlari menuju panel alarm" in storyboard.scenes[0].visual_prompt


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


def test_default_unrequested_visual_style_is_cinematic_realistic(monkeypatch):
    monkeypatch.delenv("LONG_ANIMATE_DEFAULT_VISUAL_STYLE", raising=False)

    storyboard = _fallback_storyboard(SCRIPT)

    assert "cinematic realistic" in storyboard.art_bible
    assert "no cartoon" in storyboard.art_bible


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


def test_shot_framing_is_varied_but_reproducible(monkeypatch):
    storyboard = _fallback_storyboard(SCRIPT)
    long_animate.allocate_scene_durations(
        storyboard.scenes,
        [3.0] * len(storyboard.scenes),
        24.0,
    )
    monkeypatch.setenv("LONG_ANIMATE_TRANSITION_SECONDS", "0")

    first = long_animate.plan_storyboard_shots(storyboard)
    second = long_animate.plan_storyboard_shots(storyboard)
    first_plan = [
        (shot.framing, shot.subject_placement, shot.camera_angle)
        for shot in first
    ]
    second_plan = [
        (shot.framing, shot.subject_placement, shot.camera_angle)
        for shot in second
    ]

    assert first_plan == second_plan
    assert len(first_plan) >= 3
    assert all(
        current.framing != following.framing
        for current, following in zip(first, first[1:])
    )
    assert all(
        current.subject_placement != following.subject_placement
        for current, following in zip(first, first[1:])
    )


def test_planned_framing_is_sent_to_image_generation_prompt():
    shot = long_animate.AnimateShot(
        index=1,
        scene_index=1,
        shot_index=1,
        shot_count=1,
        title="Membaca",
        narration="Seorang teknisi membaca hasil pemindai di meja.",
        visual_prompt=long_animate._compose_visual_prompt(
            "Seorang teknisi membaca hasil pemindai di meja",
            "Seorang teknisi membaca hasil pemindai di meja.",
            "cinematic realistic",
            "One recurring technician",
            visual_locked=True,
        ),
        on_screen_text="",
        camera_motion="push_in",
        color_mood="cool blue",
        framing="over_shoulder",
        subject_placement="right_third",
        camera_angle="slightly_low",
    )

    prompt = long_animate._focused_image_generation_prompt(shot)

    assert "over-the-shoulder frame" in prompt
    assert "right third" in prompt
    assert "subtle low-angle camera" in prompt


def test_child_water_scene_never_receives_intimate_close_framing():
    allowed = {"wide", "medium_wide", "medium"}

    for seed in ("one", "two", "three", "four"):
        framing, _placement, _angle = long_animate._plan_shot_framing(
            "Anak kecil mandi dan bermain air di sungai dangkal",
            seed,
        )
        assert framing in allowed


def test_close_up_camera_move_is_gentler_than_wide_camera_move():
    wide = _motion_test_shot()
    wide.framing = "wide"
    close = _motion_test_shot()
    close.framing = "close_up"

    wide_zoom, _wide_x, _wide_y = _motion_expression(wide, 300)
    close_zoom, _close_x, close_y = _motion_expression(close, 300)

    assert "0.100*min(1,on/300)" in wide_zoom
    assert "0.038*min(1,on/300)" in close_zoom
    assert "*0.30" in close_y


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


def test_islamic_tts_repairs_tablig_and_common_pronunciations(monkeypatch):
    original = (
        "Jamaat Tablek belajar fiqih, aqidah, akhlaq, hadist, sholawat, "
        "lalu shalat Ashar setelah adzan Dzuhur."
    )
    monkeypatch.setenv("LONG_ANIMATE_TTS_PROFILE", "islamic_indonesian")

    spoken = long_animate._tts_pronunciation_text(original)

    assert spoken == (
        "Jamaah Tablig belajar fikih, akidah, akhlak, hadis, salawat, "
        "lalu salat asar setelah azan zuhur."
    )
    assert "Tablek" in original


def test_storyboard_repairs_islamic_asr_terms_in_subtitles():
    storyboard = _fallback_storyboard(
        "Narator menjelaskan bahwa Jamaat Tablek berdakwah dengan tertib."
    )

    assert "Jamaah Tablig" in storyboard.scenes[0].narration
    assert "Tablek" not in storyboard.scenes[0].narration


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


def test_generic_repeated_narration_cannot_receive_high_quality_score():
    storyboard = _fallback_storyboard(SCRIPT)
    storyboard.scenes = storyboard.scenes[:5]
    generic = "Pisahkan informasi utama dari pendapat, lihat konteksnya, lalu timbang dampaknya."
    for scene in storyboard.scenes:
        scene.narration = generic

    audit = long_animate.narration_quality_audit(
        storyboard.scenes,
        requested_duration=180.0,
        effective_duration=30.0,
    )

    assert audit["passed"] is False
    assert audit["score"] < 50
    assert audit["unique_scene_narration_ratio"] < 0.9


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


def test_subtitle_style_is_proportional_and_inside_safe_area():
    landscape = long_animate._subtitle_force_style("16:9")
    portrait = long_animate._subtitle_force_style("9:16")

    assert "FontSize=26" in landscape
    assert "MarginL=110" in landscape
    assert "MarginR=110" in landscape
    assert "Outline=2" in landscape
    assert "Shadow=0" in landscape
    assert "FontSize=36" in portrait
    assert "MarginV=110" in portrait


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
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_STRICT", "true")

    try:
        long_animate._remote_scene_image(scene, tmp_path / "scene.jpg")
    except long_animate.LongAnimateImageError as exc:
        assert "API key Gemini" in str(exc)
    else:
        raise AssertionError("strict mode harus menghentikan render tanpa API key")


def test_realistic_story_mode_rejects_procedural_rectangle_fallback(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    monkeypatch.delenv("LONG_ANIMATE_IMAGE_BASE_URL", raising=False)
    monkeypatch.delenv("LONG_ANIMATE_IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LONG_ANIMATE_ALLOW_PROCEDURAL_IMAGES", raising=False)

    try:
        long_animate.generate_scene_image(
            scene,
            tmp_path / "scene.png",
            "cinematic realistic documentary-film still",
        )
    except long_animate.LongAnimateImageError as exc:
        assert "fallback kotak dinonaktifkan" in str(exc)
    else:
        raise AssertionError("Generator Cerita tidak boleh memakai gambar kotak prosedural")


def test_local_real_image_provider_preflight(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[{"id":"z-image-turbo-q3"}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request if isinstance(request, str) else request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)

    long_animate.require_real_image_provider()

    assert captured == {
        "url": "http://127.0.0.1:7860/v1/models",
        "timeout": 8,
    }


def test_local_real_image_provider_waits_for_service_startup(monkeypatch):
    requests = []
    sleeps = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[{"id":"z-image-turbo-q4-k"}]}'

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if len(requests) < 3:
            raise long_animate.urllib.error.URLError(
                ConnectionRefusedError(111, "Connection refused")
            )
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q4-k")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_READY_TIMEOUT_SECONDS", "120")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate.time, "sleep", sleeps.append)

    long_animate.require_real_image_provider()

    assert requests == [
        ("http://127.0.0.1:7860/v1/models", 8),
        ("http://127.0.0.1:7860/v1/models", 8),
        ("http://127.0.0.1:7860/v1/models", 8),
    ]
    assert sleeps == [3.0, 3.0]


def test_local_z_image_uses_sdcpp_images_api_payload(monkeypatch, tmp_path):
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
    assert "verify natural hands and finger count" not in captured["payload"]["prompt"]
    assert "model" not in captured["payload"]
    assert "quality" not in captured["payload"]
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 900
    assert long_animate._remote_provider_label(
        "http://127.0.0.1:7860/v1", "z-image-turbo-q3"
    ) == "local_z_image_turbo"


def test_local_z_image_sends_character_reference_to_edits_endpoint(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    reference = tmp_path / "character-reference.png"
    reference.write_bytes(b"reference-character-pixels")
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
        captured["body"] = request.data
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "1280x720")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "1")
    monkeypatch.setenv("LONG_ANIMATE_LOCAL_REFERENCE_IMAGES", "true")
    monkeypatch.setattr(long_animate, "_release_ollama_gpu_models", lambda: None)
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(
        scene, tmp_path / "scene.png", reference
    ) is True
    body = captured["body"]
    assert captured["url"] == "http://127.0.0.1:7860/v1/images/edits"
    assert captured["headers"]["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="image[]"; filename="character-reference.png"' in body
    assert b"reference-character-pixels" in body
    assert b"REFERENCE IDENTITY LOCK" in body
    assert b'"image_preprocess":"target=ref,mode=none"' in body
    assert b'"ref_image_args":"resize_before_vae=false"' in body


def test_local_reference_edit_falls_back_after_server_crash(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    reference = tmp_path / "character-reference.png"
    reference.write_bytes(b"reference-character-pixels")
    requested_urls = []
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
        requested_urls.append(request.full_url)
        if len(requested_urls) == 1:
            raise long_animate.urllib.error.HTTPError(
                request.full_url, 502, "reference server stopped", {}, io.BytesIO(b"{}")
            )
        assert json.loads(request.data.decode())["prompt"].startswith("FULL-BLEED")
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "2")
    monkeypatch.setenv("LONG_ANIMATE_LOCAL_REFERENCE_IMAGES", "true")
    monkeypatch.setattr(long_animate, "_release_ollama_gpu_models", lambda: None)
    monkeypatch.setattr(long_animate.time, "sleep", sleeps.append)
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    assert long_animate._remote_scene_image(
        scene, tmp_path / "scene.png", reference
    ) is True
    assert requested_urls == [
        "http://127.0.0.1:7860/v1/images/edits",
        "http://127.0.0.1:7860/v1/images/generations",
    ]
    assert sleeps == [6.0]


def test_local_image_502_waits_for_recovery_without_online_fallback(monkeypatch, tmp_path):
    scene = _fallback_storyboard(SCRIPT).scenes[0]
    requests = []
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
        payload = json.loads(request.data.decode())
        requests.append(
            {
                "url": request.full_url,
                "payload": payload,
                "headers": dict(request.header_items()),
                "timeout": timeout,
            }
        )
        if len(requests) < 3:
            raise long_animate.urllib.error.HTTPError(
                request.full_url,
                502,
                "Bad Gateway",
                {},
                io.BytesIO(b'{"error":{"message":"local generator stopped"}}'),
            )
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_IMAGE_PROVIDER", "stable-diffusion-cpp")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_BASE_URL", "http://127.0.0.1:7860/v1")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_MODEL", "z-image-turbo-q3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_SIZE", "1024x576")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_RETRIES", "3")
    monkeypatch.setenv("LONG_ANIMATE_IMAGE_STRICT", "true")
    monkeypatch.setattr(long_animate, "_release_ollama_gpu_models", lambda: None)
    monkeypatch.setattr(long_animate.time, "sleep", sleeps.append)
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(long_animate, "_normalize_scene_image", lambda path: True)

    provider = long_animate.generate_scene_image(
        scene,
        tmp_path / "scene.png",
        "cinematic realistic documentary-film still",
    )

    assert provider == "local_z_image_turbo"
    assert len(requests) == 3
    assert {request["url"] for request in requests} == {
        "http://127.0.0.1:7860/v1/images/generations"
    }
    assert [request["payload"]["size"] for request in requests] == [
        "1024x576",
        "768x432",
        "768x432",
    ]
    assert all("Authorization" not in request["headers"] for request in requests)
    assert sleeps == [6.0, 12.0]


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


def _motion_test_shot() -> long_animate.AnimateShot:
    return long_animate.AnimateShot(
        index=1,
        scene_index=1,
        shot_index=1,
        shot_count=1,
        title="Jalan desa",
        narration="Seorang anak berlari di jalan desa.",
        visual_prompt="A child runs on a rural village road at sunset",
        on_screen_text="",
        camera_motion="pan_right",
        color_mood="warm",
        animation_direction="The child runs forward while clothes move in the wind",
        duration=7.2,
    )


def test_requested_school_assembly_allows_natural_background_faces(monkeypatch):
    shot = _motion_test_shot()
    shot.narration = "Saat upacara, seorang anak berdiri di barisan bersama murid-murid sekolah."
    image = long_animate.np.random.default_rng(7).integers(
        0, 256, size=(720, 1280, 3), dtype=long_animate.np.uint8
    )
    monkeypatch.setattr(long_animate.cv2, "imread", lambda _path: image)
    monkeypatch.setattr(long_animate, "_face_boxes", lambda _image: [(0, 0, 30, 30)] * 12)

    _score, reasons = long_animate.inspect_generated_image(shot, Path("assembly.png"))

    assert "too_many_visible_faces" not in reasons
    assert long_animate._requests_group_scene(shot.narration) is True


def test_explicit_single_character_still_flags_unrequested_extra_faces(monkeypatch):
    shot = _motion_test_shot()
    image = long_animate.np.random.default_rng(8).integers(
        0, 256, size=(720, 1280, 3), dtype=long_animate.np.uint8
    )
    monkeypatch.setattr(long_animate.cv2, "imread", lambda _path: image)
    monkeypatch.setattr(long_animate, "_face_boxes", lambda _image: [(0, 0, 30, 30)] * 3)

    _score, reasons = long_animate.inspect_generated_image(shot, Path("single-child.png"))

    assert "too_many_visible_faces" in reasons


def test_single_character_requires_a_large_sharp_readable_face(monkeypatch):
    shot = _motion_test_shot()
    image = long_animate.np.random.default_rng(9).integers(
        0, 256, size=(720, 1280, 3), dtype=long_animate.np.uint8
    )
    monkeypatch.setattr(long_animate.cv2, "imread", lambda _path: image)
    monkeypatch.setattr(long_animate, "_face_boxes", lambda _image: [])

    _score, reasons = long_animate.inspect_generated_image(shot, Path("missing-face.png"))

    assert "missing_clear_face" in reasons


def test_tower_crane_qa_does_not_expect_a_person_from_capitalization(monkeypatch):
    shot = _motion_test_shot()
    shot.narration = "Tower crane bergerak mengangkat material konstruksi."
    shot.visual_prompt = long_animate._compose_visual_prompt(
        shot.narration,
        shot.narration,
        "cinematic realistic architecture",
        "No recurring character is defined",
        visual_locked=True,
    )
    image = long_animate.np.random.default_rng(10).integers(
        0, 256, size=(720, 1280, 3), dtype=long_animate.np.uint8
    )
    monkeypatch.setattr(long_animate.cv2, "imread", lambda _path: image)
    monkeypatch.setattr(long_animate, "_face_boxes", lambda _image: [])

    _score, reasons = long_animate.inspect_generated_image(shot, Path("tower.png"))

    assert "missing_clear_face" not in reasons


def test_strict_vision_qa_rejects_persistent_extra_people(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    original_prompt = shot.visual_prompt
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "2")
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_STRICT", "true")
    monkeypatch.setattr(long_animate, "generate_scene_image", lambda *_args, **_kwargs: "local-z-image")
    monkeypatch.setattr(
        long_animate,
        "inspect_generated_image",
        lambda *_args, **_kwargs: (0.65, ["too_many_visible_faces"]),
    )

    try:
        long_animate.generate_shot_image_with_qa(
            shot, tmp_path / "shot.png", "photorealistic documentary"
        )
    except long_animate.LongAnimateImageError as exc:
        assert "too_many_visible_faces" in str(exc)
    else:
        raise AssertionError("strict QA must reject a crowd in a one-person shot")
    assert shot.qa_attempts == 2
    assert shot.visual_prompt == original_prompt


def test_strict_vision_qa_rejects_undecodable_image(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "1")
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_STRICT", "true")
    monkeypatch.setattr(long_animate, "generate_scene_image", lambda *_args, **_kwargs: "local-z-image")
    monkeypatch.setattr(
        long_animate,
        "inspect_generated_image",
        lambda *_args, **_kwargs: (0.0, ["image_decode_failed"]),
    )

    try:
        long_animate.generate_shot_image_with_qa(
            shot, tmp_path / "broken.png", "photorealistic documentary"
        )
    except long_animate.LongAnimateImageError as exc:
        assert "image_decode_failed" in str(exc)
    else:
        raise AssertionError("strict QA must still reject an undecodable image")


def test_non_strict_vision_qa_still_rejects_undecodable_image(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "1")
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_STRICT", "false")
    monkeypatch.setattr(long_animate, "generate_scene_image", lambda *_args, **_kwargs: "local-z-image")
    monkeypatch.setattr(
        long_animate,
        "inspect_generated_image",
        lambda *_args, **_kwargs: (0.0, ["image_decode_failed"]),
    )

    try:
        long_animate.generate_shot_image_with_qa(
            shot, tmp_path / "broken.png", "photorealistic documentary"
        )
    except long_animate.LongAnimateImageError as exc:
        assert "image_decode_failed" in str(exc)
    else:
        raise AssertionError("an undecodable image must remain fatal in non-strict mode")


def test_non_strict_vision_qa_restores_best_candidate_and_continues(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    path = tmp_path / "shot.png"
    attempts = {"count": 0}
    results = iter(
        [
            (0.82, ["too_many_visible_faces"]),
            (0.41, ["missing_clear_face", "soft_face_detail"]),
            (0.63, ["face_too_small"]),
        ]
    )

    def fake_generate(current_shot, current_path, _art_bible, reference_image=None):
        attempts["count"] += 1
        current_path.write_bytes(f"candidate-{attempts['count']}".encode())
        if attempts["count"] > 1:
            focused = long_animate._focused_image_generation_prompt(current_shot)
            assert "QA repair requirement" in focused
        return "local-z-image"

    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "3")
    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_STRICT", "false")
    monkeypatch.setattr(long_animate, "generate_scene_image", fake_generate)
    monkeypatch.setattr(long_animate, "inspect_generated_image", lambda *_args, **_kwargs: next(results))

    provider = long_animate.generate_shot_image_with_qa(
        shot,
        path,
        "photorealistic documentary",
    )

    assert provider == "local-z-image"
    assert path.read_bytes() == b"candidate-1"
    assert shot.qa_attempts == 3
    assert shot.qa_score == 0.82
    assert shot.qa_reasons == ["too_many_visible_faces"]
    assert not list(tmp_path.glob("*.qa-best.png"))


def test_failed_long_render_preserves_partial_assets_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("LONG_ANIMATE_CLEANUP_ON_ERROR", raising=False)
    partial_path = None

    try:
        with long_animate.animate_work_directory(tmp_path, "Judul cerita") as (work_dir, _clips, scene_dir):
            partial_path = scene_dir / "shot_01.png"
            partial_path.write_bytes(b"partial-image")
            raise RuntimeError("simulated render failure")
    except RuntimeError:
        pass

    assert partial_path is not None
    assert partial_path.read_bytes() == b"partial-image"
    assert work_dir.is_dir()


def test_object_only_shot_never_receives_human_character_reference(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    shot.narration = "Tower crane bergerak mengangkat material konstruksi."
    shot.visual_prompt = long_animate._compose_visual_prompt(
        shot.narration,
        shot.narration,
        "cinematic realistic architecture",
        "No recurring character is defined",
        visual_locked=True,
    )
    reference = tmp_path / "human-reference.png"
    reference.write_bytes(b"human")
    received_references = []

    def fake_generate(_shot, path, _art_bible, reference_image=None):
        received_references.append(reference_image)
        path.write_bytes(b"generated")
        return "local-z-image"

    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "1")
    monkeypatch.setattr(long_animate, "generate_scene_image", fake_generate)
    monkeypatch.setattr(
        long_animate, "inspect_generated_image", lambda *_args, **_kwargs: (1.0, [])
    )

    long_animate.generate_shot_image_with_qa(
        shot,
        tmp_path / "tower.png",
        "cinematic realistic architecture",
        character_reference=reference,
    )

    assert received_references == [None]


def test_single_character_shot_receives_character_reference(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    reference = tmp_path / "character-reference.png"
    reference.write_bytes(b"character")
    received_references = []

    def fake_generate(_shot, path, _art_bible, reference_image=None):
        received_references.append(reference_image)
        path.write_bytes(b"generated")
        return "local-z-image"

    monkeypatch.setenv("LONG_ANIMATE_VISION_QA_ATTEMPTS", "1")
    monkeypatch.setattr(long_animate, "generate_scene_image", fake_generate)
    monkeypatch.setattr(
        long_animate, "inspect_generated_image", lambda *_args, **_kwargs: (1.0, [])
    )

    long_animate.generate_shot_image_with_qa(
        shot,
        tmp_path / "child.png",
        "cinematic realistic documentary",
        character_reference=reference,
    )

    assert received_references == [reference]


def test_motion_provider_preflight_rejects_paid_muapi(monkeypatch):
    monkeypatch.setenv("LONG_ANIMATE_VIDEO_PROVIDER", "muapi")

    try:
        long_animate.require_motion_video_provider()
    except long_animate.LongAnimateVideoError as exc:
        assert "tidak ada API berbayar" in str(exc)
    else:
        raise AssertionError("adapter video berbayar tidak boleh aktif")


def test_wikimedia_free_video_search_preserves_license_metadata(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps(
                {
                    "query": {
                        "pages": [
                            {
                                "pageid": 123,
                                "title": "File:Village road.webm",
                                "imageinfo": [
                                    {
                                        "url": "https://upload.wikimedia.org/free/village-road.webm",
                                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Village_road.webm",
                                        "size": 4_000_000,
                                        "width": 1920,
                                        "height": 1080,
                                        "mime": "video/webm",
                                        "extmetadata": {
                                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                            "LicenseUrl": {
                                                "value": "https://creativecommons.org/licenses/by-sa/4.0/"
                                            },
                                            "Artist": {"value": "<b>Example Creator</b>"},
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("LONG_ANIMATE_FREE_STOCK_LICENSES", "cc0,public domain,cc by-sa")
    monkeypatch.setattr(long_animate.urllib.request, "urlopen", fake_urlopen)

    results = long_animate._wikimedia_video_results(_motion_test_shot())

    assert len(results) == 1
    assert results[0]["license"] == "CC BY-SA 4.0"
    assert results[0]["creator"] == "Example Creator"
    assert results[0]["download_url"].startswith("https://upload.wikimedia.org/")
    assert "filetype%3Avideo" in captured["url"]
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 30.0


def test_local_free_motion_downloads_commons_and_records_credit(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    source = {
        "download_url": "https://upload.wikimedia.org/free/village.webm",
        "source_page": "https://commons.wikimedia.org/wiki/File:Village.webm",
        "creator": "Free Creator",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "width": 1920,
        "height": 1080,
        "size": 4_000_000,
    }

    def fake_download(_url, output):
        output.write_bytes(b"free-video" * 200)

    monkeypatch.setenv("LONG_ANIMATE_VIDEO_PROVIDER", "local_free")
    monkeypatch.setenv("LONG_ANIMATE_FREE_STOCK_ENABLED", "true")
    monkeypatch.setenv("LONG_ANIMATE_FREE_STOCK_MAX_SHOTS", "4")
    monkeypatch.setattr(long_animate, "_wikimedia_video_results", lambda _shot: [source])
    monkeypatch.setattr(long_animate, "_download_free_stock_video", fake_download)
    monkeypatch.setattr(long_animate, "_media_duration", lambda _path: 8.0)

    output = long_animate.generate_motion_video(shot, tmp_path / "shot.png", tmp_path)

    assert output == tmp_path / "shot_01.free-source-1.webm"
    assert shot.motion_provider == "free_stock:wikimedia_commons"
    assert shot.motion_creator == "Free Creator"
    assert shot.motion_license == "CC BY 4.0"
    assert shot.motion_source_page.endswith("File:Village.webm")


def test_free_motion_falls_back_to_local_z_image_without_network_result(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    monkeypatch.setenv("LONG_ANIMATE_VIDEO_PROVIDER", "local_free")
    monkeypatch.setenv("LONG_ANIMATE_FREE_STOCK_ENABLED", "true")
    monkeypatch.setattr(long_animate, "_wikimedia_video_results", lambda _shot: [])

    assert long_animate.generate_motion_video(shot, tmp_path / "shot.png", tmp_path) is None
    assert shot.motion_provider == "local_z_image_cinematic"


def test_disabled_motion_provider_uses_local_frame_without_network(monkeypatch, tmp_path):
    shot = _motion_test_shot()
    monkeypatch.setenv("LONG_ANIMATE_VIDEO_PROVIDER", "off")
    monkeypatch.setattr(
        long_animate.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )

    assert long_animate.generate_motion_video(shot, tmp_path / "shot.png", tmp_path) is None
    assert shot.motion_provider == "local_z_image_cinematic"
