<?php

// config
define('MIN_SAMPLES', 2);
define('EPSILON', 0.001);
define('Z_THRESHOLD_MULTIPLIER', 0.5); // lebih longgar untuk adaptivitas

// validasi vector (filter noise)
function isValidVector($vector, $expectedLength) {
    if (count($vector) !== $expectedLength) return false;

    foreach ($vector as $v) {
        if (!is_numeric($v) || $v < 10 || $v > 500) {
            return false; // filter noise
        }
    }
    return true;
}

// mean
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

// Variance dengan Bessel's correction
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
        $variances[$i] = ($value / max(1, ($count - 1))) + EPSILON;
    }

    return $variances;
}

// z score normalization
function normalizeZScore($samples) {
    $means = calculateMean($samples);
    $variances = calculateVariances($samples, $means);

    $normalized = [];

    foreach ($samples as $sample) {
        $row = [];
        foreach ($sample as $i => $value) {
            $row[] = ($value - $means[$i]) / sqrt($variances[$i]);
        }
        $normalized[] = $row;
    }

    return [$normalized, $means, $variances];
}

// Mahalanobis distance
function mahalanobisDistance($x, $mean, $var) {
    $sum = 0;

    foreach ($x as $i => $value) {
        $sum += pow($value - $mean[$i], 2) / $var[$i];
    }

    return sqrt($sum);
}

// threshold otomatis berdasarkan distribusi data training
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

    $std = sqrt($variance / max(1, count($distances) - 1));

    return $meanDist + (Z_THRESHOLD_MULTIPLIER * $std);
}

// main function untuk verifikasi keystroke
function verifyKeystroke($allStoredJson, $inputJson) {

    $input = json_decode($inputJson, true);
    if (!isset($input['dwell'], $input['flight'])) {
        return ['status' => false, 'distance' => 9999];
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

    if (count($samples) < MIN_SAMPLES) {
        file_put_contents('debug.log', "samples count: " . count($samples) . ", expectedLength: " . $expectedLength . "\n", FILE_APPEND);
        return ['status' => false, 'distance' => 9999];
    }

    // normalisasi data training
    list($normalizedSamples, $means, $vars) = normalizeZScore($samples);

    // normalisasi input
    $normInput = [];
    foreach ($inputVector as $i => $value) {
        $normInput[] = ($value - $means[$i]) / sqrt($vars[$i]);
    }

    // model
    $meanVector = calculateMean($normalizedSamples);
    $variances = calculateVariances($normalizedSamples, $meanVector);

    $distance = mahalanobisDistance($normInput, $meanVector, $variances);

    // threshold otomatis berdasarkan distribusi data training
    $threshold = calculateThreshold($normalizedSamples, $meanVector, $variances);

    return [
        'status' => $distance <= $threshold,
        'distance' => $distance,
        'threshold' => $threshold
    ];
}

// Fungsi untuk menghitung skor biometrik (distance) untuk multiple keystroke
function compareMultipleKeystroke($allData, $inputKeystroke) {
    $result = verifyKeystroke($allData, $inputKeystroke);
    return $result['distance'];
}