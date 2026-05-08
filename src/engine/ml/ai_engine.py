import os, joblib
import numpy as np
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler

class AIEngine:
    def __init__(self, model_dir=None):
        if model_dir is None:
            # Set default path ke folder 'ml/models'
            self.model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        else:
            self.model_dir = model_dir
            
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

    def _get_model_path(self, user_id):
        # Gunakan ID Database untuk nama model agar lebih privat dan konsisten
        return os.path.join(self.model_dir, f"{user_id}_ocsvm.joblib")

    def train(self, user_id, X_train):
        """Melatih model AI dengan tuning otomatis berdasarkan jumlah data."""
        try:
            n_samples = len(X_train)
            if n_samples < 15:
                return False, f"Data minimal 15 (saat ini {n_samples})"

            # ADAPTIVE NU: Dijaga tetap ketat (0.10 - 0.15) untuk keamanan tinggi
            # Lebih besar nu = lebih ketat batasannya
            adaptive_nu = float(np.clip(0.18 - (n_samples / 500.0), 0.12, 0.18))

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_train)
            
            model = OneClassSVM(kernel='rbf', gamma='scale', nu=adaptive_nu)
            model.fit(X_scaled)
            
            # Simpan model & scaler
            joblib.dump({
                'model': model, 
                'scaler': scaler, 
                'nu': adaptive_nu,
                'n_train': n_samples
            }, self._get_model_path(user_id))
            
            return True, f"Training Sukses (nu={adaptive_nu:.3f})"
        except Exception as e:
            return False, f"Training Fail: {str(e)}"

    def predict(self, user_id, features):
        """Prediksi dengan skor kepercayaan (Confidence Score)."""
        model_path = self._get_model_path(user_id)
        if not os.path.exists(model_path):
            return None, 0.0, 0, 0.0
            
        try:
            data = joblib.load(model_path)
            model, scaler = data['model'], data['scaler']
            
            X_test = scaler.transform([features])
            decision = int(model.predict(X_test)[0])
            
            # score_samples: jarak ke hyperplane (makin positif makin yakin 'asli')
            raw_score = float(model.score_samples(X_test)[0])
            
            # Mapping raw_score ke 0-1 (Dipersulit: On the boundary = 0.3 Confidence)
            confidence = float(1.0 / (1.0 + np.exp(-12 * (raw_score - 0.05)))) 
            
            return decision, confidence, data.get('n_train', 0), raw_score
        except Exception as e:
            return None, 0.0, 0, 0.0
