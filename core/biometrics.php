<?php

/**
 * Mencari Path Python (Cross-Platform / Windows Compatible)
 */
function getPythonExecBiometrics() {
    $pyExec = trim(shell_exec('where python 2>NUL') ?? '');
    $pyExec = strtok($pyExec, "\n");
    return empty($pyExec) ? 'python' : $pyExec;
}

/**
 * Menerima dataset berupa JSON String dan mendelegasikan penghitungan 
 * True Mahalanobis Distance (yang membutuhkan Matriks Kovarians Pseudo-Inverse)
 * kepada Script Python (Numpy).
 * 
 * @param array $allStoredJson - Sejarah / Historis ketikan user dari Database
 * @param string $inputJson    - Percobaan ketikan user yang disubmit saat login
 */
function verifyKeystroke($allStoredJson, $inputJson) {
    $input = json_decode($inputJson, true);

    // 1. Cek kelengkapan fitur baru
    if (!isset($input['dwell'], $input['flight'], $input['d2d'], $input['u2u'], $input['speed'])) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0, 'reason' => 'Fitur tidak lengkap'];
    }

    // 2. Deteksi Robot / Copy-Paste via Typing Speed
    if ($input['speed'] > 1000) {
        return ['status' => false, 'distance' => 9993, 'threshold' => 0, 'reason' => 'Abnormal typing speed (Terlalu Cepat)'];
    }
    if ($input['speed'] <= 0) {
        return ['status' => false, 'distance' => 9993, 'threshold' => 0, 'reason' => 'Kecepatan ketikan tidak valid (<= 0)'];
    }

    // 3. Ekstrak Riwayat untuk Dilempar ke Python
    $history = [];
    if (!empty($allStoredJson)) {
        foreach ($allStoredJson as $json) {
            $data = json_decode($json, true);
            if (json_last_error() === JSON_ERROR_NONE) {
                $history[] = $data;
            }
        }
    }

    // 4. Bundling sebagai Dictionary JSON Tunggal dan simpan pada temp local
    $dataToPython = [
        'input' => $input,
        'history' => $history
    ];
    
    // Simpan ke Temporary OS Windows Folder untuk dibaca Python
    $baseTmp = tempnam(sys_get_temp_dir(), 'biom_');
    $tmpFile = $baseTmp . '.json';
    file_put_contents($tmpFile, json_encode($dataToPython));
    @unlink($baseTmp); // Hapus file kosong bawaan tempnam
    
    // 5. Panggil Python External Script (mahalanobis.py)
    $pyPath = realpath(__DIR__ . '/../ml/scripts/mahalanobis.py');
    if (!$pyPath) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0, 'reason' => 'Script Engine Python tidak ditemukan pada ml/scripts/mahalanobis.py'];
    }

    $pyExec = getPythonExecBiometrics();
    // 2>NUL menyembunyikan warning CLI Python
    $cmd = escapeshellarg($pyExec) . ' ' . escapeshellarg($pyPath) . ' ' . escapeshellarg($tmpFile) . " 2>NUL";
    
    // Terima Ouput dan Bersihkan Temp File
    $pythonOut = trim(shell_exec($cmd));
    @unlink($tmpFile);
    
    // 6. Validasi Kembalian
    if (empty($pythonOut)) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0, 'reason' => 'Runtime Terputus (Abaikan/Python Error)'];
    }
    
    $result = json_decode($pythonOut, true);
    
    // Format JSON Harus Valid
    if (json_last_error() !== JSON_ERROR_NONE) {
         error_log("[Mahalanobis Fatal] Python Response: " . substr($pythonOut, 0, 150));
         return ['status' => false, 'distance' => 9999, 'threshold' => 0, 'reason' => 'Invalid Format Return dari Python'];
    }
    
    // Kembalikan ke Login.php (Sistem Tier-1/Fallback)
    // n_features = 8 (sehat) menunjukkan sistem sudah pakai statistical aggregation
    return [
       'status'        => $result['status'] ?? false,
       'distance'      => $result['score']  ?? 9999, // Gunakan score dari Python
       'threshold'     => $result['threshold']  ?? 0,
       'should_update' => $result['should_update_history'] ?? false, // 🔹 INI KUNCINYA
       'reason'        => $result['reason']     ?? 'Kesalahan Tanpa Penjelasan',
       'n_features'    => $result['n_features'] ?? null,
       'n_samples'     => $result['n_samples']  ?? null,
    ];
}

?>
