<?php

class Logger {
    private static $logDir = __DIR__ . '/../ml/logs/';

    public static function log($filename, $content) {
        if (!is_dir(self::$logDir)) {
            mkdir(self::$logDir, 0777, true);
        }

        $timestamp = date('Y-m-d H:i:s');
        $divider = str_repeat("-", 60) . "\n";
        
        // Ensure content ends with a newline
        if (substr($content, -1) !== "\n") {
            $content .= "\n";
        }

        file_put_contents(self::$logDir . $filename, $content . $divider, FILE_APPEND);
    }

    public static function success($username, $details) {
        self::log('login_success.log', "SUCCESS | User: $username\n$details");
    }

    public static function failure($username, $details) {
        self::log('login_failed.log', "FAILURE | User: $username\n$details");
    }
}
