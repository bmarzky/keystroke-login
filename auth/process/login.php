<?php
session_start();
date_default_timezone_set('Asia/Jakarta');

header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("X-XSS-Protection: 1; mode=block");

require_once __DIR__ . '/../../config/database.php';
require_once __DIR__ . '/../../engine/bridge.php';

// Inisialisasi Class OOP
$db = new Database();
$conn = $db->getConnection();
$biomManager = new KeystrokeManager();

function redirectWithError($msg) {
    header('Location: ../login.php?error=' . urlencode($msg));
    exit();
}

if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    redirectWithError("Form tidak lengkap");
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$inputKeystroke = trim($_POST['keystroke']);

// --- VALIDASI DATA INPUT ---
$keystrokeData = json_decode($inputKeystroke, true);
if (json_last_error() !== JSON_ERROR_NONE) {
    redirectWithError("Data biometrik tidak valid (JSON Error)");
}

// Pastikan field utama ada (dwell, flight)
if (!isset($keystrokeData['dwell']) || !isset($keystrokeData['flight']) || !is_array($keystrokeData['dwell'])) {
    redirectWithError("Struktur data biometrik tidak lengkap");
}

if (count($keystrokeData['dwell']) < 3) {
    redirectWithError("Data ketikan terlalu pendek, silakan coba lagi");
}

