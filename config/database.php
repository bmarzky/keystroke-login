<?php

class Database {
    private $conn;

    public function __construct() {
        $envPath = __DIR__ . '/../.env';

        if (!file_exists($envPath)) {
            die("File .env tidak ditemukan.");
        }

        $env = parse_ini_file($envPath);

        if (!$env || !isset($env['DB_HOST'], $env['DB_USER'], $env['DB_PASS'], $env['DB_NAME'])) {
            die("Gagal membaca file .env.");
        }

        try {
            $this->conn = new mysqli(
                $env['DB_HOST'],
                $env['DB_USER'],
                $env['DB_PASS'],
                $env['DB_NAME']
            );

            if ($this->conn->connect_error) {
                throw new Exception("Koneksi gagal: " . $this->conn->connect_error);
            }
            
            $this->conn->set_charset("utf8mb4");
        } catch (Exception $e) {
            die("Error koneksi database: " . $e->getMessage());
        }
    }

    public function getConnection() {
        return $this->conn;
    }
}