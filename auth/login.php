<!DOCTYPE html>
<html>
<head>
    <title>Login - Biometric System</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <style>
        /* Container pesan agar layout tidak melompat */
        #message-container { min-height: 45px; margin-bottom: 15px; }
        
        /* Gaya box pesan PHP */
        .error-box { color: red; font-weight: bold; border: 1px solid red; padding: 8px; border-radius: 4px; background: #fff5f5; }
        .success-box { color: green; font-weight: bold; border: 1px solid green; padding: 8px; border-radius: 4px; background: #f5fff5; }
        
        /* Efek transisi halus untuk semua pesan */
        .error-box, .success-box, #js-error-msg {
            transition: opacity 0.5s ease;
        }
    </style>
</head>
<body>

<h2>Login</h2>

<div id="message-container">
    <?php
    date_default_timezone_set('Asia/Jakarta');
    $time = date('H:i:s');

    if (isset($_GET['error'])) {
        // TAMBAHKAN class="php-msg" dan id="status-msg"
        echo '<div id="status-msg" class="php-msg" style="color: red;">[' . $time . '] ' . htmlspecialchars($_GET['error']) . '</div>';
    }
    if (isset($_GET['success'])) {
        // TAMBAHKAN class="php-msg" dan id="status-msg"
        echo '<div id="status-msg" class="php-msg" style="color: green;"> [' . $time . '] ' . htmlspecialchars($_GET['success']) . '</div>';
    }
    ?>
    <div id="js-error-msg" style="color: red;"></div>
</div>

<form id="loginForm" action="process/login.php" method="POST" autocomplete="off" novalidate>
    <div class="input-group">
        <input type="text" id="username" name="username" placeholder="Username" required autofocus autocomplete="off">
    </div>
    <br>
    <div class="input-group">
        <input type="password" id="password" name="password" placeholder="Password" required autocomplete="current-password" onpaste="return false;" ondrop="return false;">
    </div>
    <br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Login</button>
</form>

<p style="margin-top: 20px; font-size: 14px;">Belum punya akun? <a href="register.php">Daftar di sini</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
/**
 * FUNGSI AUTO-HIDE UNIVERSAL
 * Menangani pesan dari PHP (class .php-msg) dan JS (#js-error-msg)
 */
function initAutoHide() {
    // 1. Ambil semua elemen yang mungkin berisi pesan
    const msgIds = ['status-msg', 'js-error-msg'];

    msgIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        // Jika ID adalah js-error-msg, pakai Observer (karena teks muncul tanpa reload)
        if (id === 'js-error-msg') {
            const observer = new MutationObserver(() => {
                if (el.innerText !== "") startTimer(el);
            });
            observer.observe(el, { childList: true });
        } 
        // Jika status-msg dari PHP sudah ada isinya saat page load
        else if (el.innerText.trim() !== "") {
            startTimer(el);
        }
    });

    function startTimer(el) {
        // Reset opacity dulu agar terlihat
        el.style.opacity = "1";
        
        setTimeout(() => {
            el.style.opacity = "0"; // Mulai memudar
            setTimeout(() => {
                el.innerText = ""; // Hapus teks
                el.style.opacity = "1"; // Reset untuk pesan berikutnya
            }, 500);
        }, 3000); // Tampil selama 3 detik
    }
}

document.addEventListener("DOMContentLoaded", initAutoHide);

// --- LOGIKA DATA KEYSTROKE ---

function prepareKeystroke() {
    if (typeof window.getKeystrokeData === "function") {
        const data = window.getKeystrokeData();
        document.getElementById("keystrokeData").value = data;
        return JSON.parse(data);
    }
    return null;
}

document.getElementById("loginForm").addEventListener("submit", function(e) {
    const parsed = prepareKeystroke();
    const jsErrorDisplay = document.getElementById("js-error-msg");
    
    if (!parsed || !parsed.dwell || parsed.dwell.length === 0) {
        e.preventDefault();
        jsErrorDisplay.innerText = "Pola ketikan tidak terdeteksi. Silakan ketik ulang password.";
    }
});

// Navigasi Shortcut Enter
document.getElementById("username").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("password").focus();
    }
});

document.getElementById("password").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        setTimeout(() => {
            document.getElementById("loginForm").requestSubmit();
        }, 100);
    }
});
</script>
</body>
</html>