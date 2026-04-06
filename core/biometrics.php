<?php

// ================= CONFIG =================
define('MIN_SAMPLES', 3); // Minimal data training
define('EPSILON', 0.001); // Stabilkan variance
define('Z_THRESHOLD_MULTIPLIER', 2.0);

// ================= NORMALISASI VECTOR =================
function normalizeVector($vector, $targetLength) {
    $current = count($vector);

    // Potong jika terlalu panjang
    if ($current > $targetLength) {
        return array_slice($vector, 0, $targetLength);
    }

    // Tambah 0 jika kurang
    while (count($vector) < $targetLength) {
        $vector[] = 0;
    }

    return $vector;
}

// ================= VALIDASI DATA =================
function isValidVector($vector) {
    foreach ($vector as $v) {
        if (!is_numeric($v) || $v < 0 || $v > 2.0) {
            return false;
        }
    }
    return true;
}

// ================= MEAN =================
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

// ================= VARIANCE =================
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
        $variances[$i] = ($value / $denominator) + EPSILON;
    }

    return $variances;
}

// ================= MAHALANOBIS =================
function mahalanobisDistance($x, $mean, $var) {
    $sum = 0;

    foreach ($x as $i => $value) {
        $sum += pow($value - $mean[$i], 2) / $var[$i];
    }

    return sqrt($sum);
}

// ================= THRESHOLD =================
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

// ================= VERIFY FUNCTION =================
function verifyKeystroke($allStoredJson, $inputJson) {
    $input = json_decode($inputJson, true);

    if (!isset($input['dwell'], $input['flight'])) {
        return ['status' => false, 'distance' => 9999, 'threshold' => 0];
    }

    if (count($input['dwell']) < 5 || count($input['flight']) < 5) {
        return ['status' => false, 'distance' => 9997, 'threshold' => 0];
    }
    // Gabungkan fitur
    $inputVector = array_merge($input['dwell'], $input['flight']);
    if (empty($allStoredJson)) {
    return ['status' => false, 'distance' => 9996, 'threshold' => 0];
    }
    $firstData = json_decode($allStoredJson[0], true);

if (!isset($firstData['dwell'], $firstData['flight'])) {
    return ['status' => false, 'distance' => 9995, 'threshold' => 0];
}

if (!is_array($firstData['dwell']) || !is_array($firstData['flight'])) {
    return ['status' => false, 'distance' => 9994, 'threshold' => 0];
}

$expectedLength = count($firstData['dwell']) + count($firstData['flight']);

    // Normalisasi input
    $inputVector = normalizeVector($inputVector, $expectedLength);

    $samples = [];

    foreach ($allStoredJson as $json) {
        $data = json_decode($json, true);

        if (json_last_error() !== JSON_ERROR_NONE) continue;
        if (!isset($data['dwell'], $data['flight'])) continue;

        $vector = array_merge($data['dwell'], $data['flight']);

        // Normalisasi training data
        $vector = normalizeVector($vector, $expectedLength);

        if (isValidVector($vector)) {
            $samples[] = $vector;
        }
    }

    // Jika data training kurang
    if (count($samples) < MIN_SAMPLES) {
        return [
            'status' => false,
            'distance' => 9998,
            'threshold' => 0,
            'debug_samples' => count($samples)
        ];
    }

    // Hitung statistik
    $means = calculateMean($samples);
    $vars = calculateVariances($samples, $means);

    // Hitung distance
    $distance = mahalanobisDistance($inputVector, $means, $vars);

    // Threshold adaptif
    $calculatedThreshold = calculateThreshold($samples, $means, $vars);

    // Dynamic threshold (berdasarkan panjang fitur)
    $dynamicMinThreshold = sqrt($expectedLength);

    $finalThreshold = max($calculatedThreshold, $dynamicMinThreshold);

    return [
        'status' => $distance <= $finalThreshold,
        'distance' => $distance,
        'threshold' => $finalThreshold
    ];
}

// ================= HELPER =================
function compareMultipleKeystroke($allData, $inputKeystroke) {
    $result = verifyKeystroke($allData, $inputKeystroke);
    return $result['distance'];
}