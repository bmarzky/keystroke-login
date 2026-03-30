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

if (empty($username) || empty($password) || empty($keystroke) || json_decode($keystroke) === null) {
    header("Location: ../register.php?error=" . urlencode("Input data tidak lengkap atau rusak"));
    exit();
}

// Cek duplikasi username
$stmtCheck = $conn->prepare("SELECT id FROM users WHERE username = ?");
$stmtCheck->bind_param("s", $username);
$stmtCheck->execute();
$result = $stmtCheck->get_result();

if ($result->num_rows > 0) {
    header("Location: ../register.php?error=" . urlencode("Username sudah terdaftar"));
    exit();
}

$hashedPassword = password_hash($password, PASSWORD_DEFAULT);

// Simpan User Baru
$stmtInsert = $conn->prepare("INSERT INTO users (username, password) VALUES (?, ?)");
$stmtInsert->bind_param("ss", $username, $hashedPassword);

if ($stmtInsert->execute()) {
    $user_id = $conn->insert_id;

    // Simpan data keystroke pertama sebagai sampel awal
    $stmtKey = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmtKey->bind_param("is", $user_id, $keystroke);
    $stmtKey->execute();

    header("Location: ../login.php?success=" . urlencode("Registrasi berhasil! Silakan login"));
    exit();
} else {
    header("Location: ../register.php?error=" . urlencode("Gagal menyimpan data ke database"));
    exit();
}