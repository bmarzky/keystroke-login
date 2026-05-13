import os, joblib, glob, time
import numpy as np
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import RobustScaler

class AIEngine:
    def __init__(self, model_dir=None):
        # Gunakan path absolut dari root project untuk models agar lebih stabil di hosting
        if model_dir is None:
            # Mencari root directory dengan cara naik ke atas sampai ketemu folder 'models' atau root
            current = os.path.dirname(os.path.abspath(__file__))
            # Naik 3 level dari src/engine/ml/
            base_dir = os.path.abspath(os.path.join(current, "..", "..", ".."))
            self.model_dir = os.path.join(base_dir, 'models')
        else:
            self.model_dir = model_dir
            
        if not os.path.exists(self.model_dir):
            try: os.makedirs(self.model_dir, exist_ok=True)
            except: pass

    def _get_model_pattern(self, user_id):
        return os.path.join(self.model_dir, f"{user_id}_ocsvm_v*.joblib")

    def _get_latest_model_path(self, user_id):
        models = glob.glob(self._get_model_pattern(user_id))
        if not models:
            return None
        return sorted(models)[-1]

    def train(self, user_id, X_train):
        try:
            n_samples = len(X_train)
            if n_samples < 15:
                return False, f"Data minimal 15 (saat ini {n_samples})"

            adaptive_nu = float(np.clip(0.14 - (n_samples / 600.0), 0.08, 0.14))
            
            # Gunakan RobustScaler (kebal terhadap ketikan outlier / distraksi)
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X_train)
            
            model = OneClassSVM(kernel='rbf', gamma='scale', nu=adaptive_nu)
            model.fit(X_scaled)
            
            # Kalibrasi Confidence Berbasis Distribusi Pelatihan (Bukan Magic Number)
            train_scores = model.decision_function(X_scaled)
            score_std = np.std(train_scores) if np.std(train_scores) > 0 else 1.0
            calib_alpha = min(8.0, 2.0 / score_std) # Sigmoid adaptif dibatasi max 8.0 agar tidak terlampau tajam
            
            # Lifecycle & Versioning
            version = len(glob.glob(self._get_model_pattern(user_id))) + 1
            timestamp = int(time.time())
            save_path = os.path.join(self.model_dir, f"{user_id}_ocsvm_v{version}_{timestamp}.joblib")
            
            joblib.dump({
                'model': model, 
                'scaler': scaler, 
                'calib_alpha': calib_alpha,
                'nu': adaptive_nu,
                'n_train': n_samples,
                'version': version,
                'timestamp': timestamp
            }, save_path)
            
            self._cleanup_old_models(user_id, keep=3) # Simpan 3 versi terakhir untuk Rollback
            return True, f"Training Sukses v{version} (nu={adaptive_nu:.3f})"
        except Exception as e:
            return False, f"Training Fail: {str(e)}"

    def predict(self, user_id, features):
        model_path = self._get_latest_model_path(user_id)
        if not model_path:
            return None, 0.0, 0, 0.0
            
        try:
            data = joblib.load(model_path)
            model, scaler = data['model'], data['scaler']
            calib_alpha = data.get('calib_alpha', 12.0)
            
            X_test = scaler.transform([features])
            decision = int(model.predict(X_test)[0])
            raw_score = float(model.decision_function(X_test)[0])
            
            # Dynamic Confidence Calibration
            # Fungsi mapping halus yang menyesuaikan diri dengan karakter distribusi jarak tiap user
            confidence = float(1.0 / (1.0 + np.exp(-calib_alpha * raw_score))) 
            
            return decision, confidence, data.get('n_train', 0), raw_score
        except Exception as e:
            with open("ai_error.log", "a") as f:
                f.write(f"Predict Error for {user_id}: {str(e)}\n")
            return None, 0.0, 0, 0.0

    def _cleanup_old_models(self, user_id, keep=3):
        models = sorted(glob.glob(self._get_model_pattern(user_id)))
        for old_model in models[:-keep]:
            os.remove(old_model)
