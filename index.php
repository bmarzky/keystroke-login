<?php
// File rute utama
session_start();

// Log akses untuk debugging
error_log("Access to index.php at " . date('Y-m-d H:i:s'));

if (isset($_SESSION['user_id'])) {
    header("Location: dashboard/index.php");
} else {
    header("Location: auth/login.php");
}
exit();