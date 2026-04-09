<?php
include "../../config/database.php";

$conn = getConnection();

if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    header("Location: ../register.php?error=" . urlencode("Akses tidak valid"));
    exit();
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$keystroke = trim($_POST['keystroke']);

// Decode untuk validasi konten
$decodedKeystroke = json_decode($keystroke, true);

if (empty($username) || empty($password) || empty($keystroke) || $decodedKeystroke === null) {
    header("Location: ../register.php?error=" . urlencode("Data registrasi tidak valid"));
    exit();
}

// Validasi tambahan: Pastikan semua fitur biometrik ada
if (!isset($decodedKeystroke['dwell'], $decodedKeystroke['speed'])) {
    header("Location: ../register.php?error=" . urlencode("Gagal mengambil data biometrik. Pastikan JS aktif."));
    exit();
}

// Cek duplikasi username
$stmtCheck = $conn->prepare("SELECT id FROM users WHERE username = ?");
$stmtCheck->bind_param("s", $username);
$stmtCheck->execute();
if ($stmtCheck->get_result()->num_rows > 0) {
    header("Location: ../register.php?error=" . urlencode("Username sudah terdaftar"));
    exit();
}

$hashedPassword = password_hash($password, PASSWORD_DEFAULT);

// Mulai Transaksi Database (Agar data user & keystroke tersimpan secara atomik)
$conn->begin_transaction();

try {
    // 1. Simpan User Baru
    $stmtInsert = $conn->prepare("INSERT INTO users (username, password) VALUES (?, ?)");
    $stmtInsert->bind_param("ss", $username, $hashedPassword);
    $stmtInsert->execute();
    $user_id = $conn->insert_id;

    // 2. Simpan data keystroke pertama sebagai sampel awal (Initial Profile)
    $stmtKey = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmtKey->bind_param("is", $user_id, $keystroke);
    $stmtKey->execute();

    // Commit jika keduanya berhasil
    $conn->commit();
    header("Location: ../login.php?success=" . urlencode("Registrasi berhasil! Pola biometrik awal telah disimpan."));
    exit();

} catch (Exception $e) {
    // Rollback jika ada salah satu yang gagal
    $conn->rollback();
    header("Location: ../register.php?error=" . urlencode("Sistem error: " . $e->getMessage()));
    exit();
}