<?php

// Config
define('MIN_SAMPLES', 1); // Upgraded: Mulai verifikasi sejak data ke-1
define('EPSILON', 0.001); // Ditingkatkan sedikit untuk menjaga stabilitas (Security Floor)
define('HEURISTIC_TOLERANCE_PERCENT', 0.30); // Longgar (30% dari ritme asli) untuk mempermudah pemula
define('Z_THRESHOLD_MULTIPLIER', 2.5); // Lebih pemaaf terhadap variasi natural manusia

/**
 * Memvalidasi vektor fitur. Semua elemen harus angka non-negatif.
 * 
 * @param array $vector Vektor fitur yang akan divalidasi
 * @return bool True jika valid, False sebaliknya
 */
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

/**
 * Menghitung median dari array fitur
 * @param array $samples Array 2D dari sampel
 * @return array Array berisi nilai median tiap fitur
 */
function calculateMedian($samples) {
    $numFeatures = count($samples[0]);
    $medians = [];

    for ($i = 0; $i < $numFeatures; $i++) {
        $values = array_column($samples, $i);
        sort($values);
        $count = count($values);
        $middle = floor($count / 2);
        $medians[] = ($count % 2) ? $values[$middle] : ($values[$middle - 1] + $values[$middle]) / 2;
    }

    return $medians;
}

// variance
function calculateVariances($samples, $means) {
    $count = count($samples);
    $numFeatures = count($means);
    $empiricalVariances = array_fill(0, $numFeatures, 0);

    // 1. Hitung varians empiris dari sampel yang ada
    if ($count > 1) {
        foreach ($samples as $sample) {
            foreach ($sample as $i => $value) {
                $empiricalVariances[$i] += pow($value - $means[$i], 2);
            }
        }
        $denominator = $count - 1;
        foreach ($empiricalVariances as $i => $value) {
            $empiricalVariances[$i] /= $denominator;
        }
    }

    // 2. Smooth Transition (Linear Decay over 5 samples)
    $finalVariances = [];
    $maxHeuristicSamples = 10;
    
    // Weight berkurang secara linear: n=1 (1.0) ke n=10 (0.0)
    $heuristicWeight = ($count < $maxHeuristicSamples) 
        ? ($maxHeuristicSamples - $count) / ($maxHeuristicSamples - 1)
        : 0;

    foreach ($means as $i => $meanValue) {
        // Heuristic: (25% dari nilai rata-rata)^2
        $heuristicVar = pow($meanValue * HEURISTIC_TOLERANCE_PERCENT, 2);
        
        // Gabungkan: Heuristic + Empirical
        $blendedVar = ($heuristicWeight * $heuristicVar) + ((1 - $heuristicWeight) * $empiricalVariances[$i]);
        
        $finalVariances[$i] = $blendedVar + EPSILON;
    }

    return $finalVariances;
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
    
    $numSamples = count($samples);
    if ($numSamples < 3) {
        $floorMultiplier = 1.0; // Sangat pemaaf (Hanya untuk 2 login pertama)
    } elseif ($numSamples < 6) {
        $floorMultiplier = 0.8; // Menengah
    } elseif ($numSamples < 10) {
        $floorMultiplier = 0.7; // Transisi menuju standar
    } else {
        $floorMultiplier = 0.6; // Standar keamanan produksi (Mulai login ke-10)
    }
    
    $dynamicMinThreshold = sqrt($expectedLength) * $floorMultiplier; 
    
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