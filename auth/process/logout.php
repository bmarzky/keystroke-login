<?php
session_start();

// Bersihkan data dan hancurkan sesi aktif
session_unset();
session_destroy();  

header("Location: ../login.php");
exit();