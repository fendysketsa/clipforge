# Investigasi quality workflow (27 Nov 2026)

## Temuan

Dua kegagalan berurutan di workflow `quality` job `backend`:

1. `httpx` tidak tercantum di `backend/requirements.txt`, sehingga
   `starlette.testclient` gagal saat koleksi 6 tes Facebook. Sudah ditambahkan
   `httpx==0.28.1`.
2. `tests/test_long_animate.py::test_story_audio_uses_verified_mood_music_and_semantic_effects`
   bergantung pada file CC0 yang diunduh lokal saat setup dan tidak ikut ter-commit.
   Tes sekarang memakai library fixture sementara dengan sha256 terverifikasi.

## Verifikasi lokal

Reproduksi checkout CI memakai `git archive HEAD` ke direktori bersih dan venv
baru yang diinstall dari `backend/requirements.txt`:

- `3595 passed, 1 skipped` (sesudah perbaikan fixture)
- `frontend`: typecheck, seluruh `tests/*.mjs`, build, dan
  `deployment-health.cjs build` lolos

## Catatan

Job GitHub Actions gagal dengan `exit code 1` tanpa annotation yang menyebut tes.
Log penuh tidak dapat diambil tanpa izin admin repository. Commit ini sengaja
ditambahkan untuk memicu ulang CI dan memastikan perbaikan benar-benar hijau.
