# Keystroke Login System

Sistem autentikasi login berbasis biometrik keystroke menggunakan PHP, MySQL, dan JavaScript. Sistem ini menganalisis pola penekanan tombol keyboard pengguna untuk verifikasi identitas, memberikan lapisan keamanan tambahan selain password tradisional.

## Fitur

- **Registrasi Pengguna**: Pengguna dapat mendaftar dengan username, password, dan pola keystroke unik.
- **Login dengan Keystroke**: Verifikasi identitas melalui analisis waktu penekanan dan jeda antar tombol.
- **Dashboard**: Halaman aman setelah login berhasil.
- **Biometrik Keystroke**: Menggunakan JavaScript untuk capture data keystroke secara real-time.
- **Database MySQL**: Penyimpanan data pengguna dan pola keystroke.

## Prasyarat

- **XAMPP** (atau server web dengan PHP dan MySQL)
- **PHP 7.4+**
- **MySQL 5.7+**
- Browser web modern dengan JavaScript aktif

## Instalasi

1. **Clone Repository**:
   ```
   git clone https://github.com/bmarzky/keystroke-login.git
   cd keystroke-login
   ```

2. **Setup XAMPP**:
   - Salin folder `keystroke-login` ke `C:\xampp\htdocs\`.
   - Jalankan XAMPP Control Panel dan start Apache serta MySQL.

3. **Konfigurasi Database**:
   - Buka phpMyAdmin (http://localhost/phpmyadmin).
   - Buat database baru (misalnya, `keystroke_db`).
   - Import file `database/keystroke.sql` ke database tersebut.
   - Edit `config/database.php` untuk menyesuaikan kredensial database:
     ```php
     $host = 'localhost';
     $db = 'keystroke_db'; // Ganti sesuai nama database Anda
     $user = 'root';
     $pass = '';
     ```

4. **Jalankan Aplikasi**:
   - Buka browser dan akses `http://localhost/keystroke-login`.

## Penggunaan

1. **Registrasi**:
   - Akses `auth/register.php`.
   - Isi username, password, dan ketik password beberapa kali untuk capture pola keystroke.
   - Klik "Register".

2. **Login**:
   - Akses `auth/login.php`.
   - Masukkan username dan ketik password dengan pola keystroke yang sama seperti saat registrasi.
   - Sistem akan verifikasi berdasarkan biometrik keystroke.

3. **Dashboard**:
   - Setelah login berhasil, Anda akan diarahkan ke `dashboard/index.php`.

## Struktur Proyek

```
keystroke-login/
├── assets/
│   ├── css/
│   │   └── style.css          # Styling untuk UI
│   └── js/
│       └── keystroke.js       # Script untuk capture keystroke
├── auth/
│   ├── login.php              # Halaman login
│   └── register.php           # Halaman registrasi
├── process/
│   ├── login.php              # Proses login
│   ├── logout.php             # Proses logout
│   └── register.php           # Proses registrasi
├── config/
│   └── database.php           # Konfigurasi database
├── core/
│   └── biometrics.php         # Logika biometrik keystroke
├── dashboard/
│   └── index.php              # Halaman dashboard
├── database/
│   └── keystroke.sql          # Schema database
├── index.php                  # Entry point utama
└── README.md                  # Dokumentasi ini
```

## Kontribusi

Kontribusi sangat diterima! Silakan fork repository ini, buat branch fitur baru, dan kirim pull request.

1. Fork repository.
2. Buat branch fitur: `git checkout -b fitur-baru`.
3. Commit perubahan: `git commit -m 'Tambah fitur baru'`.
4. Push ke branch: `git push origin fitur-baru`.
5. Buat Pull Request.

## Kontak

Jika ada pertanyaan, hubungi [bmarzky](https://github.com/bmarzky).