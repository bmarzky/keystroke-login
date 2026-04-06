<!DOCTYPE html>
<html>
<head>
    <title>Register</title>
    <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>

<h2>Register</h2>

<div id="message-container" style="min-height: 25px; margin-bottom: 15px;">
    <?php
    date_default_timezone_set('Asia/Jakarta');
    $time = date('H:i:s');

    if (isset($_GET['error'])) {
        echo '<div id="status-msg" style="color: red; font-weight: bold;">[' . $time . '] ' . htmlspecialchars($_GET['error']) . '</div>';
    }
    if (isset($_GET['success'])) {
        echo '<div id="status-msg" style="color: green; font-weight: bold;">[' . $time . '] ' . htmlspecialchars($_GET['success']) . '</div>';
    }
    ?>
    <div id="js-error-msg" style="color: red; font-size: 14px; font-weight: bold;"></div>
</div>

<form id="registerForm" action="process/register.php" method="POST" autocomplete="off" novalidate>
    <input type="text" id="username" name="username" placeholder="Username" required autofocus autocomplete="off"><br><br>
    
    <input type="password" id="password" name="password" placeholder="Password" required autocomplete="new-password"><br><br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Register</button>
</form>

<p style="margin-top: 15px; font-size: 14px;"> Sudah punya akun? <a href="login.php">Login</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
// Kirim keystroke saat submit
document.getElementById("registerForm").addEventListener("submit", function(e) {
    const jsErrorDisplay = document.getElementById("js-error-msg");
    const keystrokeInput = document.getElementById("keystrokeData");
    
    if (typeof window.getKeystrokeData === "function") {
        const dataStr = window.getKeystrokeData();
        const parsed = JSON.parse(dataStr);
        
        // VALIDASI KRITIS: Pastikan semua array fitur terisi
        // Minimal password biasanya 6-8 karakter, jadi dwell minimal harus ada isinya
        if (!parsed.dwell || parsed.dwell.length < 5) {
            e.preventDefault();
            jsErrorDisplay.innerText = "Pola ketikan terlalu pendek atau tidak terdeteksi. Silakan ketik ulang.";
            return;
        }

        // Masukkan data ke input hidden
        keystrokeInput.value = dataStr;
        console.log("Submitting Keystroke Data...", parsed);
    } else {
        e.preventDefault();
        jsErrorDisplay.innerText = "Sistem Biometrik belum siap. Segarkan halaman.";
    }
});

// Shortcut Enter: Username -> Password
document.getElementById("username").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("password").focus();
    }
});

// Shortcut Enter: Password -> Submit
document.getElementById("password").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("registerForm").requestSubmit();
    }
});
</script>

</body>
</html>