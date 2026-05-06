# Biometric Authentication System Login

[![Version](https://img.shields.io/badge/version-2.5.0--stable-blue.svg)](https://github.com/bmarzky/keystroke-login)
[![Security](https://img.shields.io/badge/Security-Titanium--Fusion-critical.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.12-brightgreen.svg)](https://www.python.org/)

Sistem autentikasi biometrik perilaku (*behavioral biometrics*) mutakhir yang mengenali pengguna berdasarkan pola unik ketikan jari mereka. Dikembangkan untuk riset keamanan siber tingkat lanjut, sistem ini menggabungkan analisis statistik multivariat dengan *Machine Learning* untuk menciptakan lapisan pertahanan kedua yang hampir mustahil dipalsukan.

---

## Arsitektur Keamanan: Titanium Fusion Engine

Sistem ini tidak hanya mengandalkan satu metrik, melainkan menggunakan pendekatan **Multi-Layered Defense** yang disebut **Titanium Fusion**:

1.  **Structural Gate (DTW Recovery)**: Memvalidasi integritas struktur ketikan. Menggunakan algoritma *Dynamic Time Warping* (DTW) untuk mentoleransi kesalahan ketik ringan (*typos*) tanpa mengorbankan profil biometrik.
2.  **Statistical Gate (Mahalanobis Distance)**: Menghitung jarak statistik antara input saat ini dengan distribusi historis pengguna. Gerbang ini sangat efektif mendeteksi anomali pada fitur-fitur yang saling berkorelasi.
3.  **AI Layer (One-Class SVM)**: Menggunakan model *One-Class Support Vector Machine* untuk mendeteksi anomali secara *real-time*. Model ini dilatih secara otomatis setelah pengguna memiliki 20 sampel data.
4.  **Forgiver Logic (Adaptive Speed)**: Logika cerdas yang mampu membedakan antara "perubahan kecepatan karena faktor manusia" (misal: lelah atau terburu-buru) dengan "upaya impersonasi" berdasarkan konsistensi pola ritme.
5.  **Dynamic Weighting**: Untuk profil yang sudah mapan (*Mature Profiles*, n ≥ 15), sistem secara otomatis menyesuaikan bobot (weights) pada setiap metrik (Rhythm, Corr, Speed, Flow, Ratio, Stability) berdasarkan komponen mana yang paling stabil pada pengguna tersebut.

---

## Fitur Utama

-   **Adaptive Thresholding**: Ambang batas keamanan yang belajar dan mengeras secara otomatis seiring bertambahnya jumlah sampel (n < 5: Longgar, n > 50: Sangat Ketat).
-   **Replay Attack Protection**: Memblokir upaya login menggunakan data biometrik yang disalin (copy-paste) melalui validasi redundansi data.
-   **Biometric Audit Trail**: Pencatatan log teknis yang sangat detail (Dwell Time, Flight Time, Mahalanobis Distance, AI Confidence Score) untuk kebutuhan forensik dan analisis riset.
-   **Automated AI Training**: Sistem melakukan *background training* model OCSVM setiap kelipatan 20 login sukses untuk memastikan model selalu akurat.
-   **Interactive Dashboard**: Visualisasi performa mengetik, stabilitas, dan perbandingan pola ketikan terakhir.

---

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
├── app.py                     # Entry point: Flow autentikasi & Session management
├── requirements.txt           # Dependensi library (Flask, Sklearn, Numpy, etc.)
├── .env                       # Konfigurasi database & Secret keys
│
├── engine/                    # Inti Kecerdasan Biometrik
│   ├── core.py                # Titanium Fusion Engine (Logic Utama)
│   └── ml/                    # AI Environment
│       ├── ai_engine.py       # Inferensi OCSVM
│       ├── ai_trainer.py      # Background trainer model AI
│       └── models/            # Storage model *.joblib per user
│
├── logs/                      # Audit Trail (Forensik Biometrik)
│   ├── login_success.log      # Detil data biometrik yang diterima
│   └── login_failed.log       # Alasan penolakan (Speed, Mahal, or Score)
│
├── static/                    # Frontend Assets (Collector & UI)
├── templates/                 # Jinja2 Layouts (Auth & Dashboard)
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

## Metrik yang Dianalisis (24 Dimensi)

Sistem mengekstraksi 24 fitur unik dari setiap sesi login:
-   **Hold Time (Dwell)**: Durasi penekanan tombol.
-   **Flight Time**: Jeda antar penekanan tombol.
-   **D2D (Down-to-Down)**: Interval dari satu tombol ditekan ke tombol berikutnya.
-   **U2U (Up-to-Up)**: Interval dari satu tombol dilepas ke tombol berikutnya dilepas.
-   **Rhythm Ratio**: Keajegan ritme antar pasangan kunci.
-   **FFT (Fast Fourier Transform)**: Tanda tangan frekuensi dari pola ketikan untuk mendeteksi otomatisasi (bot).

---

**Dikembangkan untuk Riset Keamanan Siber Tingkat Lanjut.**
*Titanium Fusion: Because your password is not just what you know, but how you type it.*