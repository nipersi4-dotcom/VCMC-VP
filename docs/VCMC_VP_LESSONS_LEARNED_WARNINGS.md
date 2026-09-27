# VCMC-VP — Peringatan Kesalahan & Lessons Learned Teknis

Status: DIKUNCI SEBAGAI PEGANGAN
Tanggal: 27 September 2026
Scope: VCMC-VP / server.py / frontend / deployment / testing

## TUJUAN

Dokumen ini dibuat agar kesalahan yang terjadi selama pembangunan dan deployment VCMC-VP tidak diulang.

PRINSIP:
- Jangan mengulang langkah yang sudah terbukti gagal.
- Jangan mengubah bagian yang sudah terbukti bekerja hanya untuk mengejar masalah yang belum terbukti.
- Jangan menganggap output AI/transkripsi screenshot sebagai bukti lebih tinggi daripada output terminal langsung.
- Jangan deploy sebelum perubahan lokal diverifikasi.
- Jangan menyentuh database tanpa alasan dan backup yang jelas.
- Satu perubahan terisolasi → verifikasi → deploy → uji nyata → baru lanjut.

## 1. KESALAHAN PLACEHOLDER SESSION

Pernah terjadi pemeriksaan string yang salah karena pencarian substring: `VALUES(?,?,?)` dapat ditemukan di dalam `VALUES(?,?,?,?)`.

AKIBAT:
- Validasi palsu dapat menyatakan SQL benar padahal placeholder salah.

ATURAN BARU:
- Untuk SQL kritis, jangan gunakan pemeriksaan substring.
- Verifikasi baris SQL secara tepat atau hitung placeholder secara eksplisit.
- Schema sessions yang terbukti: `token TEXT, user_id INTEGER, expires REAL`
- SQL yang sesuai: `INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)`

## 2. JANGAN MENYAMAKAN GITHUB DENGAN LOCAL WORKSPACE

Repo GitHub dan workspace lokal pernah berbeda.

ATURAN BARU:
- Sebelum patch, pastikan sumber yang akan diubah benar-benar versi yang sedang dipakai deployment.
- Jangan menganggap GitHub main otomatis identik dengan `~/VCMC-VP`.
- Jangan overwrite local server.py dari sumber lain tanpa verifikasi isi dan target.
- Setelah perubahan lokal, verifikasi file lokal yang benar-benar akan di-upload.

## 3. DATABASE TIDAK BOLEH DIUBAH SEMBARANGAN

Pernah ditemukan mismatch schema audit: database lama memakai kolom `at, actor, action, entity, details`, sedangkan kode baru membutuhkan `event, detail, created_at`.

Migrasi akhirnya dilakukan dengan backup terlebih dahulu dan login kemudian terbukti berhasil.

ATURAN BARU:
- Database adalah aset fondasi.
- Jangan menghapus, membuat ulang, atau mengganti database untuk menyelesaikan masalah frontend.
- Setiap migrasi harus: backup → inspect schema → migrate minimally → verify → baru deploy.
- UI/Room patch tidak boleh menyentuh database.

## 4. FRONTEND LOGIN ADALAH BAGIAN TERLINDUNG

Baseline yang sudah terbukti di HP:
- Login page tampil.
- Ikon password `👁` tampil.
- Login berhasil.
- HOME tampil.
- Network dan Evidence dapat dipanggil.
- Session/login backend menghasilkan HTTP 200 dan token.

PERINGATAN:
- Jangan memodifikasi area login/session/navigation hanya karena sedang membangun Room.
- Room tidak boleh merusak: login → session → identity → home.
- Perubahan Room harus dibuat terisolasi dari login.

## 5. KESALAHAN PATCH ROOM

Patch Room pertama menggunakan asumsi bahwa local `server.py` memiliki `function room(id,name)`. Ternyata fungsi tersebut tidak ada pada local source.

AKIBAT:
- Patch gagal.
- Beberapa percobaan pemeriksaan/patch menghabiskan waktu.
- Patch Room yang kemudian berhasil dipasang ternyata berpengaruh terhadap frontend yang sebelumnya sudah terbukti bekerja setelah deployment.

