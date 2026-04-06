<?php

// config
define('MIN_SAMPLES', 2);
define('EPSILON', 0.00001); // Presisi tinggi untuk data dalam satuan detik
define('Z_THRESHOLD_MULTIPLIER', 2.0); // Standar deviasi multiplier untuk toleransi

/**
 * 1. Validasi Vector (Filter Noise)
 */
function isValidVector($vector, $expectedLength) {
    if (count($vector) !== $expectedLength) return false;

    foreach ($vector as $v) {
        // Toleransi: 1ms (0.001) sampai 5 detik (5.0)
        if (!is_numeric($v) || $v < 0.001 || $v > 5.0) { 
            return false; 
        }
    }
    return true;
}

/**
 * Kalkulasi Mean (Rata-rata)
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
 * 2. Kalkulasi Variance dengan Bessel's Correction
 */
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

/**
 * Kalkulasi Mahalanobis Distance
 */
function mahalanobisDistance($x, $mean, $var) {
    $sum = 0;
    foreach ($x as $i => $value) {
        // Rumus: (x - mu)^2 / sigma^2
        $sum += pow($value - $mean[$i], 2) / $var[$i];
    }
    return sqrt($sum);
}

/**
 * 3. Kalkulasi Threshold Adaptif (Z-Score Based)
 */
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

/**
 * 4. FUNGSI UTAMA: Verifikasi Keystroke Dynamics
 */
function verifyKeystroke($allStoredJson, $inputJson) {
    $input = json_decode($inputJson, true);
    if (!isset($input['dwell'], $input['flight'])) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0];
    }

    $inputVector = array_merge($input['dwell'], $input['flight']);
    $expectedLength = count($inputVector);
    $samples = [];

    foreach ($allStoredJson as $json) {
        $data = json_decode($json, true);
        if (!isset($data['dwell'], $data['flight'])) continue;

        $vector = array_merge($data['dwell'], $data['flight']);

        if (isValidVector($vector, $expectedLength)) {
            $samples[] = $vector;
        }
    }

    // Jika data training tidak cukup
    if (count($samples) < MIN_SAMPLES) {
        return [
            'status' => false, 
            'distance' => 9998, 
            'threshold' => 0
        ];
    }

    $means = calculateMean($samples);
    $vars = calculateVariances($samples, $means);

    $distance = mahalanobisDistance($inputVector, $means, $vars);
    $calculatedThreshold = calculateThreshold($samples, $means, $vars);

    /**
     * PERSONALIZED DYNAMIC THRESHOLD
     * Menggunakan akar kuadrat dari jumlah fitur (N) sebagai batas bawah minimal.
     * Semakin panjang password (N besar), toleransi dasar akan semakin besar.
     */
    $dynamicMinThreshold = sqrt($expectedLength); 

    // Final Threshold: Pilih yang paling longgar antara statistik atau batas dinamis
    $finalThreshold = max($calculatedThreshold, $dynamicMinThreshold);

    return [
        'status' => $distance <= $finalThreshold,
        'distance' => $distance,
        'threshold' => $finalThreshold
    ];
}

/**
 * Fungsi pembantu untuk membandingkan data multiple
 */
function compareMultipleKeystroke($allData, $inputKeystroke) {
    $result = verifyKeystroke($allData, $inputKeystroke);
    return $result['distance'];
}