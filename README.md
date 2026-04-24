# Keystroke Login System

Sistem autentikasi login berbasis biometrik keystroke menggunakan PHP, MySQL, JavaScript, dan Machine Learning (Python). Sistem ini menganalisis pola penekanan tombol keyboard pengguna untuk verifikasi identitas, memberikan lapisan keamanan tambahan selain password tradisional.

## Fitur

- **Registrasi Pengguna**: Pengguna dapat mendaftar dengan username, password, dan pola keystroke unik sebagai *baseline*.
- **Hybrid Authentication Tier**: Sistem keamanan bertingkat yang otomatis beradaptasi dengan jumlah data pengguna:
    - **Tier 1 (Sparse Data - Hard Wall Strategy)**: Verifikasi sejak login pertama. Menggunakan baseline absolut (`history[-1]`) dan **Hard Speed Gate (15%)** untuk melindungi baseline dari keracunan (*baseline poisoning*) oleh imposters.
    - **Tier 1 (Normal Data - True Mahalanobis Distance)**: Menggunakan algoritma **Mahalanobis Distance** via Python (`ml/scripts/mahalanobis.py`) yang menyelesaikan masalah *feature correlation bias* melalui perhitungan *covariance matrix* saat sampel ≥ 5.
    - **Tier 2 (Advanced AI)**: Beralih ke **One-Class SVM** (Python) untuk perlindungan tinggi saat sampel ≥ 15.
- **Side-Channel Gates**: Melindungi dari serangan *shoulder-surfing* dan *automated replay attacks* melalui:
    - **D2D Flow Veto**: Analisis transisi ritme/jeda antar tombol.
    - **Key Overlap Veto**: Deteksi anomali pada tumpang-tindih (overlap) penekanan tombol.
- **Auto-Aligning Truncation Logic**: Menangani variasi pengetikan alami pengguna, seperti penekanan tombol 'Enter' yang tertunda.
- **Centralized Logging & Debugging**: Penyimpanan log khusus untuk upaya login gagal (`failed_keystrokes_raw.log`) guna kemudahan audit dan debugging, serta halaman dashboard dengan Decision Score.
- **Adaptive Learning**: Model Machine Learning otomatis dilatih ulang (retrain) di *background* setiap login berhasil untuk beradaptasi dengan perubahan gaya ketik pengguna.
- **Interactive Tutorial**: Dilengkapi dengan pemandu interaktif menggunakan **Driver.js** (jika diaktifkan) untuk edukasi pengguna baru.

## Prasyarat

- **XAMPP** (atau server web dengan PHP dan MySQL)
- **PHP 7.4+**
- **MySQL 5.7+**
- Browser web modern dengan JavaScript aktif
- **Python 3.x** dengan pustaka (NumPy, SciPy, scikit-learn)
- File `.env` yang disiapkan dengan kredensial yang tepat

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
   - Buat file `.env` di root direktori proyek dan isi kredensial database Anda (lihat konfigurasi pada `config/database.php`).
     ```ini
     DB_HOST=localhost
     DB_USER=root
     DB_PASS=
     DB_NAME=keystroke_db
     ```

4. **Jalankan Aplikasi**:
   - Buka browser dan akses `http://localhost/keystroke-login`.

## Penggunaan

1. **Registrasi**:
   - Akses halaman reguler atau klik register pada halaman awal (`auth/register.php`).
   - Isi form username, password, dan ketik ulang password secara alami pada field yang disediakan untuk menangkap biometrik (pola kecepatan Anda) sebagai *baseline*.
   - Klik "Register".

2. **Login**:
   - Akses menu `auth/login.php`.
   - Masukkan username dan ketik password dengan ritme natural Anda.
   - **Proses Verifikasi**:
     - Sistem memvalidasi password konvensional terlebih dahulu.
     - Sistem memicu mesin biometrik yang terhubung ke Python (Hybrid Tier):
        - **Data 1-4 (Early Stage)**: Evaluasi heuristik & Side-Channel Gates, ditambah perlindungan *Hard Wall Gate* 15%.
        - **Data 5-14**: Kalkulasi statistik dengan True Mahalanobis Distance untuk menangkal anomali korelasi.
        - **Data 15+**: Deteksi tingkat tinggi menggunakan One-Class SVM.
     - Login akan ditolak jika mencoba merekayasa kecepatan, menggunakan script (replay), atau mencoba meniru (imposter bypass).

3. **Dashboard & Audit**:
   - Jika login berhasil, Anda dialihkan ke `dashboard/index.php`.
   - Log percobaan gagal dan anomali dapat diaudit di folder `ml/data/`.

## Struktur Proyek

```text
keystroke-login/
├── .env                       # File konfigurasi environment variables (harus dibuat)
├── assets/                    # Aset front-end (CSS, JS)
│   ├── css/
│   └── js/
│       ├── keystroke.js       # Sensor biometrik untuk frontend
│       └── auth-forms.js      # Pengelola form login/register
├── auth/                      # Modul Autentikasi UI & Backend
│   ├── login.php              
│   ├── register.php           
│   └── process/               # Controller autentikasi PHP
├── config/                    # Konfigurasi system wide
│   └── database.php           
├── core/                      # Logika pemrosesan sistem PHP
│   └── biometrics.php         # Penghubung PHP dengan mesin biometrik Python
├── dashboard/                 # Area tampilan privat pengguna
├── database/                  # Repositori database query
│   └── keystroke.sql          
├── ml/                        # Modul Model Machine Learning (AI-Powered Biometrics)
│   ├── data/                  # Folder kumpulan dataset biometrik
│   │   ├── biometric_debug.log         # Log lengkap hasil prediksi
│   │   └── failed_keystrokes_raw.log   # Raw log khusus percobaan login gagal (imposters)
│   ├── model/                 # Tempat ekspor pre-trained model SVM
│   ├── scripts/               # Algoritma Machine Learning (Python)
│   │   ├── mahalanobis.py     # Mesin True Mahalanobis Distance berbasis Covariance
│   │   ├── predict.py         # Skrip SVM prediction
│   │   ├── inspect_models.py  # Skrip visualisasi & inspeksi (PCA)
│   │   └── train.py           # Skrip background training SVM
│   └── requirements.txt       # Dependencies modul library Python (pip)
└── index.php                  # Entry point pertama pengunjung (Routing utama)
```

## Kontribusi

Kontribusi sangat diterima! Silakan fork repository ini, buat branch fitur baru, dan kirim pull request.

1. Fork repository.
2. Buat branch fitur baru: `git checkout -b fitur-baru`.
3. Commit perubahan: `git commit -m 'Tambah fitur inovasi baru'`.
4. Push ke branch: `git push origin fitur-baru`.
5. Buat Pull Request dan biarkan direview.

## Troubleshooting

Jika Anda mengalami masalah koneksi database, pastikan file `.env` sudah dikonfigurasi dengan benar dan MySQL sedang berjalan.
Jika terjadi kesalahan pada sistem biometrik (Python execution), pastikan Python 3.x dan semua package di `ml/requirements.txt` telah terinstal, dan `python` dapat dipanggil secara global melalui command line.

## Kontak

Jika ada kendala, ide fitur maupun pertanyaan lebih lanjut, silakan bebas melayangkan pesan ke [bmarzky](https://github.com/bmarzky).

## Lisensi

Proyek ini didistribusikan di bawah Lisensi MIT (Massachusetts Institute of Technology). Bebas untuk dimodifikasi dan digunakan sesuai keperluan proyek Anda.