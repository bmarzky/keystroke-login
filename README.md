# Keystroke Biometric Login System (Titanium Edition)

Sistem autentikasi login mutakhir yang menggabungkan keamanan password tradisional dengan lapisan biometrik perilaku (*behavioral biometrics*) berbasis pola pengetikan. Sistem ini menggunakan **Titanium Scoring Engine** yang diperkuat oleh algoritma **Mahalanobis Distance** dan Machine Learning (One Class SVM) untuk membedakan pengguna asli dengan penyusup (*imposter*) melalui analisis multidimensi terhadap ritme, kecepatan, stabilitas, dan akselerasi pengetikan.

## Fitur Unggulan

- **Titanium Scoring Engine**: Mesin penilaian komposit yang menggabungkan 6 metrik keamanan utama:
    - **Rhythm Score (Euclidean)**: Analisis jarak Euclidean pada 4 spektrum data (Dwell, Flight, D2D, U2U).
    - **Correlation Score (Pearson)**: Mengukur kemiripan bentuk gelombang (*waveform*) pola pengetikan.
    - **Speed Score**: Validasi kecepatan mengetik global terhadap rata-rata historis.
    - **Ratio Score (Finger Anatomy)**: Analisis rasio *dwell-to-flight* yang unik untuk setiap struktur tangan.
    - **Stability Score (Jitter Analysis)**: Mengukur konsistensi varians/getaran pengetikan.
    - **Flow Score (Transitional Acceleration)**: Analisis korelasi pada percepatan antar tombol (perubahan ritme).
- **Hybrid AI Layer**:
    - **Early Stage (Data < 5)**: Menggunakan *Soft Scoring Fusion* yang pemaaf namun tetap aman untuk *cold start*.
    - **Production Stage (Data ≥ 5)**: Mengaktifkan **Mahalanobis Distance** berbasis *Covariance Matrix* untuk mendeteksi anomali korelasi fitur yang kompleks.
- **Adaptive Learning (Anchor + Drift)**:
    - Sistem secara cerdas memilih data "Jangkar" (2 data awal) dan data "Adaptasi" (3 data terbaru) sebagai pembanding.
    - Menjamin sistem tetap akurat meskipun gaya mengetik pengguna berubah perlahan seiring waktu (*drift adaptation*).
- **Dynamic Gate System**: Perlindungan *real-time* yang langsung memblokir percobaan login jika deviasi kecepatan melampaui ambang batas keamanan (40%) bahkan sebelum analisis AI dilakukan.
- **Anti-Poisoning Guard**: Mekanisme perlindungan yang mencegah pembaruan data biometrik jika skor login dianggap "mencurigakan" atau "pas-pasan", guna mencegah penyusup merusak profil asli pengguna.
- **Auto-Aligning Truncation**: Penanganan otomatis terhadap variasi jumlah tombol (seperti tombol 'Enter' tambahan atau jeda akhir) agar perbandingan data tetap presisi.

## Prasyarat

- **Web Server**: Apache (XAMPP/Laragon) dengan PHP 7.4+
- **Database**: MySQL 5.7+
- **Python Runtime**: Python 3.8+
- **Python Libraries**: `numpy`, `scipy`, `scikit-learn`
- **Environment**: File `.env` untuk konfigurasi database.

## Instalasi

1. **Clone Repository**:
   ```bash
   git clone https://github.com/bmarzky/keystroke-login.git
   cd keystroke-login
   ```

2. **Setup Database**:
   - Import `database/keystroke.sql` menggunakan phpMyAdmin.
   - Buat file `.env` di root folder:
     ```ini
     DB_HOST=localhost
     DB_USER=root
     DB_PASS=
     DB_NAME=keystroke_db
     ```

3. **Install Python Dependencies**:
   ```bash
   pip install -r ml/requirements.txt
   ```

## Cara Kerja (Titanium Scoring)

1.  **Capture**: JavaScript (`keystroke.js`) menangkap waktu *Dwell* (tekan-lepas) dan *Flight* (lepas-tekan) secara presisi di sisi klien.
2.  **Pre-Process**: Data dikirim ke PHP dan diteruskan ke mesin Python (`mahalanobis.py`).
3.  **Heuristic Fusion**: Sistem menghitung skor dari 6 dimensi biometrik terhadap multi-baseline (Anchor & Drift).
4.  **AI Blending**: Jika sampel cukup, sistem menggabungkan 80% skor Heuristik dengan 20% skor Mahalanobis AI.
5.  **Decision**: Jika total skor ≥ Threshold (misal: 0.63-0.70), login diizinkan (**ACCEPT**).
6.  **Adaptive Update**: Jika skor sangat meyakinkan (> 0.75), profil biometrik pengguna akan diperbarui secara otomatis.

## Struktur Proyek

```text
keystroke-login/
├── assets/             # Frontend assets (CSS, JS)
├── auth/               # Authentication UI & process
├── config/             # Database connection & env config
├── database/           # SQL migration files
├── engine/             # Biometric Core Logic (PHP & Python)
│   ├── bridge.php      # PHP-Python Bridge
│   ├── core.py         # Titanium Scoring Engine
│   ├── predictor.py    # SVM Prediction script
│   └── trainer.py      # Background AI training
├── ml/                 # Machine Learning Artifacts
│   ├── logs/           # Predicition & system logs
│   └── models/         # Trained .pkl models
├── .env                # Environment variables
├── index.php           # Landing & routing
└── README.md           # Documentation
```

## Lisensi

Proyek ini menggunakan lisensi **MIT**. Bebas digunakan untuk keperluan edukasi maupun komersial dengan tetap mencantumkan atribusi.

---
**Maintained by [bmarzky](https://github.com/bmarzky)**