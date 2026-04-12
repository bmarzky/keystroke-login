# Keystroke Login System

Sistem autentikasi login berbasis biometrik keystroke menggunakan PHP, MySQL, JavaScript, dan opsi Machine Learning (Python). Sistem ini menganalisis pola penekanan tombol keyboard pengguna untuk verifikasi identitas, memberikan lapisan keamanan tambahan selain password tradisional.

## Fitur

- **Registrasi Pengguna**: Pengguna dapat mendaftar dengan username, password, dan pola keystroke unik.
- **Login dengan Keystroke**: Verifikasi identitas melalui analisis waktu penekanan dan jeda antar tombol menggunakan logika Mahalanobis Distance dalam PHP.
- **Machine Learning (Opsional)**: Terdapat fungsionalitas Machine Learning menggunakan Python di direktori `ml/` untuk melatih dan memprediksi pola keystroke.
- **Dashboard**: Halaman aman setelah login berhasil.
- **Biometrik Keystroke**: Menggunakan JavaScript untuk capture data keystroke secara real-time.
- **Database MySQL**: Penyimpanan data pengguna dan pola keystroke.

## Prasyarat

- **XAMPP** (atau server web dengan PHP dan MySQL)
- **PHP 7.4+**
- **MySQL 5.7+**
- Browser web modern dengan JavaScript aktif
- **Python 3.x** (Hanya jika ingin menggunakan fitur Machine Learning)

## Instalasi

1. **Clone Repository**:
   ```bash
   git clone https://github.com/bmarzky/keystroke-login.git
   cd keystroke-login
   ```

2. **Setup Web Server (XAMPP)**:
   - Pastikan folder `keystroke-login` berada di dalam `C:\xampp\htdocs\`.
   - Jalankan XAMPP Control Panel dan start Apache serta MySQL.

3. **Konfigurasi Database**:
   - Buka phpMyAdmin (http://localhost/phpmyadmin).
   - Buat database baru (misalnya, `keystroke_db`).
   - Import file `database/keystroke.sql` ke database tersebut.
   - Edit `config/database.php` untuk menyesuaikan kredensial database Anda (bisa sesuaikan `.env` jika digunakan):
     ```php
     $host = 'localhost';
     $db = 'keystroke_db'; // Ganti sesuai nama database Anda
     $user = 'root';
     $pass = ''; // Ganti password jika ada
     ```

4. **Jalankan Aplikasi**:
   - Buka browser dan akses `http://localhost/keystroke-login`.

## Penggunaan

1. **Registrasi**:
   - Akses halaman reguler atau klik register pada halaman awal (`auth/register.php`).
   - Isi form username, password, dan ketik ulang password beberapa kali pada field yang disediakan untuk melakukan capture terhadap biometrik (pola kecepatan Anda).
   - Klik "Register".

2. **Login**:
   - Akses menu `auth/login.php`.
   - Masukkan username dan ketik password dengan tempo irama ketikan yang secara konsisten sama persis layaknya saat registrasi.
   - PHP (`core/biometrics.php`) atau Python ML akan menganalisa dan melakukan validasi verifikasi jarak deviasi keystroke pattern.

3. **Dashboard**:
   - Setelah login berhasil, Anda akan dialihkan ke layar status `dashboard/index.php`.

## Struktur Proyek

```text
keystroke-login/
├── .env                       # File konfigurasi variabel environment (opsional)
├── .gitignore                 # Konfigurasi file yang diabaikan Git
├── .htaccess                  # Konfigurasi rewrite/aturan server web Apache
├── assets/                    # Aset front-end (CSS, JS)
│   ├── css/
│   │   └── style.css          # Styling untuk UI antarmuka
│   └── js/
│       └── keystroke.js       # Script pendeteksi & kalkulator sensor keystroke (Penting)
├── auth/                      # Modul Autentikasi UI & Backend
│   ├── login.php              # Halaman form UI login
│   ├── register.php           # Halaman form UI pendaftaran
│   └── process/               # Proses controller autentikasi
│       ├── biometric_debug.log# Log hasil pencatatan debug biometrik
│       ├── login.php          # Proses verifikasi login input
│       ├── logout.php         # Proses terminasi sesi
│       └── register.php       # Proses simpan data pengguna baru
├── config/                    # Konfigurasi system wide
│   └── database.php           # Script konfigurasi konektor database MySQL (PDO/MySQLi)
├── core/                      # Logika pemrosesan sistem
│   └── biometrics.php         # Algoritma biometrik Mahalanobis Distance (Metrik Kecocokan)
├── dashboard/                 # Area tampilan privat pengguna
│   └── index.php              # Laman depan dashboard pengguna terautentikasi
├── database/                  # Repositori database query
│   └── keystroke.sql          # File Dump database tabel dasar
├── ml/                        # Modul Model Machine Learning (AI-Powered Biometrics)
│   ├── data/                  # Folder kumpulan raw dataset atau features
│   ├── model/                 # Tempat ekspor simpangan pre-trained model
│   ├── scripts/               # Algoritma eksekusi neural atau scikit
│   │   ├── predict.py         # Skrip kalkulasi akurasi model & live prediction
│   │   └── train.py           # Skrip training set dari logs pengguna
│   └── requirements.txt       # Dependencies modul library Python (pip)
├── index.php                  # Entry point pertama pengunjung (Routing utama)
└── README.md                  # Dokumentasi repo ini
```

## Kontribusi

Kontribusi sangat diterima! Silakan fork repository ini, buat branch fitur baru, dan kirim pull request.

1. Fork repository.
2. Buat branch fitur baru: `git checkout -b fitur-baru`.
3. Commit perubahan: `git commit -m 'Tambah fitur inovasi baru'`.
4. Push ke branch: `git push origin fitur-baru`.
5. Buat Pull Request dan biarkan direview.

## Kontak

Jika ada kendala, ide fitur maupun pertanyaan lebih lanjut, silakan bebas melayangkan pesan ke [bmarzky](https://github.com/bmarzky).

## Lisensi

Proyek ini didistribusikan di bawah Lisensi MIT (Massachusetts Institute of Technology). Bebas untuk dimodifikasi dan digunakan sesuai keperluan proyek Anda.