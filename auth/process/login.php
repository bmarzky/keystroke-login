<?php
session_start();

// Header untuk mencegah caching agar session lama tidak nyangkut
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Cache-Control: post-check=0, pre-check=0", false);
header("Pragma: no-cache");

// Lapisan keamanan tambahan
header("X-XSS-Protection: 1; mode=block");

include "../../config/database.php";
include "../../core/biometrics.php";

$conn = getConnection();

// Helper: Redirect dengan pesan error dan berhenti seketika
function redirectWithError($msg) {
    header("Location: ../login.php?error=" . urlencode($msg));
    exit(); 
}

// Helper: Deteksi Python Executable
function getPythonExec() {
    $pyExec = trim(shell_exec('where python 2>NUL') ?? '');
    $pyExec = strtok($pyExec, "\n"); // Ambil baris pertama saja
    return empty($pyExec) ? 'python' : $pyExec;
}

// Helper: Picu Training AI di Latar Belakang (Self-Healing & Adaptive)
function triggerBackgroundTraining($user_id) {
    $pyPathTrain = realpath(__DIR__ . '/../../ml/scripts/train.py');
    if ($pyPathTrain) {
        $pyExec = getPythonExec();
        $argTrainUser = escapeshellarg($user_id);
        // Format Windows background: cmd /c start /B "" "python" "script" ...
        $cmd = 'cmd /c "start /B "" ' . escapeshellarg($pyExec) . ' ' . escapeshellarg($pyPathTrain) . ' ' . $argTrainUser . ' > NUL 2>&1"';
        pclose(popen($cmd, "r"));
    }
}

// Helper: Proses Login Sukses
function processSuccessfulLogin($user, $conn, $rawKeystroke, $status) {
    // Bersihkan session sisa sebelum diisi yang baru
    session_unset();
    session_regenerate_id(true);

    $_SESSION['user_id'] = $user['id'];
    $_SESSION['username'] = $user['username'];
    $_SESSION['login_status'] = $status;

    // Simpan data baru untuk memperkaya dataset (Adaptive Learning)
    $stmt = $conn->prepare("INSERT INTO keystroke_data (user_id, features) VALUES (?, ?)");
    $stmt->bind_param("is", $user['id'], $rawKeystroke);
    $stmt->execute();

    // Mengaktifkan AI di Latar Belakang (Retrain Model) ketika data baru berhasil masuk
    triggerBackgroundTraining($user['id']);

    header("Location: ../../dashboard/index.php");
    exit(); 
}

// 1. Validasi Input Dasar
if (!isset($_POST['username'], $_POST['password'], $_POST['keystroke'])) {
    redirectWithError("Form tidak lengkap");
}

$username = trim($_POST['username']);
$password = trim($_POST['password']);
$inputKeystroke = trim($_POST['keystroke']);

// 1.5. Validasi Panjang Username & Password
if (strlen($username) < 3) {
    redirectWithError("Username harus minimal 3 karakter");
}
if (strlen($password) < 6) {
    redirectWithError("Password harus minimal 6 karakter");
}

// 2. Validasi Format JSON
$decodedInput = @json_decode($inputKeystroke, true);
if (json_last_error() !== JSON_ERROR_NONE || !is_array($decodedInput) || !isset($decodedInput['speed'])) {
    redirectWithError("Data biometrik rusak atau tidak valid");
}

