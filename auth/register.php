<!DOCTYPE html>
<html>
<head>
    <title>Register</title>
    <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>

<h2>Register</h2>

<?php
if (isset($_GET['error'])) {
    echo '<p style="color: red;">' . htmlspecialchars($_GET['error']) . '</p>';
}
if (isset($_GET['success'])) {
    echo '<p style="color: green;">' . htmlspecialchars($_GET['success']) . '</p>';
}
?>

<form id="registerForm" action="process/register.php" method="POST" autocomplete="off" novalidate>
    <input type="text" id="username" name="username" placeholder="Username" required autofocus><br><br>
    
    <input type="password" id="password" name="password" placeholder="Password" required><br><br>

    <input type="hidden" name="keystroke" id="keystrokeData">

    <button type="submit">Register</button>
</form>

<p style="margin-top: 15px; font-size: 14px;"> Sudah punya akun? <a href="login.php">Login</a></p>

<script src="../assets/js/keystroke.js"></script>

<script>
// Kirim keystroke saat submit
document.getElementById("registerForm").addEventListener("submit", function() {
    // Pastikan memanggil fungsi dari keystroke.js yang sudah diperbaiki sebelumnya
    if (typeof window.getKeystrokeData === "function") {
        document.getElementById("keystrokeData").value = window.getKeystrokeData();
    } else {
        // fallback jika tidak menggunakan window object
        document.getElementById("keystrokeData").value = getKeystrokeData();
    }
});

// Enter pindah field
document.getElementById("username").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("password").focus();
    }
});

// -----------------------------------------------
</script>

</body>
</html>