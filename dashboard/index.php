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
    <title>Dashboard Keystroke Dynamics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        html, body { 
            height: 100vh; margin: 0; overflow: hidden; 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: #fff; color: #000;
        }
        .main-wrapper {
            display: flex; flex-direction: column;
            height: 100%; padding: 20px 40px; box-sizing: border-box;
        }
        header { 
            display: flex; justify-content: space-between; align-items: center; 
            border-bottom: 2px solid #000; margin-bottom: 15px; padding-bottom: 5px;
        }
        h2 { margin: 0; font-size: 1.4rem; text-transform: uppercase; }
        .stats-grid { 
            display: grid; grid-template-columns: repeat(5, 1fr); 
            border: 1px solid #000; margin-bottom: 15px;
        }
        .stat-item { padding: 10px; text-align: center; border-right: 1px solid #000; }
        .stat-item:last-child { border-right: none; }
        .stat-item small { display: block; font-size: 0.65rem; font-weight: bold; color: #666; }
        .stat-item b { font-size: 1.2rem; }
        .chart-box { 
            flex: 1; min-height: 0; border: 1px solid #000; 
            padding: 10px; margin-bottom: 15px; display: flex; align-items: center;
        }
        .table-container { max-height: 25%; overflow-y: auto; border: 1px solid #000; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        table th, table td { border: 1px solid #000; padding: 6px; text-align: center; }
        table th { background-color: #f2f2f2; position: sticky; top: 0; }
        .label-cell { text-align: left; font-weight: bold; background: #fafafa; position: sticky; left: 0; }
        .btn-logout { 
            background: #fff; border: 1px solid #000; padding: 8px 20px; 
            cursor: pointer; font-weight: bold; text-transform: uppercase;
        }
        .btn-logout:hover { background: #000; color: #fff; }
    </style>
</head>
<body>

<div class="main-wrapper">
    <header>
        <h2>Analisis Keystroke: <?php echo htmlspecialchars($_SESSION['username']); ?></h2>
        <p>Last Login: <?php echo date('Y-m-d H:i:s'); ?></p>
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
    </div>

    <div class="chart-box">
        <canvas id="keystrokeChart"></canvas>
    </div>

    <div class="table-container">
        <table>
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
                    <?php foreach($currentFeatures['dwell'] as $val) echo "<td>" . round($val * 1000, 0) . "</td>"; ?>
                </tr>
                <tr style="color: #888;">
                    <td class="label-cell">Dwell (Prev)</td>
                    <?php 
                    if(!empty($prevFeatures['dwell'])) {
                        foreach($prevFeatures['dwell'] as $val) echo "<td>" . round($val * 1000, 0) . "</td>";
                    } else { echo "<td colspan='$maxKeys'>N/A</td>"; }
                    ?>
                </tr>
                <tr style="border-top: 2px solid #000;">
                    <td class="label-cell">Flight (Current)</td>
                    <?php 
                    foreach($currentFeatures['flight'] as $val) echo "<td>" . round($val * 1000, 0) . "</td>"; 
                    echo "<td>-</td>"; 
                    ?>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<script>
    // Ambil data asli (detik)
    const rawCurrent = <?php echo json_encode($currentFeatures); ?>;
    const rawPrev = <?php echo json_encode($prevFeatures); ?>;

    // Konversi ke Milidetik (ms) untuk tampilan grafik agar lebih enak dibaca
    const currentDwellMs = rawCurrent.dwell.map(v => Math.round(v * 1000));
    const prevDwellMs = rawPrev.dwell ? rawPrev.dwell.map(v => Math.round(v * 1000)) : [];
    
    const ctx = document.getElementById('keystrokeChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: currentDwellMs.map((_, i) => "K"+(i+1)),
            datasets: [
                {
                    label: 'Dwell Terbaru (ms)',
                    data: currentDwellMs,
                    borderColor: '#000',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2
                },
                {
                    label: 'Dwell Sebelumnya (ms)',
                    data: prevDwellMs,
                    borderColor: '#ccc',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.2
                }
            ]
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            plugins: { 
                legend: { position: 'top', labels: { boxWidth: 12, font: { weight: 'bold' } } },
                tooltip: { callbacks: { label: (ctx) => ctx.raw + " ms" } }
            },
            scales: { 
                y: { 
                    beginAtZero: true,
                    title: { display: true, text: 'Durasi (Milidetik)' }
                } 
            }
        }
    });

    // Shortcut Enter untuk Logout
    document.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.tagName !== 'INPUT') {
            document.getElementById("logoutForm").submit();
        }
    });
</script>
</body>
</html>