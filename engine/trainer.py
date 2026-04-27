"""
Skrip untuk proses training Machine Learning pada data biometrik keystroke.
Akan digunakan untuk mengonversi raw sensor log menjadi baseline yang presisi.
"""

import sys
import os
import json
import pandas as pd
import numpy as np
import mysql.connector
from sklearn.svm import OneClassSVM
import joblib
from datetime import datetime

# Import fitur 8-dimensi dari core
from core import extract_features

# Logging Setup
LOG_FILE = os.path.join(os.path.dirname(__file__), '../ml/logs/train.log')

def log_message(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")  # Also print to console

# Konfigurasi Direktori & Parameter
MODEL_DIR = os.path.join(os.path.dirname(__file__), '../ml/models')
os.makedirs(MODEL_DIR, exist_ok=True)
MIN_DATA_THRESHOLD = 15 # Butuh minimal 15 sesi ketikan untuk melatih pola SVM yang stabil


def get_db_connection():
    env_path = os.path.join(os.path.dirname(__file__), '../.env')
    config = {'DB_HOST': 'localhost', 'DB_USER': 'root', 'DB_PASS': '', 'DB_NAME': 'keystroke_db'}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key] = value
                    
    try:
        return mysql.connector.connect(
            host=config['DB_HOST'], user=config['DB_USER'],
            password=config['DB_PASS'], database=config['DB_NAME']
        )
    except Exception as err:
        print(f"Error Database: {err}", file=sys.stderr)
        sys.exit(1)

def load_data(user_id):
    """
    Load data keystroke langsung dari database MySQL berdasarkan user_id.
    """
    print(f"Menghubungkan ke database untuk menarik data user_id: {user_id}...")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT features FROM keystroke_data WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    # Mengecek jumlah rekaman ketikan
    if len(rows) < MIN_DATA_THRESHOLD:
        print(json.dumps({
            "status": "insufficient_data", 
            "count": len(rows), 
            "message": f"Data belum mencapai batas minimum ({MIN_DATA_THRESHOLD}). Gunakan Mahalanobis."
        }))
        sys.exit(0)
        
    from collections import Counter

    vectors = []
    for row in rows:
        try:
            data = json.loads(row['features'])
            # Gunakan ekstraksi 8-dim stat fitur (sama persis dengan mahalanobis)
            vec_8dim = extract_features(data)
            vectors.append(vec_8dim)
        except Exception:
            continue

    if len(vectors) == 0:
        print(json.dumps({"status": "error", "message": "Tidak ada fitur valid yang berhasil diparsing."}))
        sys.exit(1)

    # Karena selalu 8 dimensi, kita tidak butuh lagi hard-filter 'dominant_length'
    # SVM akan bisa mentraining walau ada data yang aslinya beda panjang saat diketik
    
    if len(vectors) < MIN_DATA_THRESHOLD:
        print(json.dumps({"status": "insufficient_data", "count": len(vectors), "message": f"Hanya {len(vectors)} sampel valid, butuh minimal {MIN_DATA_THRESHOLD}. Gunakan Mahalanobis."}))
        sys.exit(0)

    print(f"Data siap: {len(vectors)} sampel valid dengan 8 fitur statistik.", file=sys.stderr)
    return pd.DataFrame(vectors)

def train_model(X):
    """
    Melatih model Anomaly Detection menggunakan One-Class SVM.
    One-Class SVM cocok untuk mempelajari perilaku "normal" dari seorang pengguna.
    """
    print("Training model OneClassSVM...")
    model = OneClassSVM(gamma='scale', nu=0.2)
    model.fit(X)
    return model

def save_model(model, user_id):
    """
    Menyimpan pre-trained model untuk digunakan saat prediksi (login).
    Tiap user memiliki filenya masing-masing berdasarkan user_id.
    """
    filename = f"keystroke_model_{user_id}.pkl"
    filepath = os.path.join(MODEL_DIR, filename)
    joblib.dump(model, filepath)
    msg = f"Model berhasil disimpan di: {filepath}"
    print(msg)
    log_message(msg)

def main():
    if len(sys.argv) < 2:
        print("Error: Argumen user_id harus disertakan. Contoh: python train.py user_123", file=sys.stderr)
        sys.exit(1)
        
    user_id = sys.argv[1]
    log_message(f"START training untuk user_id: {user_id}")
    print(f"Memproses training... (Output akan langsung berupa JSON saat selesai/error)", file=sys.stderr)
    try:
        # 1. Load Data
        X = load_data(user_id)
        
        # 2. Train Model
        model = train_model(X)
        
        # 3. Export Model
        save_model(model, user_id)
        
        # Response ke PHP
        res = {"status": "success", "message": f"Model OneClassSVM siap untuk user {user_id}"}
        log_message(f"SUCCESS: {res['message']}")
        print(json.dumps(res))

    except Exception as e:
        err_msg = f"ERROR: {str(e)}"
        log_message(err_msg)
        print(err_msg, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()