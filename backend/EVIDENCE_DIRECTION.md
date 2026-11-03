# Bukti yang mengikuti ucapan

`export_clip()` menelusuri referensi tulisan, unggahan sosial, ucapan, dan
tuduhan sebelum menyusun treatment creative director. Konteks sampai 120 detik
sebelum klip membantu mengenali media yang namanya terpotong dari Short.
Pencarian publik dibatasi dua permintaan dengan timeout lima detik per klip.
`SHORTS_EVIDENCE_RESEARCH_ENABLED=false` mematikan pencarian; label sumber yang
belum diperiksa tetap muncul. Tidak diperlukan API key tambahan.

Hasil pencarian hanya kandidat. Koneksi gagal, CAPTCHA, hasil kosong, dan sumber
yang belum diperiksa tersimpan sebagai status sebenarnya. Screenshot atau
kutipan dari sumber pembanding tidak menggantikan unggahan persis yang dibahas.
Tidak ada pemeriksaan fakta otomatis yang dijamin oleh fitur ini.

Setiap referensi mempunyai ID stabil dari timestamp sumber, jenis, dan ucapan.
Sidecar video menyimpan `evidence_direction.beats`, query, kandidat, status,
rentang tampil, dan apakah panel benar-benar dirender. `manual_publication_review`
menandai konteks yang belum selesai diperiksa. `production_team_handoff` meneruskan
bukti konkret ke penelusur, tim kreatif, sutradara, dan editor.

Tanpa sumber yang diperiksa, renderer memberi atribusi pada penilaian pembicara
atau menampilkan warning sumber belum terverifikasi. Satu aksen singkat menandai
kemunculan panel, lalu tulisan diam untuk dibaca. Panel dirender setelah reframe
dan efek, sebelum subtitle. Wajah dan subtitle tetap perlu diperiksa pada hasil
akhir karena komposisi setiap sumber berbeda.

## Memasukkan sumber yang sudah diperiksa

Simpan `evidence.json` di folder sumber, sejajar dengan `metadata.json` dan folder
`clips`. Ambil ID dan `utterance` dari `evidence_direction.beats` hasil render.
Contoh berikut adalah skema, bukan bukti untuk klip mana pun:

```json
{
  "references": {
    "ID_DARI_SIDECAR": {
      "kind": "written_source",
      "utterance": "Ucapan persis dari referensi tersebut.",
      "review_status": "source_checked",
      "relationship": "exact_reference",
      "source_url": "https://media.example/artikel-asli",
      "publisher": "Nama media asli",
      "published_at": "2026-11-01",
      "checked_at": "2026-11-03",
      "reviewed_by": "Nama pemeriksa",
      "excerpt": "Kutipan persis yang menjelaskan bagian terkait.",
      "snapshot_text": "evidence/article.txt",
      "snapshot_text_sha256": "SHA256_TEKS_SUMBER",
      "image": "evidence/article.png",
      "image_sha256": "SHA256_SCREENSHOT"
    }
  }
}
```

`snapshot_text` wajib memuat kutipan persis. Kutipan dibatasi 25 kata dan 240
karakter. Screenshot PNG/JPEG opsional; teks dan screenshot wajib berada di
dalam folder sumber dan cocok dengan hash yang dicatat. Record salah jenis,
beda ucapan, sumber pembanding, snapshot berubah, atau path keluar folder
ditolak. Record ini berasal dari pemeriksa sumber, bukan keluaran bebas LLM.

Sumber yang lolos ditampilkan dengan penerbit, tanggal, tautan, screenshot bila
tersedia, dan kutipan yang relevan. Status `source_checked` hanya berarti sumber
rujukannya diperiksa; tidak membuktikan semua klaim di dalamnya. Tuduhan tentang
motif tetap diberi label sebagai penilaian pembicara.

Implementasi: `evidence_director.py`, integrasi di `clipper.py`.
