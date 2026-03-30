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

    // Login otomatis jika data referensi masih sedikit (Tahap Training)
    if (count($allData) < 3) {
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['username'] = $user['username'];

        $stmtInsert = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
        $stmtInsert->bind_param("is", $user['id'], $inputKeystroke);
        $stmtInsert->execute();

        header("Location: ../../dashboard/index.php");
        exit();
    }

    // 4. Hitung Skor Biometrik
    $score = compareMultipleKeystroke($allData, $inputKeystroke);
    $threshold = 180; // Ubah angka ini jika terlalu sulit login (misal ke 300 atau 500)

    if ($score < $threshold) {
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['username'] = $user['username'];

        // Tambahkan data baru sebagai referensi tambahan
        $stmtInsert = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
        $stmtInsert->bind_param("is", $user['id'], $inputKeystroke);
        $stmtInsert->execute();

        header("Location: ../../dashboard/index.php");
        exit();
    } else {
        // Gagal karena pola tidak cocok, tampilkan skor di URL untuk bahan skripsi
        $errorMsg = "Pola ketikan tidak cocok (Skor: " . round($score, 2) . ")";
        header("Location: ../login.php?error=" . urlencode($errorMsg));
        exit();
    }

} else {
    header("Location: ../login.php?error=" . urlencode("Username atau password salah"));
    exit();
}