import os

def log_access(filename, header, content):
    log_dir = 'logs/'
    if not os.path.exists(log_dir): 
        os.makedirs(log_dir)
    
    with open(os.path.join(log_dir, filename), 'a', encoding='utf-8') as f:
        f.write("-" * 60 + "\n")
        f.write(f"{header}\n{content}\n")

def format_log(uid, result, history, raw_input):
    ag = result.get('adaptive_gates', {})
    comp = result.get('components', {})
    
    log = f"  User ID       : {uid}\n"
    log += f"  Method        : {result.get('method', 'Unknown')}\n"
    log += f"  History Count : {len(history)} sampel\n"
    log += f"  Score         : {result.get('score', 0):.4f}\n"
    log += f"  Threshold     : {result.get('threshold', 0):.4f}\n"
    log += f"  Reason        : {result.get('reason', 'N/A')}\n"
    
    # Tambahkan Info Debug jika ada (Misal: Speed Forgiven)
    debug_info = result.get('reason_debug')
    if debug_info:
        log += f"  Debug Info    : {debug_info}\n"
    
    # Mahalanobis
    log += f"  --- Mahalanobis Gate ---\n"
    log += f"  Distance      : {result.get('mahal_dist', 'N/A')}\n"
    log += f"  Current Gate  : {ag.get('mahal_gate', 'N/A')}\n"
    
    # OCSVM
    log += f"  --- OCSVM Gate ---\n"
    ai_score = result.get('ai_score', 'None')
    if ai_score != "None" and ai_score is not None:
        a_score = float(ai_score)
        log += f"  AI Score      : {a_score:.4f}\n"
    else:
        log += f"  AI Score      : None\n"
    log += f"  AI Status     : {result.get('ai_status', 'N/A')}\n"
    raw_dist = result.get('ai_raw_dist')
    if raw_dist is not None:
        log += f"  AI Raw Dist   : {raw_dist:.4f}\n"
    
    n_train = result.get('n_train', 0)
    if n_train > 0:
        log += f"  Model Info    : Trained on {n_train} samples\n"
    
    # Adaptive
    log += f"  --- Adaptive Gate ---\n"
    log += f"  Speed Gate    : {int(ag.get('speed_gate', 0.4) * 100)}%\n"
    log += f"  Threshold     : {result.get('threshold', 0.68):.4f}\n"
    
    # Biometric Method
    log += f"  --- Sequential Mahalanobis-SVM ---\n"
    weights = result.get('weights', [])
    if weights and len(weights) == 6:
        log += f"  Weights (P)   : R:{weights[0]:.2f} | C:{weights[1]:.2f} | S:{weights[2]:.2f} | F:{weights[3]:.2f} | RT:{weights[4]:.2f} | ST:{weights[5]:.2f}\n"
    
    log += f"  Rhythm        : {comp.get('rhythm', 0)*100:.1f}%  [Euclidean]\n"
    log += f"  Corr.         : {comp.get('corr', 0)*100:.1f}%  [Pearson]\n"
    log += f"  Speed         : {comp.get('speed', 0)*100:.1f}%  [CPM]\n"
    log += f"  Flow          : {comp.get('flow', 0)*100:.1f}%  [Accel]\n"
    log += f"  Ratio         : {comp.get('ratio', 0)*100:.1f}%\n"
    log += f"  Stability     : {comp.get('stability', 0)*100:.1f}%\n"
    
    # Raw Data
    log += f"  --- Raw Keystroke Data ---\n"
    log += f"  Speed         : {raw_input.get('speed', 0):.4f} char/s\n"
    log += f"  Dwell         : {raw_input.get('dwell', [])}\n"
    log += f"  Flight        : {raw_input.get('flight', [])}\n"
    log += f"  Trigraph      : {raw_input.get('trigraph', [])}\n"
    log += f"  Jitter        : {raw_input.get('jitter', 0.0):.6f}\n"
    
    log += f"  History Updated: {'Ya' if result.get('should_update_history') else 'Tidak'}\n"
    
    return log
