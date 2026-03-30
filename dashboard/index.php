<?php
session_start();
include "../config/database.php";

if (!isset($_SESSION['user_id'])) {
    header("Location: ../auth/login.php");
    exit();
}

$conn = getConnection();
$user_id = $_SESSION['user_id'];

// 1. Hitung TOTAL DATA
$stmtCount = $conn->prepare("SELECT COUNT(*) as total FROM keystroke_data WHERE user_id = ?");
$stmtCount->bind_param("i", $user_id);
$stmtCount->execute();
$totalData = $stmtCount->get_result()->fetch_assoc()['total'];

// 2. Ambil data TERAKHIR
$stmtData = $conn->prepare("SELECT features FROM keystroke_data WHERE user_id = ? ORDER BY id DESC LIMIT 1");
$stmtData->bind_param("i", $user_id);
$stmtData->execute();
$resData = $stmtData->get_result()->fetch_assoc();

$chartJson = $resData ? $resData['features'] : '{"dwell":[], "flight":[]}';
$dataArray = json_decode($chartJson, true);

// 3. HITUNG RATA-RATA DWELL TIME (Statistik Tambahan)
$avgDwell = 0;
if (!empty($dataArray['dwell'])) {
    $avgDwell = array_sum($dataArray['dwell']) / count($dataArray['dwell']);
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Skripsi</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body style="font-family: Arial; padding: 20px; line-height: 1.6;">

    <h2>Analisis Keystroke Dynamics</h2>
    <p>Halo, <b><?php echo $_SESSION['username']; ?></b></p>
    
    <div style="display: flex; gap: 20px; margin-bottom: 20px;">
        <div style="padding: 15px; border: 1px solid #ccc; border-radius: 8px;">
            <small>Total Sampel</small><br>
            <b style="font-size: 20px;"><?php echo $totalData; ?></b>
        </div>
        <div style="padding: 15px; border: 1px solid #ccc; border-radius: 8px;">
            <small>Rata-rata Tekan (Dwell)</small><br>
            <b style="font-size: 20px;"><?php echo round($avgDwell, 2); ?> ms</b>
        </div>
    </div>

    <div style="width: 600px; margin-bottom: 20px;">
        <canvas id="grafikKetikan"></canvas>
    </div>

    <form id="logoutForm" action="../auth/process/logout.php" method="POST">
        <button type="submit" style="padding: 8px 16px;">Logout</button>
    </form>

    <script>
    const dataKetikan = <?php echo $chartJson; ?>;

    new Chart(document.getElementById('grafikKetikan'), {
        type: 'line',
        data: {
            labels: dataKetikan.dwell.map((_, i) => i + 1),
            datasets: [
                {
                    label: 'Dwell Time',
                    data: dataKetikan.dwell,
                    borderColor: 'blue',
                    fill: false
                },
                {
                    label: 'Flight Time',
                    data: dataKetikan.flight,
                    borderColor: 'red',
                    fill: false
                }
            ]
        }
    });

    // Enter = Logout
    document.addEventListener("keydown", function(e) {
        if (e.key === "Enter") document.getElementById("logoutForm").submit();
    });
    </script>
</body>
</html>