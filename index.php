<?php
// File rute utama yang mengarahkan pengguna ke dashboard jika sudah login.
session_start();

if (!empty($_SESSION['user_id'])) {
    header('Location: dashboard/index.php');
    exit();
}

header('Location: auth/login.php');
exit();