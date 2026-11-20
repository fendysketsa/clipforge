# Riset niche dinamis khusus cron — 20 November 2026

Implementasi sumber dan pengujian selesai. Aktivasi container belum dilakukan:
backend yang sedang berjalan masih mengembalikan HTTP 404 untuk endpoint
`/api/automation/viral-cc/editorial-policy`. Pemeriksaan terakhir menunjukkan
cron ON dan Long sedang dirender. `sudo -n true` mengembalikan
`sudo: a password is required`.

## Perilaku baru

- Pencarian milik run `trigger=schedule` terbuka lintas channel; tidak memakai
  pembatas `channelId` atau resolusi handle channel referensi/gaming.
- Riset otomatis berjalan di thread terpisah ketika scheduler cron aktif.
  Setiap pergantian bulan Asia/Jakarta memicu rencana baru, maksimal 12 subniche
  berbasis sinyal aktual. Studio demand yang digunakan berumur maksimal tujuh
  hari; Google Trends RSS, chart populer YouTube Indonesia dan dua pencarian
  bulan berjalan menyediakan sumber tambahan. Tidak ada channel whitelist.
- Subniche eksplorasi bulanan mendapat satu dari lima slot kampanye biasa
  ketika slot tersebut tidak dipakai prioritas musim. Per tema induk maksimal
  tiga subniche; satu topik per tema dipilih dahulu agar chart besar tidak
  menutup semua kesempatan topik lain. Tema sains/teknologi/pengetahuan praktis
  ikut ditambahkan sebagai induk untuk penemuan topik baru.
- Rotasi pencarian kajian mencakup 18 nama ustadz/ustadzah, ditambah giliran
  pencarian umum agar pembicara di luar daftar tetap dapat ditemukan. Nama
  adalah kata pencarian, bukan bukti identitas, kepemilikan channel atau izin.
- Kalender Hijriah memperhitungkan pergeseran Ramadan setiap tahun: 30 hari
  persiapan mendapat prioritas 40%, Ramadan 75%, dan sepuluh malam terakhir
  menggunakan brief berbeda. Lebaran dan haji/kurban masing-masing 40%.
  Kemerdekaan, akhir tahun dan libur sekolah juga menjadi petunjuk editorial.
  Persentase adalah pembagian kampanye biasa, bukan jumlah upload yang dijamin.
- Manual/API generation tetap menggunakan pilihan operator. Tema serta konteks
  editorial diteruskan dari Short cron ke Long pasangannya, termasuk Long yang
  diproduksi worker terpisah dari riwayat sumber Short. Target harian 17 Short
  terjadwal, 4 Short private dan 2 Long tidak diubah. QC Long dan publication
  holds tetap berlaku.

Rencana, counter rotasi dan checkpoint retry disimpan atomik di
`backend/data/cron_editorial_policy.json`, dalam volume data yang sudah ada.
Preview dan endpoint GET tidak mengonsumsi slot. Slot baru dicatat ketika
kampanye cron dibuat; pemangkasan riwayat run tidak mengulang rotasi.
Jika riset kosong/gagal, tidak ada rencana palsu yang ditandai berhasil;
penelitian dicoba ulang setelah enam jam dan bulan baru mengabaikan backoff
bulan sebelumnya. Data operator, checkpoint upload dan remote ID tidak
ditulis oleh fitur ini.

## Bukti riset live

[live-monthly-research.json](live-monthly-research.json) mencatat pengambilan
terakhir: **80 sinyal dari empat sumber yang menghasilkan data**, disaring
menjadi **12 subniche untuk November 2026**. Pencarian tambahan kajian tidak
menghasilkan entri pada pengambilan terakhir; rotasi pencarian ustadz pada
kampanye cron tetap tersedia dan tidak bergantung pada hasil feed bulanan.
Topik dalam rencana mencakup gaming/story, misteri, hubungan, sains/teknologi,
sepak bola dan politik. Setiap entri menyimpan sumber dan waktu observasi.
Judul feed adalah sinyal penemuan; kebenaran klaim di judul belum diverifikasi.

Kategori musik, pola judul video musik, broadcast live/upcoming dan sinyal
berbahaya disaring sesuai bukti yang tersedia. Kecocokan niche wajib ada pada
judul/query, sehingga kata dari kredit/deskripsi tidak menentukan tema.
Judul campuran ceramah dan politik yang cocok dengan tema review wajib tetap
masuk tema review. Hasil penemuan tidak memberikan hak sumber atau izin upload;
filter sumber, bahasa Indonesia, hak penggunaan dan QC tetap dijalankan.

Rencana awal sudah disimpan pada file kebijakan baru di volume data. Ini
persiapan data untuk runtime baru, bukan bukti bahwa container aktif telah
memakai kebijakan tersebut.

## Validasi

**559 pengujian lulus**, enam pengujian storyboard/stream di luar cakupan
dikecualikan. Mencakup kalender lintas tahun, batas tanggal WIB, prioritas
Ramadan, rotasi pembicara, retry bulanan, data rusak, idempotensi checkpoint,
pencarian lintas channel, isolasi manual, klasifikasi politik, pelestarian
hold, Short/Long, kuota harian, playlist dan kontrak startup Docker.
Kompilasi modul Python serta `git diff --check` juga lulus.

Satu pengujian kuota lama dibuat deterministik dengan memilih tema kajian pada
fixture-nya. Cache Studio nyata sebelumnya memilih politik sehingga hold
politik dengan benar menonaktifkan upload, yang tidak berkaitan dengan
penghitungan kapasitas private pada pengujian tersebut.

[verification.json](verification.json) berisi ringkasan hasil pengujian,
hash sumber, waktu pemeriksaan dan status API yang sedang berjalan. Tidak ada
render baru atau publikasi video yang dilakukan untuk validasi fitur ini.

## Aktivasi

Dependency `hijridate` akan dipasang melalui requirements/Dockerfile yang sudah ada.
Manifest image mencakup modul baru; startup memeriksa dependency dan kontrak
endpoint editorial tanpa menyalakan cron yang dinonaktifkan operator.
Konfigurasi default baru diteruskan lewat Compose. Tidak memerlukan skrip
aktivasi tambahan.

Setelah pekerjaan aktif selesai dan akses sudo tersedia, gunakan perintah
standar repository:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Setelah itu verifikasi ketiga layanan, endpoint editorial, identitas sumber
runtime dan konteks request pada kampanye cron baru sebelum menyatakan fitur
aktif. Pada pemeriksaan dalam laporan ini, aktivasi **belum terverifikasi**.

## Dasar kalender

[HijriDate](https://hijridate.readthedocs.io/en/stable/) menyediakan konversi
Umm al-Qura untuk kalender editorial. Tanggal dalam fitur ini adalah perkiraan,
bukan penetapan ibadah. Pengumuman resmi Indonesia tetap menjadi rujukan,
termasuk [publikasi kalender Kemenag 2027](https://kemenag.go.id/nasional/kalender-hijriah-indonesia-tahun-2027-tersedia-di-perpustakaan-digital-kemenag-ini-cara-aksesnya-d3dNu).
