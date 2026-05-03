import os

def log_access(filename, header, content):
    log_dir = 'ml/logs/'
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
    
    # Mahalanobis
    log += f"  --- Mahalanobis Gate ---\n"
    log += f"  Distance      : {result.get('mahal_dist', 'N/A')}\n"
    log += f"  Current Gate  : {ag.get('mahal_gate', 'N/A')}\n"
    
    # OCSVM
    log += f"  --- OCSVM Gate ---\n"
    log += f"  AI Score      : {result.get('ai_score', 'N/A')}\n"
    log += f"  AI Status     : {result.get('ai_status', 'N/A')}\n"
    
    # Adaptive
    log += f"  --- Adaptive Gate ---\n"
    log += f"  Speed Gate    : {int(ag.get('speed_gate', 0.4) * 100)}%\n"
    log += f"  Threshold     : {result.get('threshold', 0.68):.4f}\n"
    
    # Titanium Fusion
    log += f"  --- Titanium Fusion Gate ---\n"
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
    
    log += f"  History Updated: {'Ya' if result.get('should_update_history') else 'Tidak'}\n"
    
    return log