// 1. Cari User di Database
$stmt = $conn->prepare("SELECT id, username, password FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

if ($user && password_verify($password, $user['password'])) {
    
    // 2. Ambil data history untuk verifikasi biometrik
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 20");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $historyResult = $stmt->get_result();

    $history = [];
    while ($row = $historyResult->fetch_assoc()) {
        $history[] = $row['features']; 
    }

    // 3. Verifikasi Biometrik menggunakan OOP Class KeystrokeManager
    $result = $biomManager->verify($history, $inputKeystroke);
    
    $isMatch    = $result['status'];
    $score      = $result['score'];
    $thresh     = $result['threshold'];
    $reason     = $result['reason'];
    $method     = $result['method']     ?? 'Unknown';
    $nSamples   = $result['n_samples']  ?? 0;
    $mahalDist  = $result['mahal_dist'] !== null ? number_format($result['mahal_dist'], 4) : 'N/A';
    $speedDev    = $result['speed_dev']  !== null ? number_format($result['speed_dev'] * 100, 1) . '%' : 'N/A';
    $ipAddr      = $_SERVER['REMOTE_ADDR'] ?? 'N/A';
    $userAgent   = $_SERVER['HTTP_USER_AGENT'] ?? 'N/A';

    // Parse input JSON untuk ditampilkan di log
    $inputParsed = json_decode($inputKeystroke, true) ?? [];
    $dwellArr    = $inputParsed['dwell']  ?? [];
    $flightArr   = $inputParsed['flight'] ?? [];
    $d2dArr      = $inputParsed['d2d']    ?? [];
    $u2uArr      = $inputParsed['u2u']    ?? [];
    $inputSpeed  = isset($inputParsed['speed']) ? number_format($inputParsed['speed'], 4) : 'N/A';

    // Skor per-komponen (Titanium Fusion)
    $comp       = $result['components'] ?? [];
    $weights    = $result['weights'] ?? [];
    
    // Default fallback (fase stabil)
    $wRhythm = isset($weights['w_rhythm']) ? round($weights['w_rhythm'] * 100) : 40;
    $wCorr   = isset($weights['w_corr'])   ? round($weights['w_corr'] * 100) : 20;
    $wSpeed  = isset($weights['w_speed'])  ? round($weights['w_speed'] * 100) : 20;
    $wFlow   = isset($weights['w_flow'])   ? round($weights['w_flow'] * 100) : 20;
    $wRatio  = isset($weights['w_ratio'])  ? round($weights['w_ratio'] * 100) : 0;
    $wStab   = isset($weights['w_stability']) ? round($weights['w_stability'] * 100) : 0;

    $fmtComp    = function($v) { return $v !== null ? number_format($v * 100, 1) . '%' : 'N/A'; };
    $scoringBlock =
        "  --- Scoring Breakdown (Titanium Fusion) ---\n" .
        sprintf("  Rhythm    (%d%%) : %s  [Euclidean Distance]\n",  $wRhythm, $fmtComp($comp['rhythm']    ?? null)) .
        sprintf("  Corr.     (%d%%) : %s  [Pearson Coefficient]\n", $wCorr,   $fmtComp($comp['corr']      ?? null)) .
        sprintf("  Speed     (%d%%) : %s  [Global CPM]\n",          $wSpeed,  $fmtComp($comp['speed']     ?? null)) .
        sprintf("  Flow      (%d%%) : %s  [Acceleration]\n",        $wFlow,   $fmtComp($comp['flow']      ?? null)) .
        sprintf("  Ratio     (%d%%)  : %s  [Info Only - Handled by Mahalanobis]\n",  $wRatio, $fmtComp($comp['ratio']     ?? null)) .
        sprintf("  Stability (%d%%)  : %s  [Info Only - Handled by Mahalanobis]\n",  $wStab,  $fmtComp($comp['stability'] ?? null));

    $rawDataBlock =
        "  --- Raw Keystroke Data ---\n" .
        sprintf("  Speed         : %s char/s\n", $inputSpeed) .
        sprintf("  Dwell (%d)    : [%s]\n", count($dwellArr),  implode(', ', array_map(fn($v) => number_format($v, 3), $dwellArr))) .
        sprintf("  Flight (%d)   : [%s]\n", count($flightArr), implode(', ', array_map(fn($v) => number_format($v, 3), $flightArr))) .
        sprintf("  D2D (%d)      : [%s]\n", count($d2dArr),    implode(', ', array_map(fn($v) => number_format($v, 3), $d2dArr))) .
        sprintf("  U2U (%d)      : [%s]\n", count($u2uArr),    implode(', ', array_map(fn($v) => number_format($v, 3), $u2uArr)));


    // Adaptive Gates
    $ag          = $result['adaptive_gates'] ?? [];
    $gatesBlock  = "  --- Adaptive Gates (Per-User) ---\n";
    $gatesBlock .= sprintf("  Speed Gate    : %.1f%%\n", ($ag['speed_gate'] ?? 0.40) * 100);
    $gatesBlock .= sprintf("  Mahal. Gate   : %.4f\n",    $ag['mahal_gate'] ?? 3.0);
    $gatesBlock .= sprintf("  Threshold     : %.4f\n",    $ag['threshold']  ?? 0.70);

    if (isset($ag['dtw_dwell']) && $ag['dtw_dwell'] !== null) {
        $gatesBlock .= sprintf("  DTW Dwell     : %.3f\n", $ag['dtw_dwell']);
        $gatesBlock .= sprintf("  DTW Flight    : %.3f\n", $ag['dtw_flight']);
        $gatesBlock .= sprintf("  Typo Recovery : Yes\n");
    }
    if (isset($ag['outlier_count']) && $ag['outlier_count'] > 0) {
        $gatesBlock .= sprintf("  Removed Keys  : %d keys (Sterile)\n", $ag['outlier_count']);
    }

    // 4. Format Log
    $LOG_DIR = __DIR__ . '/../../ml/logs/';

    $logHeader = sprintf(
        "[%s]\n" .
        "  User          : %s (ID: %d)\n" .
        "  IP Address    : %s\n" .
        "  User-Agent    : %s\n" .
        "  Method        : %s\n" .
        "  History Count : %d sampel\n" .
        "  Score         : %.4f\n" .
        "  Threshold     : %.4f\n" .
        "  Speed Dev     : %s\n" .
        "  Mahal. Dist   : %s\n" .
        "  Reason        : %s\n",
        date('Y-m-d H:i:s'),
        $username, $user['id'],
        $ipAddr,
        $userAgent,
        $method,
        $nSamples,
        $score,
        $thresh,
        $speedDev,
        $mahalDist,
        $reason
    );


    if ($isMatch) {
        // Login Sukses
        session_unset();
        session_regenerate_id(true);
        $_SESSION['user_id']  = $user['id'];
        $_SESSION['username'] = $user['username'];

        // Simpan data jika diperintahkan oleh engine (Anti-Poisoning)
        $historyUpdated = false;
        if ($result['should_update']) {
            $stmt = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
            $stmt->bind_param("is", $user['id'], $inputKeystroke);
            $stmt->execute();
            $historyUpdated = true;
        }

        $successLog = $logHeader .
            sprintf("  History Updated: %s\n", $historyUpdated ? 'Ya (anti-poisoning lolos)' : 'Tidak') .
            $gatesBlock .
            $scoringBlock .
            $rawDataBlock .
            str_repeat("-", 60) . "\n";





        file_put_contents($LOG_DIR . 'login_success.log', $successLog, FILE_APPEND);

        header("Location: ../../dashboard/index.php");
        exit();

    } else {
        // Login Gagal Biometrik
        $failLog = $logHeader .
            $gatesBlock .
            $scoringBlock .
            $rawDataBlock .
            str_repeat("-", 60) . "\n";





        file_put_contents($LOG_DIR . 'login_failed.log', $failLog, FILE_APPEND);

        redirectWithError("Akses Ditolak: Pola ketikan tidak cocok (Skor: $score)");
    }

} else {
    redirectWithError("Username atau password salah");
}