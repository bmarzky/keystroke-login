<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>

<h2>Login</h2>

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

<form id="loginForm" action="process/login.php" method="POST" autocomplete="off" novalidate>
    <input type="text" id="username" name="username" placeholder="Username" required autofocus autocomplete="off"><br><br>
    
    <input type="password" id="password" name="password" placeholder="Password" required autocomplete="new-password"><br><br>   

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Login</button>
</form>

<p style="margin-top: 15px; font-size: 14px;"> Belum punya akun? <a href="register.php">Register</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
function prepareKeystroke() {
    const data = window.getKeystrokeData();
    const hiddenInput = document.getElementById("keystrokeData");
    hiddenInput.value = data;
}

document.getElementById("loginForm").addEventListener("submit", function(e) {
    prepareKeystroke();
    
    const hiddenValue = document.getElementById("keystrokeData").value;
    const parsed = JSON.parse(hiddenValue);
    const jsErrorDisplay = document.getElementById("js-error-msg");
    
    // Jika dwell kosong (biasanya karena belum ngetik atau error reset)
    if (parsed.dwell.length === 0) {
        e.preventDefault();
        jsErrorDisplay.innerText = "Pola ketikan tidak terdeteksi. Silakan ketik ulang password.";
        
        // Auto-hide pesan error JS dalam 3 detik
        setTimeout(() => { jsErrorDisplay.innerText = ""; }, 3000);
    }
});

// Shortcut Enter
document.getElementById("username").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("password").focus();
    }
});

document.getElementById("password").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("loginForm").requestSubmit(); 
    }
});
</script>
</body>
</html>