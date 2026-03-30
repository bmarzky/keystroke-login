<?php

function euclideanDistance($a, $b) {
    if (!is_array($a) || !is_array($b)) return 9999;

    // Paksa array menggunakan index angka berurutan (0, 1, 2...)
    $a = array_values($a);
    $b = array_values($b);

    $sum = 0;
    $length = min(count($a), count($b));

    if ($length === 0) return 9999;

    for ($i = 0; $i < $length; $i++) {
        $sum += pow($a[$i] - $b[$i], 2);
    }

    return sqrt($sum);
}

function compareMultipleKeystroke($allStored, $inputJson) {
    $input = json_decode($inputJson, true);
    
    // Pastikan key 'dwell' dan 'flight' ada di input
    if (!isset($input['dwell']) || !isset($input['flight'])) return 9999;

    $totalScore = 0;
    $validDataCount = 0;

    foreach ($allStored as $storedJson) {
        $stored = json_decode($storedJson, true);
        
        // Lewati jika data di database ternyata rusak/tidak lengkap
        if (!isset($stored['dwell']) || !isset($stored['flight'])) continue;

        $dwellDist = euclideanDistance($stored['dwell'], $input['dwell']);
        $flightDist = euclideanDistance($stored['flight'], $input['flight']);
        
        // Rata-rata jarak untuk sampel ini
        $totalScore += ($dwellDist + $flightDist) / 2;
        $validDataCount++;
    }

    if ($validDataCount === 0) return 9999;

    // Return rata-rata skor dari semua sampel yang dibandingkan
    return $totalScore / $validDataCount;
}