// 3. Cari User
$stmt = $conn->prepare("SELECT id, username, password FROM users WHERE username = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$user = $stmt->get_result()->fetch_assoc();

// Proses otentikasi utama

if ($user && password_verify($password, $user['password'])) {

    // Ambil data referensi
    $stmt = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 20");
    $stmt->bind_param("i", $user['id']);
    $stmt->execute();
    $result = $stmt->get_result();

    $allData = [];
    while ($row = $result->fetch_assoc()) {
        $allData[] = $row['features']; 
    }

    $dataCount = count($allData);

    // TIER 2: Otentikasi Lanjut dengan AI OneClassSVM Python
    $svmUsed = false;
    $reason = 'N/A';
    
    if ($dataCount >= 15) {
        $pyPathPredict = realpath(__DIR__ . '/../../ml/scripts/predict.py');

        if ($pyPathPredict) {
            // Tulis JSON ke temp file agar tidak rusak saat di-escape oleh Windows CLI
            $tmpFile = tempnam(sys_get_temp_dir(), 'ks_') . '.json';
            file_put_contents($tmpFile, $inputKeystroke);

            $argUser    = escapeshellarg($user['id']);
            $argTmpFile = escapeshellarg($tmpFile);

            $pyExec = getPythonExec();
            $cmd = escapeshellarg($pyExec) . ' ' . escapeshellarg($pyPathPredict) . " $argUser $argTmpFile 2>NUL";
            $pythonOut = trim(shell_exec($cmd));
            $mlResult  = null;

            if (!empty($pythonOut)) {
                $mlResult = json_decode($pythonOut, true);
            }

            // Bersihkan file sementara
            @unlink($tmpFile);

            if ($mlResult === null || json_last_error() !== JSON_ERROR_NONE) {
                error_log("[SVM] Output Python invalid atau kosong. RAW: " . substr($pythonOut, 0, 400));
                $reason = "AI tidak tersedia, fallback ke Mahalanobis";
            } elseif ($mlResult['status'] === 'success') {
                $svmUsed = true;
                $isMatch = $mlResult['is_match'];
                $score   = $mlResult['decision_score'] ?? ($isMatch ? 1 : -1);
                $thresh  = 0; // Boundary One-Class SVM adalah 0
                $reason  = "Metode AI OneClassSVM (Python)";
            } elseif ($mlResult['status'] === 'fallback') {
                $reason = "AI Meminta Fallback ke Mahalanobis";
                // Auto-Retrain: Jika model hilang tapi data cukup, picu training ulang secara otomatis
                triggerBackgroundTraining($user['id']);
            }
        }
    }
    
        // TIER 1: Kalkulasi Mahalanobis Murni di PHP (Otomatis jika SVM absen/gagal dieksekusi)
        if (!$svmUsed) {
            $verification = verifyKeystroke($allData, $inputKeystroke); 
            $isMatch = (isset($verification['status']) && $verification['status'] === true);
            $score   = $verification['distance'] ?? 0;
            $thresh  = $verification['threshold'] ?? 0;
            $phpReason = $verification['reason'] ?? 'N/A';
            
            // Label eksplisit sesuai jumlah data dan tahap yang dilalui
            if ($dataCount >= 15) {
                $tierLabel = "[Tier-1:Mahalanobis (Fallback)]";
            } elseif ($dataCount >= 6) {
                $tierLabel = "[Tier-1:Mahalanobis (Strict)]";
            } else {
                $tierLabel = "[Tier-1:Mahalanobis (Adaptive Blending)]";
            }
            
            $reason = ($reason !== 'N/A') ? "$tierLabel $reason -> $phpReason" : "$tierLabel $phpReason";
        } else {
            $reason = "[Tier-2:SVM] $reason";
        }

    // Logging (Sekarang mencatat semua usaha, baik training maupun verifikasi)
    $logStatus = $isMatch ? 'MATCH' : 'REJECT';
    $logMsg = sprintf(
        "[%s] User: %s | Score: %.2f | Thresh: %.2f | Speed: %.2f CPM | Status: %s | Reason: %s | DataCount: %d\n",
        date('Y-m-d H:i:s'), 
        $username, 
        $score, 
        $thresh,
        (float)$decodedInput['speed'],
        $logStatus,
        $reason,
        $dataCount
    );
    file_put_contents('biometric_debug.log', $logMsg, FILE_APPEND);

    if ($isMatch) {
        // Berhasil Verifikasi (Atau Mode Belajar di Tahap Sangat Awal jika ingin dibedakan labelnya)
        $statusLabel = ($dataCount < 5) ? "Verified (Learning Mode)" : "Verified";
        processSuccessfulLogin($user, $conn, $inputKeystroke, $statusLabel);
    } else {
        // Jika tidak cocok, cek apakah skornya menunjukkan error kritis (robot) atau sekadar pola beda
        $errorDetail = ($reason !== 'N/A') ? $reason : "Pola ketikan tidak cocok";
        redirectWithError("Akses Ditolak: $errorDetail (Skor: " . round($score, 2) . ")");
    }

} else {
    redirectWithError("Username atau password salah");
}
// End of Auth Logic