import json
import numpy as np
from src.utils.logger import log_access

def check_replay_attack(input_keystroke, history_strings):
    """
    Memeriksa apakah data keystroke yang dikirimkan identik atau 'terlalu mirip' 
    dengan data sebelumnya menggunakan jarak Euclidean.
    Mencegah serangan replay yang menggunakan noise mikroskopis.
    """
    if not history_strings:
        return False

    def extract_vec(data):
        if isinstance(data, str):
            data = json.loads(data)
        # Ambil dwell dan flight sebagai vektor utama
        dwell = np.array(data.get('dwell', []), dtype=float)
        flight = np.array(data.get('flight', []), dtype=float)
        return np.concatenate([dwell, flight])

    try:
        current_vec = extract_vec(input_keystroke)
        if len(current_vec) == 0: return False

        for h_str in history_strings:
            hist_vec = extract_vec(h_str)
            if len(hist_vec) != len(current_vec):
                continue
            
            # Hitung Jarak Euclidean Normal (L2)
            # Jika jarak sangat kecil (< 1e-4), kemungkinan besar ini adalah replay
            dist = np.linalg.norm(current_vec - hist_vec)
            
            # Threshold 0.001 (1ms akumulasi perbedaan di seluruh tombol)
            # Penyerang biasanya menyuntikkan noise < 1ms untuk tetap lolos ML tapi beda string
            if dist < 0.001:
                return True
    except Exception as e:
        print(f"Replay Check Error: {e}")
        return False
    
    return False

def verify_biometric(biom_core, user_id, username, input_keystroke, history_strings):
    """
    Menjalankan alur verifikasi biometrik lengkap.
    """
    # 1. Replay Detection
    if check_replay_attack(input_keystroke, history_strings):
        log_access('login_failed.log', f"REPLAY ATTACK | User: {username}", "Blocked replay attempt")
        return {"status": False, "reason": "Keamanan: Terdeteksi serangan Replay."}

    # 2. Biometric Analysis
    history_dicts = [json.loads(h) for h in history_strings]
    result = biom_core.analyze(input_keystroke, history_dicts, user_id)
    
    return result
