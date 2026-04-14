"""
Skrip untuk prediksi dan otentikasi berdasarkan model yang sudah dilatih.
Akan dipanggil untuk membandingkan input keystroke login dengan baseline model.
"""

import sys
import os
import json
import joblib
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(__file__), '../model')

def load_model(user_id):
    """Memuat model ML yang sudah disimpan spesifik untuk tiap user."""
    model_path = os.path.join(MODEL_DIR, f'keystroke_model_{user_id}.pkl')
    if not os.path.exists(model_path):
        # Ini menjadi pertanda bahwa data masih dikumpulkan dan SVM belum dilatih
        print(json.dumps({"status": "fallback", "message": "SVM Model Threshold belum tercapai. Lakukan fallback ke PHP Mahalanobis."}))
        sys.exit(0)
    return joblib.load(model_path)

def extract_features(data):
    """
    Parsing dict keystroke {dwell, flight, d2d, u2u, speed}
    menjadi vektor flat numerik yang sama persis dengan format training.
    """
    if not all(k in data for k in ['dwell', 'flight', 'd2d', 'u2u', 'speed']):
        raise ValueError("Fitur keystroke tidak lengkap. Harus ada: dwell, flight, d2d, u2u, speed.")
    vector = data['dwell'] + data['flight'] + data['d2d'] + data['u2u'] + [float(data['speed'])]
    return np.array(vector).reshape(1, -1)

def predict(features, model):
    """
    Prediksi menggunakan model terlatih.
    OneClassSVM mengembalikan:
       1 jika inlier (valid user)
      -1 jika outlier (imposter/invalid user)
    """
    prediction = model.predict(features)
    return prediction[0]

def main():
    # Skrip menerima argumen: python predict.py <user_id> <path_to_json_file>
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Argumen user_id atau path file tidak disertakan"}))
        sys.exit(1)

    user_id   = sys.argv[1]
    json_file = sys.argv[2]

    # Baca JSON dari file (menghindari masalah escaping di Windows CLI)
    if not os.path.exists(json_file):
        print(json.dumps({"status": "error", "message": f"File data tidak ditemukan: {json_file}"}))
        sys.exit(1)

    with open(json_file, 'r') as f:
        raw_data = json.load(f)

    try:
        model    = load_model(user_id)
        features = extract_features(raw_data)
        
        # Lakukan prediksi
        result = predict(features, model)
        
        # decision_function: nilai jarak ke batas keputusan SVM
        # Positif = inlier (makin besar makin yakin cocok)
        # Negatif = outlier (makin kecil makin yakin asing)
        decision_score = float(model.decision_function(features)[0])
        is_match = bool(result == 1)
        
        output = {
            "status": "success",
            "is_match": is_match,
            "decision_score": round(decision_score, 4)
        }
        print(json.dumps(output))

    except Exception as e:
        # Print dalam struktur JSON agar error mudah ditebak oleh pemanggil bahasa lain
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()