<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Halaman pendaftaran akun dengan Keystroke Dynamics">
    <title>Register</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <link rel="stylesheet" href="../assets/tutorial/guide.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.css"/>
    <style>
        /* Container pesan agar tidak melompat */
        #message-container { min-height: 25px; margin-bottom: 15px; font-size: 14px; }
        
        /* Efek transisi halus untuk teks */
        #status-msg, #js-error-msg {
            transition: opacity 0.5s ease;
            opacity: 1;
        }
    </style>
</head>
<body>

<h2>Register</h2>

<div id="message-container">
    <?php
    date_default_timezone_set('Asia/Jakarta');
    $time = date('H:i:s');

    if (isset($_GET['error'])) {
        echo '<div id="status-msg" style="color: red;"> [' . $time . '] ' . htmlspecialchars($_GET['error']) . '</div>';
    }
    if (isset($_GET['success'])) {
        echo '<div id="status-msg" style="color: green;"> [' . $time . '] ' . htmlspecialchars($_GET['success']) . '</div>';
    }
    ?>
    <div id="js-error-msg" style="color: red;"></div>
</div>

<form id="registerForm" action="process/register.php" method="POST" autocomplete="off" novalidate>
    <input type="text" id="username" name="username" placeholder="Username Anda..." required autofocus autocomplete="off"><br><br>
    
    <input type="password" id="password" name="password" placeholder="Password" required autocomplete="new-password" onpaste="return false;" ondrop="return false;"><br><br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Register</button>
</form>

<p style="margin-top: 15px; font-size: 14px;"> Sudah punya akun? <a href="login.php">Login</a></p>

<script src="../assets/js/keystroke.js"></script>
<script src="https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.js.iife.js"></script>
<script src="../assets/tutorial/guide.js"></script>
<script>

// Fungsi auto hide pesan
function setupAutoHide() {
    const statusMsg = document.getElementById("status-msg");
    const jsErrorMsg = document.getElementById("js-error-msg");

    // 1. Cek pesan dari PHP (saat halaman pertama kali dimuat)
    if (statusMsg && statusMsg.innerText.trim() !== "") {
        startTimer(statusMsg);
    }

    // 2. Pantau pesan dari JavaScript (biometrik) secara dinamis
    const observer = new MutationObserver(() => {
        if (jsErrorMsg.innerText.trim() !== "") {
            startTimer(jsErrorMsg);
        }
    });
    
    if (jsErrorMsg) {
        observer.observe(jsErrorMsg, { childList: true });
    }

    function startTimer(el) {
        el.style.opacity = "1"; // Pastikan terlihat
        setTimeout(() => {
            el.style.opacity = "0"; // Mulai memudar
            setTimeout(() => {
                el.innerText = ""; // Kosongkan teks
                el.style.opacity = "1"; // Reset untuk pesan berikutnya
            }, 500);
        }, 3000); // Tampil selama 3 detik
    }
}

document.addEventListener("DOMContentLoaded", setupAutoHide);

// Logika form register
document.getElementById("registerForm").addEventListener("submit", function(e) {
    const jsErrorDisplay = document.getElementById("js-error-msg");
    const keystrokeInput = document.getElementById("keystrokeData");
    
    if (typeof window.getKeystrokeData === "function") {
        const dataStr = window.getKeystrokeData();
        const parsed = JSON.parse(dataStr);
        
        if (!parsed.dwell || parsed.dwell.length < 5) {
            e.preventDefault();
            jsErrorDisplay.innerText = "Pola ketikan terlalu pendek. Silakan ketik ulang.";
            return;
        }

        keystrokeInput.value = dataStr;
    } else {
        e.preventDefault();
        jsErrorDisplay.innerText = "Sistem Biometrik belum siap.";
    }
});

// Navigasi Shortcut
document.getElementById("username").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); document.getElementById("password").focus(); }
});

document.getElementById("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        setTimeout(() => { document.getElementById("registerForm").requestSubmit(); }, 100);
    }
});
</script>

</body>
</html>