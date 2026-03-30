<?php
// Cek apakah sudah login atau belum
session_start();

if (isset($_SESSION['user_id'])) {
    // Jika sudah login, ke dashboard
    header("Location: dashboard/index.php");
} else {
    // Jika belum, ke halaman login
    header("Location: auth/login.php");
}
exit();