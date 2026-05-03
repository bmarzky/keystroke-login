# Smart Guard: AI-Driven Keystroke Biometric Authentication

Sistem autentikasi biometrik perilaku (*behavioral biometrics*) yang sangat aman dan cerdas, dikembangkan sepenuhnya menggunakan **Python (Flask)**. Sistem ini mengenali pengguna berdasarkan pola unik ketikan jari mereka (ritme, kecepatan, dan tekanan) menggunakan algoritma **Titanium Fusion Engine**.

---

## Fitur Utama

1. **Titanium Fusion Engine**: Mesin skor yang menggabungkan 6 metrik (Rhythm, Correlation, Speed, Flow, Ratio, Stability).
2. **Mahalanobis Gate**: Gerbang statistik tingkat tinggi untuk memverifikasi kedekatan data terhadap profil historis.
3. **OCSVM AI Layer**: Deteksi anomali real-time menggunakan model *One-Class Support Vector Machine* untuk keamanan ekstra.
4. **Adaptive Thresholding**: Ambang batas yang belajar dan beradaptasi secara otomatis mengikuti perkembangan gaya ketik pengguna.
5. **Secure Core**: Dilengkapi perlindungan terhadap serangan *Replay* dan pengarsipan log teknis yang sangat mendetail.

---

## Tech Stack

- **Backend**: Python 3.12, Flask Framework
- **Database**: MySQL (MariaDB)
- **Machine Learning**: Scikit-learn (OCSVM), Numpy
- **Keamanan**: Bcrypt Hashing, Session Encryption
- **Frontend**: Jinja2 Templates, Vanilla CSS & JS

---

## Struktur Proyek (Mendetail)

```text
keystroke-login/
├── app.py                     # Entry point aplikasi: Menangani routing, session, dan flow autentikasi.
├── .env                       # File konfigurasi sensitif (DB Credentials, Secret Keys).
├── .htaccess                  # Konfigurasi Apache Reverse Proxy untuk integrasi dengan XAMPP.
├── requirements.txt           # Daftar dependensi library Python yang diperlukan.
│
├── config/
│   └── database.py            # Logika koneksi Database MySQL menggunakan mysql-connector.
│
├── engine/
│   └── core.py                # Core Biometric Engine: Menghitung Fusion Score, Mahalanobis Distance, 
│                                dan Adaptive Thresholding.
│
├── ml/                        # Lingkungan Machine Learning
│   ├── ai_trainer.py          # Script untuk melatih model OCSVM berdasarkan data historis pengguna.
│   ├── ai_engine.py           # Komponen inferensi AI untuk memprediksi anomali ketikan.
│   ├── models/                # Penyimpanan Model AI (*.joblib) yang unik untuk setiap user.
│   └── logs/                  # Audit trail biometric:
│       ├── login_success.log  # Detail teknis login yang diterima (skor fusion, AI status, dll).
│       └── login_failed.log   # Analisis penyebab login ditolak (skor rendah, AI caution, dll).
│
├── static/                    # Aset Statis Frontend
│   ├── css/                   # Desain antarmuka (Modern & Responsive).
│   └── js/                    # Keystroke Collector: Menangkap timing dwell & flight time secara real-time.
│
├── templates/                 # Template HTML (Jinja2 Engine)
│   ├── auth/                  # Halaman Login & Registrasi.
│   └── dashboard/             # Antarmuka setelah user berhasil masuk.
│
├── utils/
│   └── logger.py              # Utility untuk mencatat log biometrik Titanium Fusion yang mendetail.
│
└── scratch/                   # Folder sementara untuk proses pengolahan data training AI.
```


---

## Cara Instalasi & Menjalankan

### 1. Prasyarat
- Pastikan MySQL (XAMPP) sudah berjalan.
- Buat database bernama `keystroke_db`.

### 2. Instalasi Dependensi
Jalankan perintah berikut di terminal:
```powershell
pip install -r requirements.txt
```

### 3. Konfigurasi Environment
Edit file `.env` dan sesuaikan dengan kredensial database Anda:
```env
DB_HOST=localhost
DB_USER=root
DB_PASS=
DB_NAME=keystroke_db
```

### 4. Menjalankan Aplikasi
Jalankan server Flask:
```powershell
python app.py
```
Akses sistem melalui browser di: `http://127.0.0.1:8000`

---

## Logika Keamanan

Sistem menggunakan alur verifikasi berlapis:
1. **Password Match**: Verifikasi password standar (Bcrypt).
2. **Replay Check**: Memastikan data biometrik bukan hasil *copy-paste*.
3. **Statistical Gate**: Analisis jarak Mahalanobis.
4. **AI Decision**: Skor kepercayaan dari model OCSVM.
5. **Final Decision**: Pengambilan keputusan akhir berdasarkan *Adaptive Threshold*.

---

**Developed with Love for Advanced Cybersecurity Research.**