ATURAN BARU:
- Jangan berasumsi struktur kode berdasarkan versi lain.
- Sebelum patch, identifikasi struktur nyata local source.
- Jangan mengganti blok frontend besar untuk menambahkan satu Room.
- Room harus ditambahkan dengan perubahan sekecil mungkin dan tidak menyentuh login.
- Setelah patch Room: compile/syntax check → static check → deploy → HP login test → Home test → Room test.
- Jika login/eye rusak setelah Room patch, rollback segera ke baseline terbukti.

## 6. ROLLBACK ADALAH MEKANISME KONTROL

Backup yang dipakai untuk kembali ke baseline terbukti: `server.py.before-room-patch-v2`.

Rollback berhasil memulihkan:
- ikon 👁
- login HP
- HOME

ATURAN BARU:
- Sebelum perubahan besar frontend, selalu buat backup.
- Backup harus memiliki nama jelas berdasarkan perubahan.
- Jangan menghapus backup baseline yang sudah terbukti sampai versi baru terbukti.
- Jika perubahan baru merusak baseline, rollback lebih dulu daripada menambal secara acak.

## 7. DEPLOY ≠ PROVEN

Deploy berhasil dengan preflight 7 checks passed serta upload/build/roll out berhasil dan HTTP 200.

Tetapi itu tidak otomatis membuktikan login UI, password eye, Room interaction, browser behavior, atau mobile behavior.

ATURAN BARU: `DEPLOYED ≠ PROVEN`.
Setelah deploy wajib ada real-user test dari HP untuk jalur yang berubah.

## 8. HP ADALAH TEST REPRESENTATIVE NYATA

HP/browser pengguna sudah terbukti menjadi jalur nyata: PUBLIC HTTPS → LOGIN → SESSION → IDENTITY → HOME.

ATURAN BARU:
- HP dipakai sebagai salah satu wakil pengguna publik.
- Jika HP gagal, jangan menyatakan fitur frontend terbukti.
- Jangan mengejar environment Dola/client lain dengan mengorbankan baseline HP yang sudah bekerja.

## 9. JANGAN MENGULANG PEMERIKSAAN YANG SAMA

Kesalahan proses: terlalu banyak pemeriksaan potongan baris yang terpotong oleh tampilan terminal dan terlalu banyak meminta salinan yang tidak memberikan bukti baru.

ATURAN BARU:
- Pilih satu pemeriksaan yang benar-benar menjawab pertanyaan.
- Gunakan command berbasis marker/fungsi yang pasti bila perlu.
- Jika bukti sudah cukup, berhenti memeriksa.
- Fokus pada perubahan dan penyelesaian, bukan loop diagnosis.

## 10. ATURAN PERUBAHAN FRONTEND BERIKUTNYA

BASELINE TERKUNCI: LOGIN → SESSION → IDENTITY → HOME.

Perubahan yang diizinkan: HOME → satu Room → interior Room → kembali HOME.

Perubahan yang tidak boleh dilakukan tanpa alasan dan bukti:
- mengganti login
- mengganti session
- mengganti identity
- mengganti navigation global
- mengganti database
- mengganti provider/deployment
- mengganti seluruh frontend

## 11. URUTAN KERJA WAJIB

ARCHITECTURE FIRST → perubahan minimal → backup → local syntax check → local functional check → deploy → HP test → evidence → lanjut Room berikutnya.

Jika gagal: STOP → IDENTIFY → ROLLBACK → VERIFY → baru perbaiki.

## 12. KETETAPAN PENTING

Pengalaman ini harus diperlakukan sebagai bagian dari continuity VCMC-VP.

Jangan:
- mulai dari nol
- mengulang patch gagal
- menganggap source lain identik
- mengubah database untuk masalah UI
- deploy berulang tanpa bukti
- mengorbankan login yang sudah terbukti demi Room
- menganggap HTTP 200 sebagai bukti seluruh aplikasi
- menganggap AI transcription sebagai bukti lebih tinggi daripada terminal langsung

Pegangan utama:

RECORD ≠ DONE ≠ PROVEN

Dan:

WORKING BASELINE MUST BE PROTECTED BEFORE EXPANSION.