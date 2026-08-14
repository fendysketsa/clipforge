import base64
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
    assert all("no text" in scene.visual_prompt for scene in storyboard.scenes)
    assert len({scene.narration for scene in storyboard.scenes}) == len(storyboard.scenes)


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
    assert [scene.camera_motion for scene in storyboard.scenes] == [
        "push_in",
        "pan_right",
        "drift_up",
        "pull_out",
    ]
    assert storyboard.scenes[-1].narrative_role == "payoff_conclusion"
    assert all("no public figure" in scene.visual_prompt for scene in storyboard.scenes)


def test_motion_expression_varies_direction_without_static_slideshow():
    storyboard = _fallback_storyboard(SCRIPT)
    scene = storyboard.scenes[0]
    scene.camera_motion = "pan_right"

    zoom, x, y = _motion_expression(scene, 300)

    assert "on/300" in zoom
    assert "on/300" in x
    assert "iw-iw/zoom" in x
    assert "ih-ih/zoom" in y


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

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.jpg") is True
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

    assert long_animate._remote_scene_image(scene, tmp_path / "scene.jpg") is True
    assert captured["url"] == "http://127.0.0.1:7860/v1/images/generations"
    assert captured["payload"]["size"] == "1024x576"
    assert captured["payload"]["output_format"] == "jpeg"
    assert "model" not in captured["payload"]
    assert "quality" not in captured["payload"]
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 900
    assert long_animate._remote_provider_label(
        "http://127.0.0.1:7860/v1", "z-image-turbo-q3"
    ) == "local_z_image_turbo"
