<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Halaman pendaftaran akun dengan Keystroke Dynamics">
    <title>Register</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.css"/>
    <link rel="stylesheet" href="../assets/tutorial/guide.css">
</head>
<body>
    <div class="auth-wrapper">
        <h2 class="auth-title">Register</h2>

        <div class="message-container">
            <?php
            date_default_timezone_set('Asia/Jakarta');
            $time = date('H:i:s');

            if (isset($_GET['error'])) {
                echo '<div id="status-msg" class="php-message error-box"> [' . $time . '] ' . htmlspecialchars($_GET['error']) . '</div>';
            }
            if (isset($_GET['success'])) {
                echo '<div id="status-msg" class="php-message success-box"> [' . $time . '] ' . htmlspecialchars($_GET['success']) . '</div>';
            }
            ?>
            <div id="js-error-msg"></div>
        </div>

        <form id="registerForm" class="auth-form" action="process/register.php" method="POST" autocomplete="off" novalidate>
            <input type="text" id="username" name="username" placeholder="Username Anda..." required autofocus autocomplete="off">
            <input type="password" id="password" name="password" placeholder="Password" required autocomplete="new-password">
            <input type="hidden" name="keystroke" id="keystrokeData">

            <button type="submit">Register</button>
        </form>

        <p class="page-note">Sudah punya akun? <a href="login.php">Login</a></p>
    </div>

<script src="../assets/js/keystroke.js"></script>
<script src="../assets/js/auth-forms.js"></script>
<script src="https://cdn.jsdelivr.net/npm/driver.js@1.0.1/dist/driver.js.iife.js"></script>
<script src="../assets/tutorial/guide.js"></script>
</body>
</html>
