# Audit kode lanjutan — 24 November 2026

Tindak lanjut dari laporan `ai-office-autonomy-20261124`, `ai-office-control-20261124`, dan
`facebook-terminal-disposal-20261124`. Fokus: source verification, regresi suite penuh, dan
logika modul pemulihan yang baru ditambahkan.

## Temuan dan perbaikan

1. **Source verification tidak mencakup `motlab/story-scene.mjs`.** File ini dipakai saat build
   (`node --check` di Dockerfile) dan saat render cerita (`facebook_motlab.py`, `facebook-scene.mjs`),
   tetapi tidak masuk fingerprint `deployment_runtime.source_files()`. Perubahan pada renderer Story
   tidak membatalkan image. Diperbaiki: file ditambahkan ke fingerprint, ke pemeriksaan
   `node --check` saat startup, dan ke fixture/asertasi `test_compose_deployment.py`.

2. **Bug blocker: `stories.choose_topic()` menerima `set` sebagai `recent_styles`.**
   `facebook_stories.py:181` melakukan `recent_styles[-3:]`, sehingga `set` memicu
   `TypeError: 'set' object is not subscriptable`. Dua pemanggil di `facebook_runner.py`
   (permintaan manual `series=topik` dan jalur cron/tick) mengirim `set`. Akibatnya produksi
   topik otomatis tidak pernah berjalan (exception ditelan `loop()`), dan endpoint
   `/api/facebook/originals` mengembalikan 500 untuk permintaan `topik` tanpa topik eksplisit.
   Diperbaiki dengan mengirim daftar urut. Tes regresi ditambahkan.

3. **Story yang dilewati tetap memblokir produksi Story baru.** `facebook_runner.tick()` menandai
   `story_blocked` dari pesan "audiens publik story belum terbukti", tetapi tidak mengecualikan
   baris dengan `recovery_status == 'skipped'`. Karena jalur skip sengaja mempertahankan pesan dan
   `upload_confirmed=False`, satu Story lama yang sudah terminal memblokir semua slot Story berikutnya
   selama probe audiens gagal. Diperbaiki dengan filter `recovery_status != 'skipped'`, selaras dengan
   `facebook_api.office_snapshot()`. Tes regresi ditambahkan.

4. **Lima fixture tes usang menyebabkan 13 kegagalan pada suite penuh** (3 regresi dari perubahan API
   task sebelumnya, 2 sudah ada di HEAD): mock `request_original` dengan tanda tangan lama,
   `SimpleNamespace` tanpa `attention_archived_at`, asertasi keys `office_snapshot` yang tidak
   mencakup field baru, daftar modul `cron_long_strategy` yang hilang, dan teks/statusHistory yang
   sudah berubah. Semua diperbarui; tidak ada perubahan perilaku produksi yang dibuat hanya untuk
   menyenangkan tes.

## Verifikasi

- 150 tes backend terfokus lolos (deployment, Kantor AI, pemulihan, cleanup).
- 28 tes backend untuk modul pemulihan + regresi Story lolos.
- `npm run typecheck` lolos; 13 berkas tes Node frontend lolos (94 asersi, 0 gagal).
- Suite backend penuh dijalankan ulang: **3392 lolos, 0 gagal** (sebelumnya 3376 lolos, 13 gagal).
  Detail di `suite-rerun.json`.

## Status produksi

Saat audit dimulai, backend produksi sudah memuat `control_version: 2` dan
`autonomous_recovery_version: 1`, tetapi masih **`terminal_cleanup_version: null`**. Pemeriksaan
kontrak lokal `backend_contract()` gagal hanya pada field tersebut, membuktikan image produksi
lebih lama dari source.

Operator kemudian menjalankan ulang perintah deployment standar. Verifikasi setelah rebuild
(`deployment-verification.json`):

- Backend `/api/health` → `ok`.
- `deployment_runtime.backend_contract()` terhadap backend produksi → **lolos** (sebelumnya gagal).
- Facebook: `autonomous_recovery_version: 1`, `terminal_cleanup_version: 1`,
  `story_catalogue_version: 1`, `max_seconds: 55`.
- AI Office: `version: 1`, `control_version: 2`, worker berjalan.
- Container backend/telegram-bot/frontend dimulai 14:06, setelah perubahan source terakhir 14:01,
  sehingga image produksi memuat perbaikan audit ini.
- Frontend menyajikan `deployment.json` dengan `ui_verified: true` dan build_id aktif.

Tidak ada publikasi, perubahan pengaturan operator, atau penghapusan state yang dilakukan selama audit
dan verifikasi.
