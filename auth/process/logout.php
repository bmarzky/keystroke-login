<?php
session_start();
session_unset();    // Kosongkan variabel session
session_destroy();  // Hancurkan session di server
header("Location: ../login.php"); // Balik ke halaman login
exit(); 