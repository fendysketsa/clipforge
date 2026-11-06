# Arahan visual RYUUNDY: momen yang bisa dilihat dan dipahami

Status: tahap awal renderer telah diimplementasikan dan demo MP4 18 detik
telah dirender. Implementasi dan batas kemampuan dijelaskan dalam
`ryuundy-motion-implementation-20261106.md`. Aktivasi produksi versi ini
terkonfirmasi pada 6 November 2026 pukul 14:56 WIB; catatan treatment di bawah
tetap menjadi arahan. Crop detail masih memerlukan region sumber yang direview.

## Brief

Pengguna ingin RYUUNDY memiliki penyutradaraan serta visual unik: referensi
klip luar, gambar yang berhenti lalu diperlakukan secara kreatif, animasi,
dan kemungkinan stop-motion. Sasaran: memperjelas momen, memberi kejutan yang
beralasan, dan menambah nilai penjelasan editor. Konten tetap bertumpu pada
sumber; caption terbaca stabil dan transisi kembali ke sumber terasa menyatu.
Belum ada otorisasi pengeluaran untuk generasi aset atau video berbayar pada
pengembangan treatment ini.

## Analysis

Source `backend/clipper.py` sudah memiliki `creative_director_plan`, pemilihan
aksen menurut isi, `semantic_surprise_beat`, serta treatment `reveal_punch_in`,
`reaction_snap`, dan `payoff_silence`. Pemilihan model dibatasi ke treatment
yang tersedia. Ini dasar yang dapat diperluas; bukan bukti bahwa freeze-frame
beranotasi, masking cutout, atau stop-motion objek sudah tersedia.

Rujukan teknik yang diperiksa adalah halaman resmi, bukan analisis audiovisual
penuh terhadap semua film:

