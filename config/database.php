<?php
function getConnection() {
    $envPath = __DIR__ . '/../.env';

    if (!file_exists($envPath)) {
        die("File .env tidak ditemukan. Salin .env.example dan sesuaikan kredensial database Anda.");
    }

    $env = parse_ini_file($envPath);

    if (!$env || !isset($env['DB_HOST'], $env['DB_USER'], $env['DB_PASS'], $env['DB_NAME'])) {
        die("Gagal membaca file .env. Pastikan format benar dan file berisi DB_HOST, DB_USER, DB_PASS, DB_NAME.");
    }

    try {
        $conn = new mysqli(
            $env['DB_HOST'],
            $env['DB_USER'],
            $env['DB_PASS'],
            $env['DB_NAME']
        );

        if ($conn->connect_error) {
            throw new Exception("Koneksi gagal: " . $conn->connect_error);
        }
    } catch (Exception $e) {
        die("Error koneksi database: " . $e->getMessage());
    }

    $conn->set_charset("utf8mb4");

    return $conn;
}
// End of DB configuration