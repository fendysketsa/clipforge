# Aksen sutradara otomatis untuk cron

Status: implementasi dan pratinjau siap; **belum aktif di backend produksi**. Pemeriksaan live terakhir menunjukkan cron aktif tetapi penanda versi efek belum tersedia. Sudo memerlukan password interaktif.

Setiap render cron baru wajib memiliki 1–2 aksen visual. AI director yang sudah ada boleh memilih kutipan asli dan suasana; jika tidak tersedia, pemilih lokal memakai dialog bertimestamp dan sinyal konteks. Burst, sparkle, ripple, orbit, garis gerak, swoosh, rays, dan focus brackets dipilih dengan variasi konsisten per klip. Konteks sensitif memakai satu aksen tenang tanpa suara. Long memakai maksimal dua aksen pada bab terpilih.

Posisi ditentukan dari frame setelah framing dan subtitle selesai. Deteksi wajah opsional, area subtitle dan panel dilindungi, lalu gerakan/detail membantu memilih area. Jika area aman tidak ditemukan atau renderer aksen gagal, dipakai penanda tepi yang tenang. Ini heuristik visual dengan guard konservatif, bukan pelacakan objek semantik. Waktu efek diperkirakan di dalam segmen dialog, bukan alignment kata yang diverifikasi.

Render tidak menambahkan waktu atau menggeser audio/subtitle. Sebelum penggantian video sementara, jumlah frame, dimensi, dan durasi diperiksa. Upload cron baru ditahan jika bukti render efek wajib tidak tersedia; pemeriksaan sumber dan kualitas tetap berlaku. Pekerjaan manual tidak mengaktifkan efek ini.

## Pratinjau

- [Video contoh dari salinan klip lokal](cron-adaptive-preview.mp4)
- [GIF burst](impact-preview.gif)
- [Frame contoh](preview-burst.jpg)
- [Variasi aksen](effect-vocabulary.jpg)
- [Rencana efek contoh](preview-plan.json)

Contoh tidak diunggah. Video asli tidak diubah. Efek sengaja tanpa SFX tambahan; dialog tetap dominan.

## Validasi

34 pengujian fitur efek lulus. Sebelumnya 309 pengujian gabungan efek/Long/deployment/upload, 220 pengujian caption, dan 61 pengujian API cron/worker/manual lulus; gabungan tersebut memasukkan 33 pengujian efek sebelum satu pengujian hak sumber ditambahkan. Total cakupan berbeda: 591 pengujian. Jalur ekspor clipper.export_clip sesungguhnya juga berhasil menghasilkan video sintetis delapan detik dengan sidecar efek rendered=true; lihat [bukti ekspor](full-export-verification.json).

Pengujian encoding pada 30 dan 30000/1001 fps memeriksa jumlah frame, dimensi, durasi, hash paket audio, dan kotak efek terhadap area terlindungi. Pemeriksaan kompilasi Python, sintaks shell, dan whitespace diff lulus. Run API yang lebih luas berhenti pada pengujian streaming storyboard di luar perubahan ini; seluruh file API tidak dinyatakan lulus.

## Aktivasi

```sh
sudo bash /www/wwwroot/clipper/clipforge/scripts/activate-cron-director-effects.sh
```

Skrip membangun image, menunggu pekerjaan aktif selesai sebelum restart, mempertahankan browser upload, mengembalikan status sakelar cron, lalu memeriksa penanda versi efek pada API live. Hanya render cron baru setelah aktivasi yang mendapat kewajiban ini; hasil lama tidak dirender ulang atau diunggah ulang oleh perubahan ini.

[Hasil pemeriksaan terstruktur](verification.json)
