import sys
import os
import json
import pandas as pd
import numpy as np
import mysql.connector
import joblib

# Konfigurasi Direktori
MODEL_DIR = os.path.join(os.path.dirname(__file__), '../model')

def get_db_connection():
    env_path = os.path.join(os.path.dirname(__file__), '../../.env')
    config = {'DB_HOST': 'localhost', 'DB_USER': 'root', 'DB_PASS': '', 'DB_NAME': 'keystroke_db'}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key] = value
    return mysql.connector.connect(
        host=config['DB_HOST'], user=config['DB_USER'],
        password=config['DB_PASS'], database=config['DB_NAME']
    )

def inspect_user_models():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Ambil semua user
    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    
    results = []
    
    for user in users:
        user_id = user['id']
        username = user['username']
        model_path = os.path.join(MODEL_DIR, f'keystroke_model_{user_id}.pkl')
        
        user_info = {
            "user_id": user_id,
            "username": username,
            "has_model": os.path.exists(model_path),
            "samples": []
        }
        
        if user_info["has_model"]:
            model = joblib.load(model_path)
            cursor.execute("SELECT id, features, created_at FROM keystroke_data WHERE user_id = %s", (user_id,))
            samples = cursor.fetchall()
            
            for s in samples:
                try:
                    data = json.loads(s['features'])
                    # Flatten fitur
                    vector = data['dwell'] + data['flight'] + data['d2d'] + data['u2u'] + [float(data['speed'])]
                    features = np.array(vector).reshape(1, -1)
                    
                    prediction = int(model.predict(features)[0])
                    score = float(model.decision_function(features)[0])
                    
                    user_info["samples"].append({
                        "sample_id": s['id'],
                        "prediction": "MATCH (1)" if prediction == 1 else "REJECT (-1)",
                        "decision_score": round(score, 6),
                        "created_at": str(s['created_at'])
                    })
                except Exception as e:
                    user_info["samples"].append({"sample_id": s['id'], "error": str(e)})
                    
        results.append(user_info)
        
    conn.close()
    return results

if __name__ == "__main__":
    analysis = inspect_user_models()
    print(json.dumps(analysis, indent=2))
