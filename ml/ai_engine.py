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
        """Melatih model AI untuk user tertentu menggunakan ID Database."""
        try:
            if len(X_train) < 10:
                return False, "Data tidak cukup (min 10)"

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_train)
            
            # nu=0.08: toleransi 8% outlier saat training untuk model yang lebih luwes
            model = OneClassSVM(kernel='rbf', gamma='scale', nu=0.08)
            model.fit(X_scaled)
            
            # Simpan model & scaler dalam satu file
            joblib.dump({'model': model, 'scaler': scaler}, self._get_model_path(user_id))
            return True, "Training Sukses"
        except Exception as e:
            return False, f"Training Fail: {str(e)}"

    def predict(self, user_id, features):
        """Memprediksi apakah gaya ketik sesuai dengan profil ID user."""
        model_path = self._get_model_path(user_id)
        if not os.path.exists(model_path):
            return None, None
            
        try:
            data = joblib.load(model_path)
            model, scaler = data['model'], data['scaler']
            
            X_test = scaler.transform([features])
            decision = model.predict(X_test)[0]
            # score_samples memberikan nilai kemiripan (positif=normal, negatif=aneh)
            score = model.score_samples(X_test)[0]
            
            return int(decision), float(score)
        except:
            return None, None
