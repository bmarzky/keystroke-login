<?php

/**
 * Validasi Konsistensi Data
 * Memastikan semua sampel memiliki jumlah fitur yang sama agar operasi matriks valid.
 */
function validateFeatureConsistency($samples, $expectedCount) {
    foreach ($samples as $sample) {
        if (count($sample) !== $expectedCount) {
            return false;
        }
    }
    return true;
}

/**
 * Menghitung Mean (Rata-rata)
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
 * Menghitung Varians (Diagonal Covariance)
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
        // Epsilon untuk mencegah pembagian nol jika data terlalu identik
        $variances[$i] = ($variances[$i] / ($count - 1)) + 0.0001;
    }
    return $variances;
}

/**
 * Core Mahalanobis Distance
 */
function mahalanobisDistance($inputVector, $meanVector, $variances) {
    $sum = 0;
    foreach ($inputVector as $i => $value) {
        $sum += pow($value - $meanVector[$i], 2) / $variances[$i];
    }
    return sqrt(abs($sum));
}

/**
 * Normalisasi Z-Score untuk fitur (opsional, tapi direkomendasikan untuk konsistensi)
 */
function normalizeZScore($samples) {
    if (empty($samples)) return $samples;
    $numFeatures = count($samples[0]);
    $means = calculateMean($samples);
    $variances = calculateVariances($samples, $means);
    
    $normalized = [];
    foreach ($samples as $sample) {
        $normSample = [];
        foreach ($sample as $i => $value) {
            $normSample[] = ($value - $means[$i]) / sqrt($variances[$i] + 0.0001);
        }
        $normalized[] = $normSample;
    }
    return $normalized;
}

/**
 * Fungsi Utama dengan Validasi dan Normalisasi
 */
function compareMultipleKeystroke($allStoredJson, $inputJson) {
    $input = json_decode($inputJson, true);
    
    // 1. Validasi awal struktur input
    if (!isset($input['dwell'], $input['flight']) || empty($input['dwell'])) {
        return 9999; 
    }

    $inputVector = array_merge(array_values($input['dwell']), array_values($input['flight']));
    $expectedFeatureCount = count($inputVector);

    // 2. Parsing dan Validasi Sampel Historis
    $samples = [];
    foreach ($allStoredJson as $storedJson) {
        $stored = json_decode($storedJson, true);
        if (isset($stored['dwell'], $stored['flight'])) {
            $vector = array_merge(array_values($stored['dwell']), array_values($stored['flight']));
            // Validasi: Panjang data harus sama dengan input
            if (count($vector) === $expectedFeatureCount) {
                $samples[] = $vector;
            }
        }
    }

    // Syarat minimal untuk statistik: butuh setidaknya 1 sampel valid (untuk training awal)
    if (count($samples) < 1) return 9999;

    // 3. Hitung mean dan variance asli untuk normalisasi input
    $originalMean = calculateMean($samples);
    $originalVariances = calculateVariances($samples, $originalMean);

    // Normalisasi samples
    $samples = normalizeZScore($samples);

    // Normalisasi input dengan mean dan variance asli
    $normalizedInput = [];
    foreach ($inputVector as $i => $value) {
        $normalizedInput[] = ($value - $originalMean[$i]) / sqrt($originalVariances[$i] + 0.0001);
    }

    // 4. Hitung parameter distribusi dari samples normalized
    $meanVector = calculateMean($samples);
    $variances = calculateVariances($samples, $meanVector);

    // 5. Hitung Jarak
    return mahalanobisDistance($normalizedInput, $meanVector, $variances);
}