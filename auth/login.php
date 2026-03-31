<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>

<h2>Login</h2>

<?php
if (isset($_GET['error'])) {
    echo '<p style="color: red;">' . htmlspecialchars($_GET['error']) . '</p>';
}
if (isset($_GET['success'])) {
    echo '<p style="color: green;">' . htmlspecialchars($_GET['success']) . '</p>';
}
?>

<form id="loginForm" action="process/login.php" method="POST" autocomplete="off">
    <input type="text" id="username" name="username" placeholder="Username" required autofocus autocomplete="off"><br><br>
    
    <input type="password" id="password" name="password" placeholder="Password" required autocomplete="new-password"><br><br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Login</button>
</form>

<p style="margin-top: 15px; font-size: 14px;"> Belum punya akun? <a href="register.php">Register</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
// Fungsi untuk memindahkan data dari JS ke input hidden
function prepareKeystroke() {
    // Memanggil fungsi dari file keystroke.js
    const data = window.getKeystrokeData();
    const hiddenInput = document.getElementById("keystrokeData");
    
    hiddenInput.value = data;
    
    // Debugging: Muncul di Console (F12)
    console.log("Data Keystroke terisi: ", data);
}

// listener submit form
document.getElementById("loginForm").addEventListener("submit", function(e) {
    prepareKeystroke();
    
    // Validasi akhir sebelum kirim ke PHP
    const hiddenValue = document.getElementById("keystrokeData").value;
    const parsed = JSON.parse(hiddenValue);
    
    if (parsed.dwell.length === 0) {
        e.preventDefault();
        alert("Pola ketikan tidak terdeteksi. Silakan ketik ulang password.");
    }
});

// Shortcut Enter di Username
document.getElementById("username").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("password").focus();
    }
});

// Shortcut Enter di Password
document.getElementById("password").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        // Memicu event submit agar listener prepareKeystroke berjalan
        document.getElementById("loginForm").requestSubmit(); 
    }
});

// Notifikasi Error/Success
const params = new URLSearchParams(window.location.search);
if (params.get("error")) alert(params.get("error"));
if (params.get("success")) alert(params.get("success"));
</script>

</body>
</html>