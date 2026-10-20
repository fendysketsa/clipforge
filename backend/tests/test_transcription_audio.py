import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

import clipper
from clipper import (
    UserFacingError,
    cached_whisper_model_path,
    load_transcription_audio,
    transcribe,
    whisper_runtime_candidates,
)


def write_pcm_wav(path, samples, *, channels=1, sample_rate=16000, sample_width=2):
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(sample_rate)
        target.writeframes(np.asarray(samples, dtype="<i2").tobytes())


def test_load_transcription_audio_returns_normalized_float32(tmp_path):
    audio_path = tmp_path / "audio.wav"
    write_pcm_wav(audio_path, [-32768, -16384, 0, 16384, 32767])

    samples = load_transcription_audio(audio_path)

    assert samples.dtype == np.float32
    assert samples.tolist() == pytest.approx([-1.0, -0.5, 0.0, 0.5, 32767 / 32768])


def test_load_transcription_audio_rejects_noncanonical_wav(tmp_path):
    audio_path = tmp_path / "stereo.wav"
    write_pcm_wav(audio_path, [0, 0], channels=2)

    with pytest.raises(UserFacingError, match="PCM mono 16 kHz 16-bit"):
        load_transcription_audio(audio_path)


def test_transcribe_passes_waveform_instead_of_path_to_faster_whisper(monkeypatch, tmp_path):
    audio_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "transcript.json"
    write_pcm_wav(audio_path, [0, 1000, -1000, 0])
    captured = {}

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            captured["model_name"] = model_name
            captured["model_options"] = kwargs

        def transcribe(self, audio, **kwargs):
            captured["audio"] = audio
            captured["decode_options"] = kwargs
            return [], types.SimpleNamespace(language="id")

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(clipper, "whisper_runtime_candidates", lambda: [("cpu", "int8")])

    rows = transcribe(audio_path, transcript_path, "test-model", "id", force=True)

    assert rows == []
    assert isinstance(captured["audio"], np.ndarray)
    assert captured["audio"].dtype == np.float32
    assert captured["audio"].tolist() == pytest.approx([0, 1000 / 32768, -1000 / 32768, 0])
    assert captured["model_name"] == "test-model"
    assert captured["decode_options"]["language"] == "id"
    assert transcript_path.exists()


def test_cached_whisper_model_path_resolves_complete_main_snapshot(monkeypatch, tmp_path):
    hub = tmp_path / "hub"
    model_cache = hub / "models--Systran--faster-whisper-medium"
    snapshot = model_cache / "snapshots" / "revision-1"
    snapshot.mkdir(parents=True)
    (model_cache / "refs").mkdir()
    (model_cache / "refs" / "main").write_text("revision-1\n", encoding="utf-8")
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.bin").write_bytes(b"ready" * 300)
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))

    assert cached_whisper_model_path("Systran/faster-whisper-medium") == snapshot


def test_whisper_runtime_prefers_cuda_and_keeps_cpu_fallback(monkeypatch):
    fake_ctranslate2 = types.ModuleType("ctranslate2")
    fake_ctranslate2.get_cuda_device_count = lambda: 1
    monkeypatch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)
    monkeypatch.setenv("FENDY_CLIPPER_WHISPER_DEVICE", "auto")

    assert whisper_runtime_candidates() == [("cuda", "float16"), ("cpu", "int8")]


def test_requirements_keep_pyav_below_removed_metadata_errors_api():
    requirements = (Path(__file__).parents[1] / "requirements.txt").read_text(encoding="utf-8")

    assert "av>=11,<19" in requirements
    assert "nvidia-cublas-cu12" in requirements
    assert "nvidia-cudnn-cu12" in requirements
