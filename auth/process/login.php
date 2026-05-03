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

if (count($keystrokeData['dwell']) < 7) {
    redirectWithError("Data biometrik terlalu pendek (Min. 7 karakter), silakan gunakan password yang lebih panjang untuk keamanan biometrik.");
}

// 1. Cari User di Database
$stmt = $conn->prepare("SELECT id, username, password FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

if ($user && password_verify($password, $user['password'])) {
    
    // 2. Ambil seluruh data history untuk verifikasi biometrik yang lebih akurat (Penting untuk OCSVM)
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id ASC");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $historyResult = $stmt->get_result();

    $history = [];
    $isReplay = false;
    // Gunakan normalisasi JSON untuk perbandingan replay
    $currentClean = json_encode(json_decode($inputKeystroke, true));

    while ($row = $historyResult->fetch_assoc()) {
        $history[] = $row['features'];
        // Replay Detection: Bandingkan input sekarang dengan data history
        if (!$isReplay && json_encode(json_decode($row['features'], true)) === $currentClean) {
            $isReplay = true;
        }
    }

    if ($isReplay) {
        // Log serangan replay
        $logDir = __DIR__ . '/../../ml/logs/';
        if (!is_dir($logDir)) mkdir($logDir, 0777, true);
        $header = "REPLAY ATTACK | User: $username";
        $content = "  Detection: 100% Timing Match Found in History\n" .
                   "  Action   : Blocked Immediately\n" .
                   "  IP       : " . ($_SERVER['REMOTE_ADDR'] ?? 'N/A') . "\n";
        file_put_contents($logDir . 'login_failed.log', "------------------------------------------------------------\n$header\n$content", FILE_APPEND);

        redirectWithError("Keamanan: Terdeteksi serangan Replay (Timing Identik). Akses Ditolak.");
    }

    // 3. Verifikasi Biometrik menggunakan OOP Class KeystrokeManager
    $result = $biomManager->verify($history, $inputKeystroke, $username, $user['id']);
    
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
        "  --- Titanium Fusion Gate ---\n" .
        sprintf("  Rhythm    (%d%%) : %s  [Euclidean Distance]\n",  $wRhythm, $fmtComp($comp['rhythm']    ?? null)) .
        sprintf("  Corr.     (%d%%) : %s  [Pearson Coefficient]\n", $wCorr,   $fmtComp($comp['corr']      ?? null)) .
        sprintf("  Speed     (%d%%) : %s  [Global CPM]\n",          $wSpeed,  $fmtComp($comp['speed']     ?? null)) .
        sprintf("  Flow      (%d%%) : %s  [Acceleration]\n",        $wFlow,   $fmtComp($comp['flow']      ?? null)) .
        sprintf("  Ratio     (%d%%)  : %s\n",  $wRatio, $fmtComp($comp['ratio']     ?? null)) .
        sprintf("  Stability (%d%%)  : %s\n",  $wStab,  $fmtComp($comp['stability'] ?? null));

    $rawDataBlock =
        "  --- Raw Keystroke Data ---\n" .
        sprintf("  Speed         : %s char/s\n", $inputSpeed) .
        sprintf("  Dwell (%d)    : [%s]\n", count($dwellArr),  implode(', ', array_map(fn($v) => number_format($v, 3), $dwellArr))) .
        sprintf("  Flight (%d)   : [%s]\n", count($flightArr), implode(', ', array_map(fn($v) => number_format($v, 3), $flightArr))) .
        sprintf("  D2D (%d)      : [%s]\n", count($d2dArr),    implode(', ', array_map(fn($v) => number_format($v, 3), $d2dArr))) .
        sprintf("  U2U (%d)      : [%s]\n", count($u2uArr),    implode(', ', array_map(fn($v) => number_format($v, 3), $u2uArr)));


    // Adaptive Gates
    $ag          = $result['adaptive_gates'] ?? [];
    $gatesBlock  = "  --- Adaptive Gate ---\n";
    $gatesBlock .= sprintf("  Speed Gate    : %.1f%%\n", ($ag['speed_gate'] ?? 0.40) * 100);
    $gatesBlock .= sprintf("  Threshold     : %.4f\n",    $ag['threshold']  ?? 0.70);

    if (isset($ag['dtw_dwell']) && $ag['dtw_dwell'] !== null) {
        $gatesBlock .= sprintf("  DTW Dwell     : %.3f\n", $ag['dtw_dwell']);
        $gatesBlock .= sprintf("  DTW Flight    : %.3f\n", $ag['dtw_flight']);
        $gatesBlock .= sprintf("  Typo Recovery : Yes\n");
    }
    if (isset($ag['outlier_count']) && $ag['outlier_count'] > 0) {
        $gatesBlock .= sprintf("  Removed Keys  : %d keys (Sterile)\n", $ag['outlier_count']);
    }

    // Mahalanobis Section
    $mahalBlock = "  --- Mahalanobis Gate ---\n";
    $mahalBlock .= sprintf("  Distance      : %s\n", $mahalDist);
    $mahalBlock .= sprintf("  Current Gate  : %.4f\n", $ag['mahal_gate'] ?? 8.0);

    // 4. Finalize & Log (Integrated Logger)
    $logDir = __DIR__ . '/../../ml/logs/';
    if (!is_dir($logDir)) mkdir($logDir, 0777, true);

    $writeLog = function($filename, $header, $content) use ($logDir) {
        $divider = str_repeat("-", 60) . "\n";
        $data = "$header\n$content" . (substr($content, -1) !== "\n" ? "\n" : "") . $divider;
        file_put_contents($logDir . $filename, $data, FILE_APPEND);
    };

    // Format AI Section
    $aiBlock = "";
    if (isset($result['ai_status'])) {
        $aiBlock  = "  --- OCSVM Gate ---\n";
        $aiBlock .= sprintf("  AI Score      : %s\n",   (isset($result['ai_score']) && $result['ai_score'] !== null) ? number_format($result['ai_score'], 4) : 'N/A');
        $aiBlock .= sprintf("  AI Status     : %s\n",   $result['ai_status']);
    }

    $logDetails = sprintf(
        "  User ID       : %s\n" .
        "  Method        : %s\n" .
        "  History Count : %d sampel\n" .
        "  Score         : %.4f\n" .
        "  Threshold     : %.4f\n" .
        "  Speed Dev     : %s\n" .
        "  Reason        : %s\n",
        $user['id'],
        $method,
        $nSamples,
        $score,
        $thresh,
        $speedDev,
        $reason
    );

    if ($mahalBlock)  $logDetails .= $mahalBlock;
    if ($aiBlock)     $logDetails .= $aiBlock;
    if ($gatesBlock)  $logDetails .= $gatesBlock;
    if ($scoringBlock) $logDetails .= $scoringBlock;
    if ($rawDataBlock) $logDetails .= $rawDataBlock;

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
            $nSamples++; // Increment untuk pengecekan milestone
        }

        // --- AUTO-RETRAIN PIPELINE (AI ENGINE) ---
        $modelPath = realpath(__DIR__ . '/../../ml/models/') . "/{$user['id']}_ocsvm.joblib";
        $isModelMissing = !file_exists($modelPath);
        $isMilestone = ($nSamples % 20 === 0 && $historyUpdated); // Hanya update rutin jika ada data baru

        if ($nSamples >= 20 && ($isModelMissing || $isMilestone)) {
            $trainData = ['history' => $history];
            if ($historyUpdated) {
                $trainData['history'][] = json_decode($inputKeystroke, true); 
            }
            
            $trainFile = realpath(__DIR__ . '/../../scratch/') . "/training_{$user['id']}.json";
            file_put_contents($trainFile, json_encode($trainData));
            
            $pyExec = $biomManager->getPythonPath();
            $pyTrain = realpath(__DIR__ . '/../../ml/ai_trainer.py');
            
            // Jalankan di background (Windows menggunakan 'start /B')
            pclose(popen("start /B \"\" \"$pyExec\" \"$pyTrain\" \"{$user['id']}\" \"$trainFile\"", "r"));
            
            $msg = $isModelMissing ? "Recovery" : "Update";
            $logDetails .= "  [PIPELINE] AI Auto-Training $msg Started (n=$nSamples)\n";
        }

        $logDetails .= "  History Updated: " . ($historyUpdated ? 'Ya' : 'Tidak') . "\n";

        $writeLog('login_success.log', "SUCCESS | User: $username", $logDetails);

        header("Location: ../../dashboard/index.php");
        exit();

    } else {
        $writeLog('login_failed.log', "FAILURE | User: $username", $logDetails);

        redirectWithError($reason);
    }

} else {
    redirectWithError("Username atau password salah");
}