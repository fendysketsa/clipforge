# Referensi kortix-ai/CompanyOS untuk Kantor AI — 24 November 2026

## Sumber yang diperiksa

- Repository: `kortix-ai/CompanyOS` (default branch `dev`, tree `47b101f0…`), 20.8k stars, TypeScript.
- Dibaca: `README.md`, `.agents/skills/learnings/SKILL.md`, `packages/starter/templates/base/kortix.yaml`,
  serta struktur `.agents/skills/` dan `packages/ui/src/{internal,session}/outcomes/`.

## Inti CompanyOS

CompanyOS adalah "company as code": agen, skill, pemicu, konektor, dan aturan hidup dalam satu repo.
Model operasinya:

```
Outcome → Plan → Work → Verify → Learn → (run berikutnya mulai dari learn)
```

- **My Kortix** adalah satu agen yang merutekan tugas ke agen spesialis tanpa memblokir percakapan.
- **Triggers** (jadwal, webhook, event) menyalakan agen; filter di kode membuang noise sebelum model jalan.
- **Skills** adalah playbook bersama berbentuk file di git; tiap agen diberi grant.
- **Learnings** adalah ledger episodik append-only: satu entri per insiden, berisi
  **Rule / Trigger surface / Incident / Enforcement**, dengan `MEMORY.md` sebagai index yang di-generate
  dan gate `--check` yang gagal bila index melenceng.
- Perubahan yang masuk `main` lewat change request yang disetujui manusia.

## Pemetaan ke codebase ini

| CompanyOS | Clipforge | Status |
|---|---|---|
| My Kortix (router) | `Pimpinan Digital` (`ai_office_director.py`, `model='digital_leader'`) | sudah ada |
| Skills sebagai playbook git | 11 skill `/yt-*` (`yt_skills.py`) + grant di 6 arahan | sudah ada |
| Triggers / scheduler | tick koordinator 30 detik + insiden + cron Facebook/YouTube | sudah ada |
| Agen/sesi | worker pemilik (cron, upload, attention, Facebook) | sudah ada, sengaja satu owner |
| Verify (verifier terpisah) | QC independen + `yt-audit` (hanya membaca bukti) | sudah ada |
| Change request + approval | publication hold, `PASS_UPLOAD`, setelan operator | sudah ada |
| **Learn (ledger episodik)** | **`ai_office_learning.py`** | **baru diterapkan** |
| Komputer cloud per sesi | tidak dipakai; satu stack Docker | sengaja tidak diadopsi |
| Webhook/MCP/3000+ konektor | tidak dipakai; browser per platform | di luar cakupan |
| RBAC multi-tenant | tidak dipakai; operator tunggal | di luar cakupan |

## Yang baru diterapkan: episodic learning ledger

`backend/ai_office_learning.py` mengikuti pola skill `learnings` CompanyOS:

- Entri append-only `entries/<UTC>-<slug>.md` dengan empat bagian wajib: **Rule**, **Trigger surface**,
  **Incident**, **Enforcement** (gate pengujian yang akan merah bila aturan dilanggar).
- `MEMORY.md` di-generate dari entri; `check()` mendeteksi drift index dan dipakai readiness deployment.
- `POST /api/ai-office/learning` mencatat aturan baru secara validasi; `GET /api/ai-office/learning`
  menampilkan ringkasan. Tidak ada entri yang bisa diubah setelah masuk (append-only).
- Tujuh entri awal bersumber dari insiden nyata di repo ini: `choose_topic` menerima `set`,
  Story skipped memblokir slot baru, `story-scene.mjs` lolos dari manifest, cooldown memegang giliran
  browser, fixture usang, direktur tanpa owner paralel, dan skill yang tidak boleh mengarang bukti QC.
- Data disimpan di `backend/data/ai-office-learnings/` sehingga selamat dari rebuild.

## AI Office 3D (tampilan)

Berdasarkan pola dashboard kantor agen modern (konten bergerak, status spatial, agen berpindah ruang),
Komponen baru `OfficeLivingFloor.tsx` (dipanggil `Office3DFloor`) menggantikan panel direktur statis:

- Enam ruangan (Produksi, QC, Distribusi, Pemulihan, Kebersihan, Facebook) dengan meja dan monitor menyala.
- Enam agen bergerak antar posisi saat status berubah (CSS transition + animasi jalan), mengetik saat bekerja,
  melambaikan tangan saat menunggu keputusan, dan redup saat dinonaktifkan.
- Status ditampilkan tiga cara sekaligus: animasi tubuh, ikon di atas kepala, dan cincin berwarna di bawah kaki.
- Jalur konveyor dengan paket kerja berjalan dari Produksi ke Distribusi saat ada aktivitas.
- Pod Pimpinan Digital, mode malam sesuai waktu WIB, dan kontrol jeda/reduced-motion yang sudah ada.

Referensi yang dipakai: pola "agents walk between rooms", monitor glow, dan status ring dari dashboard
agen isometric/2D kontemporer. Tidak ada canvas berat atau dependensi baru; semuanya SVG + CSS.

## Yang sengaja tidak diadopsi

Kortix menjalankan banyak sesi terisolasi dengan komputer cloud dan approval multi-pengguna. Clipforge
sengaja mempertahankan **satu production owner** dan state persisten di `backend/data`; mengadopsi
swarm/sesi paralel akan melanggar jaminan `no_parallel_production_owner` dan dapat menyebabkan dobel Post.

## Verifikasi

- `backend/tests/test_ai_office_learning.py` — 7 pengujian ledger (seed, struktur, append, drift, validasi, integrasi direktur).
- Suite backend penuh: lihat hasil pada sesi deployment berikutnya.
- Capability baru `organizational_learning` dan `director.learning` diverifikasi `backend_contract()`.
