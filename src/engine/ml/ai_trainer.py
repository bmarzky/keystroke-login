import sys
import os
import json
import numpy as np

# Fix path agar bisa import folder 'src' saat dijalankan sebagai script
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.engine.core import BiometricCore
from src.engine.ml.ai_engine import AIEngine

def train_user_model_in_memory(user_id, history):
    """Fungsi utama untuk melatih AI secara in-memory (tanpa Disk I/O)."""
    core = BiometricCore()
    ai = AIEngine()
    
    if len(history) < 15:
        return False, f"Sampel kurang ({len(history)})"

    # Pastikan semua history berbentuk dictionary
    history = [json.loads(h) if isinstance(h, str) else h for h in history]

    try:
        # 2. Extract & Clean
        X = np.array([core.extractor.extract(h, history) for h in history])
        
        # Outlier Filter (Hapus data yang terlalu berantakan) menggunakan Shrinkage & pinv
        mu, cov = np.mean(X, 0), np.cov(X, rowvar=False) + np.eye(X.shape[1])*1e-4
        pinv_cov = np.linalg.pinv(cov)
        dists = [np.sqrt(max(0, (r-mu).T @ pinv_cov @ (r-mu))) for r in X]
        
        clean_X = X[np.array(dists) < 10.0]

        # 3. Training
        success, msg = ai.train(user_id, clean_X)
        return success, msg
        
    except Exception as e:
        return False, f"Crash during training: {str(e)}"

def train_user_model(user_id, data_path=None):
    """Fungsi legacy pembungkus untuk melatih AI membaca file temporary."""
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    history = []
    actual_path = data_path
    
    if actual_path and os.path.exists(actual_path):
        with open(actual_path, 'r') as f:
            data = json.load(f)
            history = data.get('history', [])
    else:
        # Fallback ke temp file standar menggunakan user_id
        scratch_dir = os.path.join(BASE_DIR, 'scratch')
        actual_path = os.path.join(scratch_dir, f"training_{user_id}.json")
        if os.path.exists(actual_path):
            with open(actual_path, 'r') as f:
                data = json.load(f)
                history = data.get('history', [])
                
    success, msg = train_user_model_in_memory(user_id, history)
    
    # Bersihkan file temp jika ada
    if actual_path and os.path.exists(actual_path):
        try: os.remove(actual_path)
        except: pass
        
    return success, msg

if __name__ == "__main__":
    if len(sys.argv) > 1:
        uid = sys.argv[1]
        path = sys.argv[2] if len(sys.argv) > 2 else None
        ok, m = train_user_model(uid, path)
        print(f"Status: {'Success' if ok else 'Failed'} | {m}")
    else:
        print("Usage: python engine/ml/ai_trainer.py [user_id] [optional_data_path]")
