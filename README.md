# Biometric Authentication System Login

[![Version](https://img.shields.io/badge/version-2.5.0--stable-blue.svg)](https://github.com/bmarzky/keystroke-login)
[![Python](https://img.shields.io/badge/Python-3.12-brightgreen.svg)](https://www.python.org/)

**Biometric Authentication System Login** adalah sistem autentikasi berbasis *Keystroke Dynamics* yang memverifikasi identitas pengguna melalui pola ritme ketikan yang unik. Sistem ini dirancang sebagai lapisan keamanan kedua (**MFA**) yang menggabungkan analisis statistik multivariat dan *Machine Learning* untuk mendeteksi upaya impersonasi secara *real-time*, memastikan bahwa hanya pemilik akun asli yang dapat mengakses sistem meskipun password telah diketahui oleh pihak lain.

---

## Arsitektur Keamanan

Sistem ini mengadopsi arsitektur keamanan berlapis yang dirancang untuk integritas data tinggi. Alur kerja dimulai dari penangkapan aliran input ketikan pengguna secara *real-time*, yang kemudian diproses oleh *Pre-processing Engine* untuk divalidasi dan dibersihkan dari pencilan (*outliers*). Fitur-fitur biometrik inti seperti *Dwell Time* dan *Flight Time* diekstraksi untuk membangun profil perilaku yang unik bagi setiap pengguna.

Inti dari kecerdasan sistem ini terletak pada mekanisme autentikasi ganda: **Statistical Engine** yang menggunakan perhitungan jarak Mahalanobis dan **AI Engine** berbasis *One-Class Support Vector Machine* (OCSVM). Kedua mesin ini bekerja secara paralel untuk menganalisis kedekatan pola input dengan profil historis. Hasil dari kedua analisis tersebut kemudian disatukan melalui **Decision Fusion Engine** untuk memberikan keputusan akhir apakah akses diberikan atau ditolak. Selain itu, sistem secara cerdas memperbarui profil pengguna melalui *Adaptive Learning Engine* pada setiap login yang berhasil, memastikan sistem tetap akurat meskipun terjadi perubahan gaya ketik pengguna di masa depan (*concept drift*). Seluruh aktivitas dan anomali dicatat secara mendetail dalam log keamanan untuk pemantauan dan analisis pola serangan.

---

## Fitur Unggulan

| Komponen | Deskripsi Fungsional |
| :--- | :--- |
| **Adaptive Thresholding** | Pengerasan ambang batas keamanan secara dinamis berbasis populasi sampel ($n$). |
| **Replay Protection** | Deteksi redundansi data untuk menangkal serangan biometrik statis (*copy-paste*). |
| **Biometric Audit Trail** | Dokumentasi metrik teknis (Mahalanobis & AI Score) untuk kebutuhan forensik. |
| **AI Auto-Training** | Pelatihan model OCSVM secara otomatis setiap kelipatan 20 data baru. |
| **Forgiver Logic** | Toleransi cerdas terhadap deviasi kecepatan jika korelasi pola tetap tinggi. |
| **Multivariate Gating** | Analisis keterkaitan antar fitur menggunakan jarak Mahalanobis yang presisi. |
| **24D Feature Vector** | Ekstraksi 24 fitur unik termasuk FFT untuk identifikasi tanda tangan frekuensi. |
| **Secure Core** | Enkripsi sesi dan hashing password standar industri menggunakan Bcrypt. |

## Tech Stack

-   **Backend Core**: Python 3.12 (Flask Framework)
-   **Intelligence Unit**: Scikit-Learn (OCSVM), NumPy (Linear Algebra), Joblib
-   **Data Storage**: MySQL / MariaDB
-   **Security**: Bcrypt (Password Hashing), Session Encryption, .env Configuration
-   **Frontend**: HTML5, Vanilla CSS (Glassmorphism UI), Javascript (Keystroke Collector)

---

## Struktur Proyek

```text
keystroke-login/
├── app.py                     # Entry point: Flask App initialization & Routing
├── requirements.txt           # Dependensi library (Flask, Sklearn, Numpy, etc.)
├── .env                       # Konfigurasi database & Secret keys
│
├── src/                       # Source Code (Pusat Logika)
│   ├── engine/                # Inti Kecerdasan Biometrik
│   │   ├── core.py            # Titanium Fusion Engine (Logic Utama)
│   │   └── ml/                # AI Environment (OCSVM, Training)
│   │
│   ├── models/                # Data Layer (Akses Database)
│   │   ├── user_model.py      # CRUD untuk tabel pengguna
│   │   └── keystroke_model.py # CRUD untuk data biometrik
│   │
│   ├── services/              # Logic Layer (Aturan Bisnis)
│   │   ├── biometric_service.py # Verifikasi, Replay Detection & Orkestrasi
│   │   └── stats_service.py   # Kalkulasi metrik dashboard (WPM, Stability)
│   │
│   ├── config/                # Konfigurasi Teknis
│   │   └── database.py        # Koneksi Database & Secret Management
│   │
│   ├── utils/                 # Utility Helpers
│   │   └── logger.py          # Logger forensik biometrik
│   │
│   └── database/              # Skema SQL & Inisialisasi DB
│
├── static/                    # Frontend Assets (Collector & UI)
├── templates/                 # Jinja2 Layouts (Auth & Dashboard)
├── logs/                      # Audit Trail (Forensik Biometrik)
└── scratch/                   # Tools Riset (Validation & Training scripts)
```

---

## Cara Instalasi

1.  **Persiapkan Database**: Jalankan MySQL (XAMPP), buat database `keystroke_db` dan impor skema yang disediakan di folder `database/`.
2.  **Virtual Environment (Opsional)**:
    ```powershell
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```
4.  **Konfigurasi `.env`**:
    Sesuaikan kredensial database di file `.env`.
5.  **Run Application**:
    ```powershell
    python app.py
    ```
    Akses di: `http://localhost:8000`

---

## Metrik yang Dianalisis

Sistem membangun tanda tangan biometrik yang presisi melalui ekstraksi **24 fitur unik** yang dikategorikan sebagai berikut:

*   **Temporal Metrics**:
    *   **Hold Time**: Durasi penekanan tombol dari *keydown* hingga *keyup*. Metrik ini mencerminkan kebiasaan motorik halus pengguna.
    *   **Flight Time**: Jeda waktu transisi antara melepaskan satu tombol dan menekan tombol berikutnya.
*   **Interval Metrics**:
    *   **Down-to-Down**: Interval waktu dari awal penekanan satu tombol hingga awal penekanan tombol berikutnya.
    *   **Up-to-Up**: Interval waktu dari pelepasan satu tombol hingga pelepasan tombol berikutnya.
*   **Advanced Behavioral Metrics**:
    *   **Rhythm Ratio**: Analisis konsistensi perbandingan durasi antar pasangan kunci untuk mengukur stabilitas irama mengetik.
    *   **Frequency Domain**: Menggunakan *Fast Fourier Transform* untuk mengekstraksi tanda tangan frekuensi ketikan, sangat efektif dalam membedakan antara operator manusia dan serangan bot otomatis.

---

<div align="center">

**Developed for Advanced Cybersecurity Research**  
*“In the world of Titanium Fusion, your password is no longer just what you know, but the unique rhythm of who you are.”*

[Report Bug](https://github.com/bmarzky/keystroke-login/issues) · [Request Feature](https://github.com/bmarzky/keystroke-login/issues)

</div>