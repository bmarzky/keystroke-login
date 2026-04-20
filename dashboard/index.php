<?php
session_start();
include "../config/database.php";

if (!isset($_SESSION['user_id'])) {
    header("Location: ../auth/login.php");
    exit();
}

$conn = getConnection();
$user_id = $_SESSION['user_id'];

// 1. Ambil total data
$stmtCount = $conn->prepare("SELECT COUNT(*) as total FROM keystroke_data WHERE user_id = ?");
$stmtCount->bind_param("i", $user_id);
$stmtCount->execute();
$totalData = $stmtCount->get_result()->fetch_assoc()['total'];

// 2. Ambil 2 data terakhir (Data Login Terbaru vs Data Sebelumnya)
$stmtData = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 2");
$stmtData->bind_param("i", $user_id);
$stmtData->execute();
$result = $stmtData->get_result();

$allData = [];
while ($row = $result->fetch_assoc()) { $allData[] = $row; }

$currentFeatures = isset($allData[0]) ? json_decode($allData[0]['features'], true) : ['dwell' => [], 'flight' => []];
$prevFeatures = isset($allData[1]) ? json_decode($allData[1]['features'], true) : ['dwell' => [], 'flight' => []];

// 3. Kalkulasi Statistik (Disesuaikan untuk satuan DETIK)
$avgDwell = 0; $avgFlight = 0; $wpm = 0; $stability = 0;

if (!empty($currentFeatures['dwell'])) {
    $cntD = count($currentFeatures['dwell']);
    $sumDwell = array_sum($currentFeatures['dwell']);
    $sumFlight = !empty($currentFeatures['flight']) ? array_sum($currentFeatures['flight']) : 0;
    
    // Rata-rata dalam detik
    $avgDwell = $sumDwell / $cntD;
    if (!empty($currentFeatures['flight'])) {
        $avgFlight = $sumFlight / count($currentFeatures['flight']);
    }

    // Hitung WPM: (Jumlah Karakter / 5) / (Total Waktu dalam Menit)
    // Karena $sumDwell & $sumFlight dalam detik, maka dibagi 60 untuk jadi menit
    $totalTimeInSeconds = $sumDwell + $sumFlight;
    if ($totalTimeInSeconds > 0) {
        $wpm = ($cntD / 5) / ($totalTimeInSeconds / 60);
    }

    // Stabilitas (Standard Deviation dari Dwell Time)
    $var = 0;
    foreach($currentFeatures['dwell'] as $d) { 
        $var += pow($d - $avgDwell, 2); 
    }
    $stability = sqrt($var / $cntD);
}
?>

<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Keystroke Dynamics</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="dashboard-page">

<div class="dashboard-wrapper">
    <header class="dashboard-header">
        <h2 class="dashboard-title">Analisis Keystroke: <?php echo htmlspecialchars($_SESSION['username']); ?></h2>
        <form id="logoutForm" action="../auth/process/logout.php" method="POST">
            <button type="submit" class="btn-logout">Logout</button>
        </form>
    </header>

    <div class="stats-grid">
        <div class="stat-item"><small>TOTAL DATA</small><b><?php echo $totalData; ?></b></div>
        <div class="stat-item"><small>AVG DWELL</small><b><?php echo round($avgDwell * 1000, 0); ?> ms</b></div>
        <div class="stat-item"><small>AVG FLIGHT</small><b><?php echo round($avgFlight * 1000, 0); ?> ms</b></div>
        <div class="stat-item"><small>KECEPATAN</small><b><?php echo round($wpm, 1); ?> WPM</b></div>
        <div class="stat-item"><small>STABILITAS</small><b>±<?php echo round($stability * 1000, 1); ?></b></div>
        <div class="stat-item"><small>LAST LOGIN</small><b><?php echo htmlspecialchars($_SESSION['last_login'] ?? 'N/A'); ?></b></div>
    </div>

    <div class="chart-box">
        <canvas id="keystrokeChart"></canvas>
    </div>

    <div id="dashboard-data" class="hidden-dashboard-data" data-current='<?php echo htmlspecialchars(json_encode($currentFeatures), ENT_QUOTES); ?>' data-prev='<?php echo htmlspecialchars(json_encode($prevFeatures), ENT_QUOTES); ?>'></div>

    <div class="table-container">
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>Fitur (ms)</th>
                    <?php 
                    $maxKeys = max(count($currentFeatures['dwell']), count($prevFeatures['dwell']));
                    for($i=1; $i<=$maxKeys; $i++) echo "<th>K$i</th>"; 
                    ?>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="label-cell">Dwell (Current)</td>
                    <?php
                    for ($i = 0; $i < $maxKeys; $i++) {
                        $value = $currentFeatures['dwell'][$i] ?? null;
                        echo '<td>' . ($value !== null ? round($value * 1000, 0) : '-') . '</td>';
                    }
                    ?>
                </tr>
                <tr class="row-muted">
                    <td class="label-cell">Dwell (Prev)</td>
                    <?php
                    for ($i = 0; $i < $maxKeys; $i++) {
                        $value = $prevFeatures['dwell'][$i] ?? null;
                        echo '<td>' . ($value !== null ? round($value * 1000, 0) : '-') . '</td>';
                    }
                    ?>
                </tr>
                <tr class="row-divider">
                    <td class="label-cell">Flight (Current)</td>
                    <?php
                    for ($i = 0; $i < $maxKeys; $i++) {
                        $value = $currentFeatures['flight'][$i] ?? null;
                        echo '<td>' . ($value !== null ? round($value * 1000, 0) : '-') . '</td>';
                    }
                    ?>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<script src="../assets/js/dashboard.js"></script>
<script>
document.addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        const logoutForm = document.getElementById('logoutForm');
        if (logoutForm) {
            logoutForm.submit();
        }
    }
});
</script>
</body>
</html>