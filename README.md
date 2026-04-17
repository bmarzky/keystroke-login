# Keystroke Login System

Sistem autentikasi login berbasis biometrik keystroke menggunakan PHP, MySQL, JavaScript, dan opsi Machine Learning (Python). Sistem ini menganalisis pola penekanan tombol keyboard pengguna untuk verifikasi identitas, memberikan lapisan keamanan tambahan selain password tradisional.

## Fitur

- **Registrasi Pengguna**: Pengguna dapat mendaftar dengan username, password, dan pola keystroke unik.
- **Hybrid Authentication Tier**: Sistem keamanan bertingkat yang otomatis beradaptasi dengan jumlah data pengguna:
    - **Tier 1 (Sparse Data)**: Verifikasi instan sejak login pertama menggunakan **Personalized Heuristic (10%)**. Sangat ketat dan langsung beradaptasi dengan kecepatan unik tiap pengguna.
    - **Tier 1 (Normal Data)**: Beralih ke **Strict Mahalanobis** saat data mencapai ≥ 5 sampel untuk keamanan maksimal.
    - **Tier 2 (Advanced AI)**: Aktif otomatis saat data mencapai ≥ 15 sampel menggunakan **One-Class SVM** (Python).
- **Interactive Tutorial**: Dilengkapi dengan pemandu interaktif menggunakan **Driver.js** untuk membantu pengguna memahami cara kerja sistem saat pertama kali berkunjung.
- **Adaptive Learning**: Model Machine Learning otomatis dilatih ulang (retrain) di background setiap kali pengguna berhasil login, memastikan sistem selalu relevan dengan perubahan gaya ketik pengguna.
- **Biometrik Keystroke**: Capture data dwell time, flight time, n-graph, dan speed secara real-time menggunakan JavaScript.
- **Dashboard & Debugging**: Halaman dashboard yang aman dan log biometrik mendetail (Decision Score) untuk pemantauan akurasi.
- **Database MySQL**: Penyimpanan terenkripsi untuk data user dan metadata keystroke dalam format JSON.

## Prasyarat

- **XAMPP** (atau server web dengan PHP dan MySQL)
- **PHP 7.4+**
- **MySQL 5.7+**
- Browser web modern dengan JavaScript aktif
- **Python 3.x** (Hanya jika ingin menggunakan fitur Machine Learning)
- File `.env` yang dibuat dari `.env.example`

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
   - Salin `.env.example` ke `.env` dan sesuaikan kredensial database Anda:
     ```ini
     DB_HOST=localhost
     DB_USER=root
     DB_PASS=
     DB_NAME=keystroke_db
     ```
   - Jika Anda menyesuaikan `config/database.php` langsung, pastikan struktur variabel sudah benar.

4. **Jalankan Aplikasi**:
   - Buka browser dan akses `http://localhost/keystroke-login`.

## Penggunaan

1. **Registrasi**:
   - Akses halaman reguler atau klik register pada halaman awal (`auth/register.php`).
   - Isi form username, password, dan ketik ulang password beberapa kali pada field yang disediakan untuk melakukan capture terhadap biometrik (pola kecepatan Anda).
   - Klik "Register".

## Troubleshooting

Jika Anda mengalami masalah koneksi database, pastikan file `.env` sudah dikonfigurasi dengan benar dan XAMPP MySQL sedang berjalan.

2. **Login**:
   - Akses menu `auth/login.php`.
   - Masukkan username dan ketik password dengan ritme natural Anda.
   - **Proses Verifikasi**:
     - Sistem mengecek kecocokan password konvensional terlebih dahulu.
     - Jika benar, sistem memicu mesin biometrik dengan 3 level adaptif:
        - **Level 1 (Data 1-4)**: Menggunakan **Adaptive Blending (10%)** agar verifikasi instan tetap cerdas mengikuti ritme asli Anda.
        - **Level 2 (Data 5-14)**: Menggunakan **Strict Mahalanobis** dengan ambang batas agresif untuk mencegah segala jenis peniruan ritme.
        - **Level 3 (Data 15+)**: Menggunakan **One-Class SVM** melalui Python untuk perlindungan tingkat tinggi berbasis AI.
     - Login berhasil jika ritme ketikan dianggap cocok oleh sistem.

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