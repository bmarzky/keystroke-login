<?php
session_start();

include "../../config/database.php";
include "../../core/biometrics.php";

$conn = getConnection();

// 1. Validasi Input Dasar
if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    redirectWithError("Form tidak lengkap");
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$inputKeystroke = trim($_POST['keystroke']);

// 2. Validasi Format JSON (Wajib ada d2d, u2u, dan speed sekarang)
$decodedInput = json_decode($inputKeystroke, true);
if (json_last_error() !== JSON_ERROR_NONE || !isset($decodedInput['speed'])) {
    redirectWithError("Data biometrik tidak valid atau rusak");
}

// 3. Ambil data user dari DB
$stmt = $conn->prepare("SELECT id, username, password FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

// Cek Password Statis Terlebih Dahulu
if ($user && password_verify($password, $user['password'])) {

    // Ambil data referensi (Gunakan LIMIT 20 agar perhitungan Mahalanobis tetap cepat)
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 20");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $result = $stmt->get_result();

    $allData = [];
    while ($row = $result->fetch_assoc()) {
        $allData[] = $row['features']; 
    }

    $dataCount = count($allData);
    
    // --- TAHAP 1: TRAINING PHASE ---
    // Gunakan konstanta MIN_SAMPLES dari biometrics.php agar sinkron
    if ($dataCount < MIN_SAMPLES) {
        $step = $dataCount + 1;
        processSuccessfulLogin($user, $conn, $inputKeystroke, "Training Mode ($step/".MIN_SAMPLES.")");
    }

    // --- TAHAP 2: VERIFIKASI BIOMETRIK ---
    $verification = verifyKeystroke($allData, $inputKeystroke); 
    
    // Logging Lengkap untuk Bahan Skripsi
    $logMsg = sprintf(
        "[%s] User: %s | Score: %.2f | Thresh: %.2f | Speed: %.2f CPM | Status: %s | Reason: %s\n",
        date('Y-m-d H:i:s'), 
        $username, 
        $verification['distance'], 
        $verification['threshold'],
        $decodedInput['speed'],
        $verification['status'] ? 'MATCH' : 'REJECT',
        $verification['reason'] ?? 'N/A'
    );
    file_put_contents('biometric_debug.log', $logMsg, FILE_APPEND);

    if ($verification['status'] === true) {
        // MATCH: Update profil biometrik dengan data terbaru
        processSuccessfulLogin($user, $conn, $inputKeystroke, "Verified");
    } else {
        // REJECT: Gagal Biometrik
        $reason = $verification['reason'] ?? "Pola tidak cocok";
        $errorMsg = "Akses Ditolak: $reason (Skor: " . round($verification['distance'], 2) . ")";
        redirectWithError($errorMsg);
    }

} else {
    redirectWithError("Username atau password salah");
}

// helper fuction
function redirectWithError($msg) {
    header("Location: ../login.php?error=" . urlencode($msg));
    exit();
}

function processSuccessfulLogin($user, $conn, $rawKeystroke, $status) {
    // Gunakan session_status() untuk memastikan session belum hancur
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }

    session_regenerate_id(true);
    $_SESSION['user_id'] = $user['id'];
    $_SESSION['username'] = $user['username'];
    $_SESSION['login_status'] = $status;

    // Simpan data baru untuk memperkaya dataset user (Continuous Authentication)
    $stmt = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmt->bind_param("is", $user['id'], $rawKeystroke);
    $stmt->execute();

    header("Location: ../../dashboard/index.php");
    exit();
}