<?php
session_start();

include "../../config/database.php";
include "../../core/biometrics.php";

$conn = getConnection();

// 1. Cek apakah data POST ada
if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    header("Location: ../login.php?error=" . urlencode("Form tidak lengkap"));
    exit();
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$inputKeystroke = trim($_POST['keystroke']);

// 2. Debugging jika keystroke kosong atau bukan JSON
if (empty($inputKeystroke)) {
    header("Location: ../login.php?error=" . urlencode("Data ketikan kosong (Cek JS)"));
    exit();
}

$decodedInput = json_decode($inputKeystroke, true);
if ($decodedInput === null) {
    header("Location: ../login.php?error=" . urlencode("Format data ketikan rusak"));
    exit();
}

// 3. Ambil data user
$stmt = $conn->prepare("SELECT * FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

if ($user && password_verify($password, $user['password'])) {

    // Ambil data referensi keystroke dari database
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ?");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $result = $stmt->get_result();

    $allData = [];
    while ($row = $result->fetch_assoc()) {
        if (!empty($row['features'])) {
            $allData[] = $row['features'];
        }
    }

    // Debug log
    file_put_contents('debug.log', "allData count: " . count($allData) . "\n", FILE_APPEND);

    // Jika data kurang dari 3, training phase: login otomatis tapi simpan data
    if (count($allData) < 3) {
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['username'] = $user['username'];

        $stmtInsert = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
        $stmtInsert->bind_param("is", $user['id'], $inputKeystroke);
        $stmtInsert->execute();

        header("Location: ../../dashboard/index.php");
        exit();
    }

    // Verifikasi keystroke dengan threshold tetap
    $verification = verifyKeystroke($allData, $inputKeystroke);

    // Debug log
    file_put_contents('debug.log', "score: " . $verification['distance'] . "\n", FILE_APPEND);

    if ($verification['distance'] < 7) { // threshold tetap yang lebih longgar
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['username'] = $user['username'];

        // Tambahkan data baru sebagai referensi
        $stmtInsert = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
        $stmtInsert->bind_param("is", $user['id'], $inputKeystroke);
        $stmtInsert->execute();

        header("Location: ../../dashboard/index.php");
        exit();
    } else {
        // Gagal: hapus session jika ada, lalu redirect
        session_unset();
        session_destroy();
        $errorMsg = "Pola ketikan tidak cocok (Skor: " . round($verification['distance'], 2) . ")";
        header("Location: ../login.php?error=" . urlencode($errorMsg));
        exit();
    }

} else {
    header("Location: ../login.php?error=" . urlencode("Username atau password salah"));
    exit();
}