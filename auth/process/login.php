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

// 2. Validasi Format JSON
if (empty($inputKeystroke)) {
    redirectWithError("Data ketikan kosong (Cek JS)");
}

$decodedInput = json_decode($inputKeystroke, true);
if (json_last_error() !== JSON_ERROR_NONE) {
    redirectWithError("Format data ketikan rusak");
}

// 3. Ambil data user dari DB
$stmt = $conn->prepare("SELECT id, username, password FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

if ($user && password_verify($password, $user['password'])) {

    // Ambil maksimal 20 data referensi terbaru (Moving Window)
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 20");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $result = $stmt->get_result();

    $allData = [];
    while ($row = $result->fetch_assoc()) {
        if (!empty($row['features'])) {
            // Biarkan dalam bentuk string JSON karena verifyKeystroke() mengekspektasikan string
            $allData[] = $row['features']; 
        }
    }

    $dataCount = count($allData);
    
    // --- TAHAP 1: TRAINING PHASE (Data < 3) ---
    if ($dataCount < 3) {
        processSuccessfulLogin($user, $conn, $inputKeystroke, "Training Mode");
    }

    // --- TAHAP 2: VERIFIKASI DATA INPUT ---
    // Fungsi verifyKeystroke di biometrics.php sudah otomatis menghitung threshold adaptif!
    $verification = verifyKeystroke($allData, $inputKeystroke); 
    $currentDistance = $verification['distance'];
    $adaptiveThreshold = $verification['threshold'] ?? 0;

    // Logging untuk analisa/keperluan skripsi
    $logMsg = sprintf(
        "[%s] User: %s | Score: %.2f | Thresh: %.2f\n",
        date('Y-m-d H:i:s'), $username, $currentDistance, $adaptiveThreshold
    );
    file_put_contents('biometric_debug.log', $logMsg, FILE_APPEND);

    // Bandingkan skor dengan status hasil verifikasi biometrics.php
    if ($verification['status'] === true) {
        processSuccessfulLogin($user, $conn, $inputKeystroke, "Verified");
    } else {
        // Gagal Biometrik
        session_unset();
        session_destroy();
        
        // Memunculkan info skor dan threshold agar mudah saat sidang/presentasi
        $errorMsg = "Pola ketikan tidak cocok (Skor: " . round($currentDistance, 2) . " > Limit: " . round($adaptiveThreshold, 2) . ")";
        redirectWithError($errorMsg);
    }

} else {
    redirectWithError("Username atau password salah");
}

/**
 * HELPER FUNCTIONS
 */
function redirectWithError($msg) {
    header("Location: ../login.php?error=" . urlencode($msg));
    exit();
}

function processSuccessfulLogin($user, $conn, $rawKeystroke, $status) {
    session_regenerate_id(true);
    $_SESSION['user_id'] = $user['id'];
    $_SESSION['username'] = $user['username'];
    $_SESSION['login_status'] = $status;

    // Simpan data baru untuk memperkaya dataset user
    $stmt = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmt->bind_param("is", $user['id'], $rawKeystroke);
    $stmt->execute();

    header("Location: ../../dashboard/index.php");
    exit();
}