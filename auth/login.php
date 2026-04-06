<!DOCTYPE html>
<html>
<head>
    <title>Login - Biometric System</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <style>
        /* Memastikan container pesan tidak merusak layout saat kosong */
        #message-container { min-height: 45px; margin-bottom: 15px; }
        .error-box { color: red; font-weight: bold; border: 1px solid red; padding: 8px; border-radius: 4px; background: #fff5f5; }
        .success-box { color: green; font-weight: bold; border: 1px solid green; padding: 8px; border-radius: 4px; background: #f5fff5; }
    </style>
</head>
<body>

<h2>Login</h2>

<div id="message-container">
    <?php
    date_default_timezone_set('Asia/Jakarta');
    if (isset($_GET['error'])) {
        echo '<div class="error-box">' . htmlspecialchars($_GET['error']) . '</div>';
    }
    if (isset($_GET['success'])) {
        echo '<div class="success-box">' . htmlspecialchars($_GET['success']) . '</div>';
    }
    ?>
    <div id="js-error-msg" style="color: red; font-size: 14px; font-weight: bold; margin-top: 5px;"></div>
</div>

<form id="loginForm" action="process/login.php" method="POST" autocomplete="off" novalidate>
    <div class="input-group">
        <input type="text" id="username" name="username" placeholder="Username" required autofocus autocomplete="off">
    </div>
    <br>
    <div class="input-group">
        <input type="password" id="password" name="password" placeholder="Password" required autocomplete="current-password">
    </div>
    <br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Login</button>
</form>

<p style="margin-top: 20px; font-size: 14px;">Belum punya akun? <a href="register.php">Daftar di sini</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
// Fungsi utama untuk menyiapkan data
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
    
    // Validasi: Apakah pola terekam? (Dwell harus memiliki data)
    if (!parsed || !parsed.dwell || parsed.dwell.length === 0) {
        e.preventDefault();
        jsErrorDisplay.innerText = "⚠️ Pola ketikan tidak terdeteksi. Silakan ketik ulang password.";
        setTimeout(() => { jsErrorDisplay.innerText = ""; }, 3000);
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
        // Beri jeda 100ms agar event 'keyup' pada tombol terakhir sempat diproses 
        // oleh keystroke.js sebelum form terkirim
        setTimeout(() => {
            document.getElementById("loginForm").requestSubmit();
        }, 100);
    }
});
</script>
</body>
</html>