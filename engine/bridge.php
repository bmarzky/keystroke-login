<?php

class KeystrokeManager {
    
    private function getPythonPath() {
        $path = trim(shell_exec('where python 2>NUL') ?? '');
        $path = strtok($path, "\n");
        return empty($path) ? 'python' : $path;
    }

    public function verify($historyData, $inputJson) {
        $input = json_decode($inputJson, true);

        if (!isset($input['dwell'], $input['flight'], $input['d2d'], $input['u2u'], $input['speed'])) {
            return ['status' => false, 'score' => 0, 'reason' => 'Fitur tidak lengkap'];
        }

        if ($input['speed'] > 1000 || $input['speed'] <= 0) {
            return ['status' => false, 'score' => 0, 'reason' => 'Kecepatan tidak valid'];
        }

        $history = [];
        if (!empty($historyData)) {
            foreach ($historyData as $json) {
                $data = json_decode($json, true);
                if (json_last_error() === JSON_ERROR_NONE) {
                    $history[] = $data;
                }
            }
        }

        $payload = [
            'input' => $input,
            'history' => $history
        ];
        
        $tmpFile = tempnam(sys_get_temp_dir(), 'bio_') . '.json';
        file_put_contents($tmpFile, json_encode($payload));
        
        $pyCore = realpath(__DIR__ . '/core.py');
        $pyExec = $this->getPythonPath();
        
        # Gunakan format command yang lebih aman untuk Windows (bungkus seluruh string dengan kutip ganda jika perlu)
        $command = "\"$pyExec\" \"$pyCore\" \"$tmpFile\" 2>&1";
        
        $output = shell_exec($command);
        $output = trim($output ?? '');
        @unlink($tmpFile);
        
        if (empty($output)) {
            return ['status' => false, 'score' => 0, 'reason' => 'Python Output Empty'];
        }
        
        $result = json_decode($output, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
             # Jika gagal parse JSON, kemungkinan besar $output berisi pesan error Python yang asli
             return ['status' => false, 'score' => 0, 'reason' => 'Python Debug: ' . substr($output, 0, 100)];
        }
        
        return [
           'status'        => $result['status']         ?? false,
           'score'         => $result['score']           ?? 0,
           'threshold'     => $result['threshold']       ?? 0,
           'should_update' => $result['should_update_history'] ?? false,
           'reason'        => $result['reason']          ?? 'Error',
           'method'        => $result['method']          ?? 'Unknown',
           'n_features'    => $result['n_features']      ?? null,
           'n_samples'     => $result['n_samples']       ?? null,
           'mahal_dist'     => $result['mahal_dist']      ?? null,
           'speed_dev'      => $result['speed_dev']       ?? null,
           'components'     => $result['components']      ?? [],
           'adaptive_gates' => $result['adaptive_gates']  ?? [],
        ];



    }
}
