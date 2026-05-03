<?php
require_once __DIR__ . '/../../config/database.php';

$db = new Database();
$conn = $db->getConnection();

if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    header("Location: ../register.php?error=" . urlencode("Akses tidak valid"));
    exit();
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$keystroke = trim($_POST['keystroke']);

$decoded = json_decode($keystroke, true);

if (empty($username) || empty($password) || empty($keystroke) || $decoded === null) {
    header("Location: ../register.php?error=" . urlencode("Data tidak valid."));
    exit();
}

// Validasi Panjang Biometrik (Sesuai dengan Login)
if (count($decoded['dwell']) < 7) {
    header("Location: ../register.php?error=" . urlencode("Password terlalu pendek untuk biometrik. Gunakan minimal 7 karakter."));
    exit();
}

// Cek duplikasi
$stmt = $conn->prepare("SELECT id FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
if ($stmt->get_result()->num_rows > 0) {
    header("Location: ../register.php?error=" . urlencode("Username sudah terdaftar"));
    exit();
}

$hashed = password_hash($password, PASSWORD_DEFAULT);

$conn->begin_transaction();
try {
    // 1. Simpan User
    $stmt = $conn->prepare("INSERT INTO users (username, password) VALUES (?, ?)");
    $stmt->bind_param("ss", $username, $hashed);
    $stmt->execute();
    $uid = $conn->insert_id;

    // 2. Simpan Biometrik Awal
    $stmt = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmt->bind_param("is", $uid, $keystroke);
    $stmt->execute();

    $conn->commit();
    header("Location: ../login.php?success=" . urlencode("Registrasi berhasil!"));
    exit();
} catch (Exception $e) {
    $conn->rollback();
    header("Location: ../register.php?error=" . urlencode("Error: " . $e->getMessage()));
    exit();
}