import json
import os
import time
import numpy as np
from src.utils.logger import log_access

# ---------------------------------------------------------------------------
# Replay-detection threshold (Euclidean distance in combined dwell+flight space).
#
# REPLAY_EPSILON = 0.001 (default)
#   Rationale: Physical human variability across separate keystrokes is typically
#   > 5 ms per key.  A 10-key password with 5 ms spread gives a minimum expected
#   L2 distance of sqrt(10) * 0.005 ≈ 0.016, well above this threshold.
#   Values below 0.001 risk treating hardware floating-point rounding as a replay.
#   Values above 0.01 may miss sophisticated replay with injected micro-noise.
#   Override via environment variable REPLAY_EPSILON before starting the server.
# ---------------------------------------------------------------------------
REPLAY_EPSILON = float(os.getenv('REPLAY_EPSILON', '0.001'))

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

            # Hitung Jarak Euclidean Normal (L2).
            # Jika jarak sangat kecil (di bawah REPLAY_EPSILON), kemungkinan ini replay.
            dist = np.linalg.norm(current_vec - hist_vec)

            # Gunakan np.isclose dengan absolute tolerance (atol=REPLAY_EPSILON) agar
            # perbandingan robust terhadap floating-point rounding error.
            # Cek eksplisit `dist < REPLAY_EPSILON` ditambahkan sebagai fast-path.
            if dist < REPLAY_EPSILON or np.isclose(dist, 0.0, atol=REPLAY_EPSILON):
                # Log detail kecil untuk forensik
                try:
                    log_access('login_failed.log',
                               f"{time.strftime('%Y-%m-%d %H:%M:%S')} | REPLAY DETECTED |",
                               f"UserVecLen={len(current_vec)} Dist={dist:.6f}")
                except Exception:
                    pass
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
