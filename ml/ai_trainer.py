import sys
import os
import json
import numpy as np

# Fix pathing agar bisa menemukan folder 'engine' dan 'ml' dari manapun skrip ini dipanggil
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path: sys.path.append(root)

from engine.core import BiometricCore
from ml.ai_engine import AIEngine

def train_user_model(user_id, data_path=None):
    """Fungsi utama untuk melatih AI berdasarkan ID User."""
    core = BiometricCore()
    ai = AIEngine()
    
    # 1. Load Data
    history = []
    if data_path and os.path.exists(data_path):
        with open(data_path, 'r') as f:
            data = json.load(f)
            history = data.get('history', [])
    else:
        # Fallback ke temp file standar menggunakan user_id (Gunakan path absolut)
        scratch_dir = os.path.join(root, 'scratch')
        temp_path = os.path.join(scratch_dir, f"training_{user_id}.json")
        if os.path.exists(temp_path):
            with open(temp_path, 'r') as f:
                data = json.load(f)
                history = data.get('history', [])

    if len(history) < 15:
        return False, f"Sampel kurang ({len(history)})"

    # Pastikan semua history berbentuk dictionary (bongkar JSON jika perlu)
    history = [json.loads(h) if isinstance(h, str) else h for h in history]

    # 2. Extract & Clean (Gunakan core untuk ambil fitur biometrik)
    X = np.array([core.extract(h, history) for h in history])
    
    # Outlier Filter (Hapus data yang terlalu berantakan)
    mu, cov = np.mean(X, 0), np.cov(X, rowvar=False) + np.eye(X.shape[1])*1e-3
    cinv = np.linalg.inv(cov)
    dists = [np.sqrt((r-mu).T @ cinv @ (r-mu)) for r in X]
    
    clean_X = X[np.array(dists) < 10.0]

    # 3. Training
    success, msg = ai.train(user_id, clean_X)
    
    # Bersihkan file temp jika ada (Penting agar folder scratch tetap bersih)
    if temp_path and os.path.exists(temp_path):
        try: os.remove(temp_path)
        except: pass
        
    return success, msg

if __name__ == "__main__":
    if len(sys.argv) > 1:
        uid = sys.argv[1]
        path = sys.argv[2] if len(sys.argv) > 2 else None
        ok, m = train_user_model(uid, path)
        print(f"Status: {'Success' if ok else 'Failed'} | {m}")
    else:
        print("Usage: python ml/ai_trainer.py [user_id] [optional_data_path]")
