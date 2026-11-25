# Tiga aksen hidup opsional untuk Shorts (25 Nov 2026)

## Keputusan

Menambah tiga aksen visual baru sebagai **lapisan opsinal** untuk render cron
Shorts. Jalur render yang sudah berjalan tidak diubah: flag default mati di
Compose, job manual tidak pernah menerima flag, dan aksen baru tidak menggantikan
`cron_director_effects`, motion inserts, cinematic pass, atau watermark.

Ketiga aksen (prosedural, tanpa aset pihak ketiga):

1. `beat_pulse` — cincin luas singkat pada kata reaksi yang benar-benar ada di
   transkrip berseluruh waktu.
2. `comet_streak` — garis cahaya pendek pada kata aksi berseluruh waktu.
3. `edge_glow` — cahaya lembut di payoff/hasil yang memang diucapkan.

## Batas

- Maksimal dua aksen per klip, masing-masing harus cocok dengan segmen dialog
  berseluruh waktu di dalam klip.
- Konteks sensitif, layout evidence/social-card/reaction-avatar/multi-split,
  dan klip pendek dilewati tanpa efek.
- Tidak menambah atau memindahkan waktu sumber, audio, subtitle, atau durasi.
- Kegagalan renderer opsional dicatat di plan dan ekspor utama tetap selesai.
- Render diverifikasi: duration, frame count, dan geometri harus sama persis;
  audio disalin (`-c:a copy`).

## Perubahan

- `backend/clip_liveliness.py` (baru): `build_plan`, `accent_frame`,
  `render_overlays`, `POLICY_VERSION=1`.
- `backend/clipper.py`: import dan satu blok pemanggilan yang hanya jalan saat
  `SHORTS_SCHEDULED_LIVELINESS_ACCENTS_ENABLED=true`.
- `backend/api.py`: meneruskan flag hanya untuk job cron yang sudah memiliki
  `scheduled_director_effects`.
- `docker-compose.yml`, `.env`, `.env.example`: variabel
  `AUTO_VIRAL_SCHEDULED_LIVELINESS_ACCENTS_ENABLED`. Compose default `false`;
  `.env` lokal di-set `true` sesuai permintaan.
- Tes: `backend/tests/test_clip_liveliness.py` (12 tes) dan satu tes isolasi
  worker di `backend/tests/test_api_budget.py`.

## Validasi

- 12 tes aksen baru lulus, termasuk render MP4 sintetis 1080x1920 dengan
  audio hash, duration, frame count, dan geometri identik.
- 90 tes terarah lulus (liveliness, worker isolation, deployment guard,
  Compose deployment), serta 370 tes caption/cron/render/selection lulus.
- `py_compile`, `git diff --check`, dan `docker-compose config --quiet` lulus.
- Hash source baru yang diharapkan setelah rebuild:
  `c1af535c8c6cc1a3358722ea837af3e044c07ecf8de09d455263893cb382a809`.

## Aktivasi

Status: **belum aktif**. Sesi ini tidak memiliki sudo interaktif dan socket
Docker tidak dapat diakses, jadi perubahan belum berjalan di produksi. Setelah
pekerjaan aktif selesai, jalankan perintah standar repositori:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Verifikasi setelah perintah tersebut (bukan sekadar build):

- `/api/health` mengembalikan `ok`;
- release id backend dan telegram-bot sama dengan hash source di atas;
- `/api/automation/viral-cc/schedule` tetap menunjukkan
  `cron_director_effects_required=true`, `cron_director_effects_policy_version=4`,
  `enabled=true`, `scheduler_running=true`;
- sidecar render cron baru memuat `clip_liveliness.rendered=true` dengan
  `verification=duration_frame_count_and_geometry_preserved`.

Perilaku lama tetap dipertahankan: pengaturan operator, publication hold,
identitas upload, dan video lama tidak diubah atau di-upload ulang.