- [PES — Fresh Guacamole](https://pesfilm.com/pages/fresh-guacamole),
  [keterangan film](https://pesfilm.com/products/fresh-guacamole-hd), dan
  [tentang PES](https://pesfilm.com/pages/about): stop-motion serta transformasi
  benda sehari-hari. Pelajaran untuk treatment ini adalah perubahan bentuk yang
  memiliki logika visual dan rasa material; tidak menyalin film atau asetnya.
- [Adobe — Cut-out animation](https://www.adobe.com/uk/creativecloud/animation/discover/cut-out-animation.html):
  penjelasan teknik dan contoh paper-cut termasuk karya MoSoMoS untuk Sesame
  Workshop. Berguna sebagai keluarga teknik untuk ilustrasi berlapis.
- [Johnny Harris — About](https://www.johnnyharris.ch/about): pembuat menjelaskan
  perpaduan motion graphics dan videografi sinematik untuk menjelaskan isu.
  RYUUNDY dapat mengambil prinsip memperlihatkan hubungan/sebab-akibat, dengan
  bahasa visual serta penjelasan sendiri.

Freeze-frame berarti satu gambar ditahan. Stop-motion berarti objek bergerak
melalui pose/gambar yang berubah bertahap. Keduanya bisa dipakai dalam satu
klip tetapi memiliki fungsi berbeda. Efek freeze tidak dengan sendirinya
menjadi penjelasan, dan efek stop-motion tidak dengan sendirinya menjaga retensi.

## Treatment

### 1. Freeze -> bedah momen -> kembali ke sumber

Pada pilihan atau ekspresi yang benar-benar penting, satu frame sumber ditahan.
Bagian relevan dilingkari/di-outline, satu panah menunjukkan objek yang sedang
dibicarakan, lalu satu catatan editor menjelaskan apa yang perlu diperhatikan.
Perlakuan awal sekitar 0,6–1,2 detik, disesuaikan kebutuhan membaca dan tempo.
Ini target desain, bukan waktu render yang sudah divalidasi.

Contoh ilustratif: pemain memilih jembatan yang salah. Freeze sebelum keputusan,
highlight celah yang terlihat, tampilkan "Celahnya di sini", kemudian pertahankan
urutan keputusan dan akibat sebenarnya. Jangan mengubah penilaian hasil atau
menyisipkan frame palsu. Jika sumber tidak memperlihatkan celah, contoh ini
tidak boleh dipaksakan pada klip tersebut.

Audio, caption, dan video perlu dirancang sebagai satu timeline. Pilih jeda
sumber yang cocok, gunakan cutaway analisis yang jelas, atau jika menyisipkan
waktu baru, remap ketiganya bersama. Jangan membuat wajah membeku sambil tetap
terlihat sedang mengucapkan audio yang tidak sinkron, atau melewatkan tindakan
penting ketika kembali ke sumber.

### 2. Cutout -> objek bergerak -> hubungan menjadi jelas

Pisahkan objek yang relevan menjadi lapisan: misalnya pintu, jalur permainan,
atau benda yang dibicarakan. Beri bayangan dan gerak kecil untuk menuntun mata.
Ilustrasi diberi konteks sebagai penjelasan editor, bukan rekaman bukti tambahan.
Cutout manusia yang perlu mempertahankan rambut/tangan memerlukan segmentasi
yang ditinjau; kotak crop tidak boleh disebut masking sempurna.

Gunakan komposisi yang tersambung: objek yang keluar dari frame sumber dapat
menjadi objek yang sama di diagram, lalu kembali ke lokasi semula. Hindari
memindahkan mulut atau mengarang gestur orang nyata.

### 3. Stop-motion benda untuk menjelaskan perubahan

Benda/ilustrasi bergerak dengan pose bertahap sekitar 8–12 perubahan per detik,
sementara video sumber dan caption tetap mengikuti frame rate normal.
Perubahan bisa memperlihatkan pilihan jalur, langkah kerja, atau urutan tindakan
yang disebut sumber. Kekhasannya berasal dari gerak dan hubungan benda, bukan
deretan judul di atas kartu.

Gunakan hanya 1–3 objek utama dan satu hubungan yang jelas. Untuk contoh proses,
objek yang sama tetap ada ketika keadaan berubah sehingga penonton memahami
apa yang berubah. Bunyi kertas/klik, jika digunakan, harus mendukung perubahan
yang terlihat dan tidak menutupi ucapan.

### 4. Diagram kecil yang dibangun oleh ucapan

Saat sumber menerangkan tiga penyebab, tampilkan tiga objek yang terhubung
bertahap. Saat menjelaskan sebelum/sesudah, objek yang sama berubah keadaan.
Label singkat membantu gambar; animasi memperlihatkan hubungan yang dijelaskan.
Angka, grafik, dan dokumen faktual harus berasal dari bukti yang tersedia.

### 5. Transisi yang melanjutkan gerakan

Arah tatapan, tangan, atau lintasan objek menuntun ke gambar berikutnya.
Potongan berikutnya menyambung gerak atau bentuk yang sama. Untuk ilustrasi
baru, tentukan lebih dulu objek serta hubungan yang ingin dipertahankan.
Transisi kuat boleh berupa cut langsung jika itu paling jelas.

## Contoh timeline ilustratif 24 detik

Ini contoh rancangan game, bukan transkrip atau video yang sudah diproduksi.

| Waktu desain | Apa yang terjadi | Fungsi |
| --- | --- | --- |
| 0–3 dtk | Tujuan pemain terlihat, potongan sumber langsung berjalan. | Penonton memahami taruhan. |
| 3–6 dtk | Pilihan pemain dan konteks cukup dipertahankan. | Menyiapkan keputusan. |
| 6–8 dtk | Analisis freeze singkat menandai detail yang benar-benar terlihat. | Mengarahkan perhatian. |
| 8–11 dtk | Diagram cutout dua jalur memperlihatkan pilihan; gerak objek bertahap. | Menjelaskan hubungan. |
| 11–20 dtk | Kembali ke sumber, keputusan dan akibat tidak dipotong. | Menuntaskan janji cerita. |
| 20–24 dtk | Reaksi asli atau simpulan spesifik; visual mengendap. | Memberi payoff dan ruang memahami. |

Waktu harus menyesuaikan materi, bukan memotong semua klip ke template 24 detik.

## Prioritas implementasi berikutnya

Mulai dari freeze beranotasi dan diagram objek/cutout sederhana sebagai dua
pilihan sutradara. Keduanya memiliki fungsi penjelasan yang dapat ditinjau.
Stop-motion menjadi karakter geraknya ketika sesuai isi. Masking manusia,
parallax kompleks, dan video generatif memerlukan tahap serta validasi terpisah.

Sutradara perlu mengeluarkan cue yang konkret: timestamp sumber, kutipan pemicu,
objek yang terlihat, perubahan yang dituju, alasan kreatif, aset yang tersedia,
area caption, serta cara keluar dan kembali ke sumber. Cue tanpa aset atau
bukti cukup dilewati. Pengembangan renderer diperlukan sebelum cue baru boleh
disebut dapat dieksekusi.

Review harus memakai hasil video sebenarnya: baca caption di ukuran ponsel,
periksa sebelum/sesudah cue, putar untuk menilai berat gerak dan kontinuitas,
serta dengarkan dialog dan mixing. Tes source saja tidak membuktikan kualitas
visual yang dilihat penonton.
