<?php

// Config
define('MIN_SAMPLES', 3); // Minimal data training untuk mulai verifikasi
define('EPSILON', 0.0001); // Menghindari division by zero dan menstabilkan data detik
define('Z_THRESHOLD_MULTIPLIER', 2.0); // 95% confidence interval

// validasi data
function isValidVector($vector) {
    foreach ($vector as $v) {
        // Validasi: Harus angka, tidak boleh negatif, dan tidak boleh terlalu lama (> 5 detik)
        // Kecuali elemen terakhir (Speed) yang bisa bernilai besar (CPM)
        if (!is_numeric($v) || $v < 0) {
            return false;
        }
    }
    return true;
}

/**
 * Menghitung nilai rata-rata (mean) untuk setiap fitur (vektor) dari sekumpulan sampel.
 * 
 * @param array $samples Kumpulan array fitur
 * @return array Array berisi nilai rata-rata tiap fitur
 */
function calculateMean($samples) {
    $count = count($samples);
    $numFeatures = count($samples[0]);
    $means = array_fill(0, $numFeatures, 0);

    foreach ($samples as $sample) {
        foreach ($sample as $i => $value) {
            $means[$i] += $value;
        }
    }

    foreach ($means as $i => $value) {
        $means[$i] /= $count;
    }

    return $means;
}

// variance
function calculateVariances($samples, $means) {
    $count = count($samples);
    $numFeatures = count($means);
    $variances = array_fill(0, $numFeatures, 0);

    foreach ($samples as $sample) {
        foreach ($sample as $i => $value) {
            $variances[$i] += pow($value - $means[$i], 2);
        }
    }

    foreach ($variances as $i => $value) {
        $denominator = ($count > 1) ? ($count - 1) : 1;
        $variances[$i] = ($variances[$i] / $denominator) + EPSILON;
    }

    return $variances;
}

// mahalanobis distance
function mahalanobisDistance($x, $mean, $var) {
    $sum = 0;
    foreach ($x as $i => $value) {
        $sum += pow($value - $mean[$i], 2) / $var[$i];
    }
    return sqrt($sum);
}

// threshold
function calculateThreshold($samples, $mean, $var) {
    $distances = [];
    foreach ($samples as $s) {
        $distances[] = mahalanobisDistance($s, $mean, $var);
    }

    $meanDist = array_sum($distances) / count($distances);
    $variance = 0;
    foreach ($distances as $d) {
        $variance += pow($d - $meanDist, 2);
    }

    $denominator = (count($distances) > 1) ? (count($distances) - 1) : 1;
    $std = sqrt($variance / $denominator);

    return $meanDist + (Z_THRESHOLD_MULTIPLIER * $std);
}

// verify keystroke
function verifyKeystroke($allStoredJson, $inputJson) {
    $input = json_decode($inputJson, true);

    // 1. Cek kelengkapan fitur baru
    if (!isset($input['dwell'], $input['flight'], $input['d2d'], $input['u2u'], $input['speed'])) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0, 'reason' => 'Fitur tidak lengkap'];
    }

    // 2. Deteksi Robot / Copy-Paste via Typing Speed
    // Jika CPM > 1000, hampir pasti itu robot/paste (Manusia pro sekitar 100-200 CPM untuk password)
    if ($input['speed'] > 1000 || $input['speed'] <= 0) {
        return ['status' => false, 'distance' => 9993, 'threshold' => 0, 'reason' => 'Abnormal typing speed'];
    }

    // 3. Gabungkan semua fitur menjadi satu vektor input
    $inputVector = array_merge(
        $input['dwell'], 
        $input['flight'], 
        $input['d2d'], 
        $input['u2u'], 
        [(float)$input['speed']]
    );

    $expectedLength = count($inputVector);
    $samples = [];

    // 4. Proses data training
    if (empty($allStoredJson)) {
        return ['status' => false, 'distance' => 9996, 'threshold' => 0, 'reason' => 'No training data'];
    }

    foreach ($allStoredJson as $json) {
        $data = json_decode($json, true);
        if (json_last_error() !== JSON_ERROR_NONE) continue;
        if (!isset($data['dwell'], $data['flight'], $data['d2d'], $data['u2u'], $data['speed'])) continue;

        $vector = array_merge(
            $data['dwell'], 
            $data['flight'], 
            $data['d2d'], 
            $data['u2u'], 
            [(float)$data['speed']]
        );

        // Pastikan panjang vektor sama (user tidak boleh typo/backspace saat input)
        $currentLength = count($vector);
        if ($currentLength === $expectedLength && isValidVector($vector)) {
            $samples[] = $vector;
        } else {
            // Tambahkan log ini untuk debug di PHP
            error_log("Sample diabaikan: Ukuran $currentLength, Harusnya $expectedLength");
        }
    }

    // 5. Cek kecukupan sampel yang valid
    if (count($samples) < MIN_SAMPLES) {
        $found = count($samples);
        return [
            'status' => false,
            'distance' => 9998,
            'threshold' => 0,
            'reason' => "Sampel tidak cukup (Hanya ditemukan $found dari minimal " . MIN_SAMPLES . ")"
        ];
    }

    // 6. Kalkulasi Statistik Mahalanobis
    $means = calculateMean($samples);
    $vars = calculateVariances($samples, $means);
    $distance = mahalanobisDistance($inputVector, $means, $vars);

    // 7. Penentuan Threshold (Adaptif + Dynamic Baseline)
    $calculatedThreshold = calculateThreshold($samples, $means, $vars);
    $dynamicMinThreshold = sqrt($expectedLength); 

    $finalThreshold = max($calculatedThreshold, $dynamicMinThreshold);
    $isMatch = ($distance <= $finalThreshold);

    // return
    return [
        'status' => $isMatch,
        'distance' => (float)$distance,
        'threshold' => (float)$finalThreshold,
        'reason' => $isMatch ? 'Pola Cocok' : 'Pola Tidak Cocok'
    ];
}

// compare multiple keystroke
function compareMultipleKeystroke($allData, $inputKeystroke) {
    $result = verifyKeystroke($allData, $inputKeystroke);
    return $result['distance'];
}