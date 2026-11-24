# Facebook cron: dari kartu teks ke adegan karakter — 24 November 2026

## Penyebab

Produksi Facebook di-set ke seri `topik`, sehingga jalur cron memakai `facebook_stories.plan()`
→ `plan['story']` → **`motlab/story-scene.mjs`**. Renderer itu hanya menggambar kartu,
ikon, label, caption, dan batang fase — **tidak punya kode menggambar orang sama sekali**.
Satu-satunya renderer Motlab dengan karakter (`education-scene.mjs`, Nara/Bimo) hanya dipilih
jika `plan['education']` ada, yaitu untuk seri edukasi — bukan `topik`.

Jadi topik seperti "anak tersedak saat minum es" jadi papan + tulisan, bukan orang minum dan tersedak.

## Perbaikan

1. **`facebook_stories.py`**
   - `SCENE_HINTS` + `infer_scene()` memilih adegan dari topik secara deterministik
     (`tersedak/minum/es` → `drink_choking`, serta berbagi, minta maaf, menolong, antre,
     merapikan, mendengarkan, terima kasih, menyapa, jujur, PR, dan fallback sehari-hari).
   - `story.scene` dan `story.scene` pada frame `scene()`, plus `stage_starts` dari narasi
     terukur — clock tetap berasal dari TTS yang diukur, bukan angka rekaan.
   - Hanya gaya `moral_anak` yang memakai adegan karakter; gaya lain tetap kartu (kompatibel).

2. **`motlab/story-scene.mjs`**
   - `person()` dengan pose `curious / hold / drink / cough / calm / help`,
     Napas/bob, kedip, mulut batuk, tangan ke dada, tanda gerak.
   - `glass()` berisi air + es, dimiringkan ke mulut saat minum, diletakkan saat batuk.
   - `personScene()` menggambar latar, meja, dua tokoh, catatan moral, dan empat batang fase.
   - Jalur kartu lama tetap utuh untuk `scene === 'cards' | 'steps'`.

3. **`facebook_originals.py`**
   - Sidecar `story_motion.component = 'character_led_story'` bila ada adegan karakter.
   - Audit memverifikasi `scene` di sidecar sama dengan rencana; tidak ada kelulusan otomatis baru.

## Yang tidak berubah

QC independen, confidence ≥ 0.8, `automatic_pass()`, publication hold, batas 55 detik,
identitas remote, dan `@motlab/cli` 0.3.0. Tidak ada narasi, angka penonton, atau bukti QC yang dibuat-buat.

## Verifikasi

- Screenshot render Motlab langsung: tokoh mengangkat gelas, lalu batuk (mulut terbuka,
  tangan ke dada, tanda gerak), lalu tokoh kedua menolong dan ceklis.
- `node --check motlab/story-scene.mjs` lolos.
- Pengujian Facebook/Motlab/education/cron-long terfokus lolos.
- Hasil suite penuh mengikuti sesi deployment.
