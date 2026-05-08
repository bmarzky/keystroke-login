import json
from src.utils.logger import log_access

def check_replay_attack(input_keystroke, history):
    """
    Memeriksa apakah data keystroke yang dikirimkan identik dengan data sebelumnya.
    Mencegah serangan replay.
    """
    current_norm = json.dumps(input_keystroke, sort_keys=True)
    for h_str in history:
        try:
            # Bandingkan JSON yang sudah dinormalisasi urutan key-nya
            if json.dumps(json.loads(h_str), sort_keys=True) == current_norm:
                return True
        except:
            continue
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
