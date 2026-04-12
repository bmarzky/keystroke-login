<?php
function getConnection() {
    $envPath = __DIR__ . '/../.env';

    if (!file_exists($envPath)) {
        die("File .env tidak ditemukan.");
    }

    $env = parse_ini_file($envPath);

    if (!$env) {
        die("Gagal membaca file .env.");
    }

    $conn = new mysqli(
        $env['DB_HOST'],
        $env['DB_USER'],
        $env['DB_PASS'],
        $env['DB_NAME']
    );

    if ($conn->connect_error) {
        die("Koneksi gagal: " . $conn->connect_error);
    }

    $conn->set_charset("utf8mb4");

    return $conn;
}
// End of DB configuration