import sys
import os
import json
import numpy as np
import mysql.connector
import joblib
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# konfigurasi
MODEL_DIR = os.path.join(os.path.dirname(__file__), '../model')


# DB Connetion
def get_db_connection():
    env_path = os.path.join(os.path.dirname(__file__), '../../.env')
    config = {
        'DB_HOST': 'localhost',
        'DB_USER': 'root',
        'DB_PASS': '',
        'DB_NAME': 'keystroke_db'
    }

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key] = value

    return mysql.connector.connect(
        host=config['DB_HOST'],
        user=config['DB_USER'],
        password=config['DB_PASS'],
        database=config['DB_NAME']
    )


# visualisasi
def plot_pca_boundary(user_data, model):
    if not user_data["features_list"]:
        print(f"Tidak ada data fitur untuk user {user_data['username']}")
        return

    X = np.array(user_data["features_list"])
    if len(X) < 3:
        print(f"Data terlalu sedikit untuk PCA (min 3 sample). User: {user_data['username']}")
        return

    # 1. PCA (Tanpa Scaling agar sesuai dengan data asli model)
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X)

    # 2. Buat Meshgrid untuk Boundary
    # Gunakan margin yang lebih kecil agar fokus pada cluster data
    x_min, x_max = X_pca[:, 0].min() - 0.5, X_pca[:, 0].max() + 0.5
    y_min, y_max = X_pca[:, 1].min() - 0.5, X_pca[:, 1].max() + 0.5
    
    # Tingkatkan densitas grid
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 150),
                         np.linspace(y_min, y_max, 150))

    # 3. Map Meshgrid balik ke 31D
    grid_points_pca = np.c_[xx.ravel(), yy.ravel()]
    grid_points_raw = pca.inverse_transform(grid_points_pca)
    
    # Predict menggunakan model asli
    Z = model.predict(grid_points_raw)
    Z = Z.reshape(xx.shape)

    # 4. Plotting
    plt.figure(figsize=(10, 7))
    
    # Boundary: Dua-Warna (Hijau untuk Match, Merah untuk Reject)
    from matplotlib.colors import ListedColormap
    cm = ListedColormap(['#FFCCCC', '#CCFFCC']) # Merah muda (Reject), Hijau muda (Match)
    
    plt.contourf(xx, yy, Z, cmap=cm, alpha=0.8)
    
    # Plot Titik Data User
    plt.scatter(X_pca[:, 0], X_pca[:, 1], c='black', edgecolors='k', label='User Samples')

    plt.title(f"2D PCA Decision Boundary - User: {user_data['username']}")
    plt.xlabel("Principal Component 1")
    plt.ylabel("Principal Component 2")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    print(f"Menampilkan grafik 2D PCA untuk {user_data['username']}... (Tutup jendela untuk lanjut)")
    plt.show()


# visualisasi skor
def plot_user_scores(user_data):
    if not user_data["samples"]:
        return

    sample_ids = []
    scores = []

    for s in user_data["samples"]:
        if "decision_score" in s:
            sample_ids.append(s["sample_id"])
            scores.append(s["decision_score"])

    if not scores:
        return

    # pisahkan MATCH dan REJECT
    match_x, match_y = [], []
    reject_x, reject_y = [], []

    for i in range(len(sample_ids)):
        if scores[i] >= 0:
            match_x.append(sample_ids[i])
            match_y.append(scores[i])
        else:
            reject_x.append(sample_ids[i])
            reject_y.append(scores[i])

    plt.figure(figsize=(10, 4))
    plt.scatter(match_x, match_y, color='green', label="MATCH")
    plt.scatter(reject_x, reject_y, color='red', label="REJECT")
    plt.axhline(y=0, color='black', linestyle='--')

    plt.title(f"Score History - User: {user_data['username']}")
    plt.xlabel("Sample ID")
    plt.ylabel("Decision Score")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()


# analisis model
def inspect_user_models(target_user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if target_user_id:
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (target_user_id,))
    else:
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
            "samples": [],
            "features_list": []
        }

        if user_info["has_model"]:
            model = joblib.load(model_path)

            cursor.execute(
                "SELECT id, features, created_at FROM keystroke_data WHERE user_id = %s ORDER BY id ASC",
                (user_id,)
            )
            samples = cursor.fetchall()

            for s in samples:
                try:
                    data = json.loads(s['features'])
                    vector = (
                        data['dwell'] +
                        data['flight'] +
                        data['d2d'] +
                        data['u2u'] +
                        [float(data.get('speed', 0))]
                    )

                    features = np.array(vector).reshape(1, -1)
                    user_info["features_list"].append(vector)

                    prediction = int(model.predict(features)[0])
                    score = float(model.decision_function(features)[0])

                    user_info["samples"].append({
                        "sample_id": s['id'],
                        "prediction": "MATCH (1)" if prediction == 1 else "REJECT (-1)",
                        "decision_score": round(score, 6),
                        "created_at": str(s['created_at'])
                    })

                except Exception as e:
                    user_info["samples"].append({
                        "sample_id": s['id'],
                        "error": str(e)
                    })
            
            user_info["model_object"] = model

        results.append(user_info)

    conn.close()
    return results


# main
if __name__ == "__main__":
    print("=== Keystroke Model Inspector (2D PCA Edition) ===")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username FROM users")
    all_users = cursor.fetchall()
    conn.close()

    print("\nDaftar User yang tersedia:")
    for u in all_users:
        print(f"[{u['id']}] {u['username']}")
    
    try:
        choice = input("\nMasukkan User ID yang ingin diperiksa (atau 'all'): ").strip()
        
        if choice.lower() == 'all':
            analysis = inspect_user_models()
        else:
            analysis = inspect_user_models(target_user_id=int(choice))
            
        for user in analysis:
            print(f"\n--- Analisis User: {user['username']} (ID: {user['user_id']}) ---")
            if not user["has_model"]:
                print("Model tidak ditemukan (.pkl missing)")
                continue
            
            print(f"Ditemukan {len(user['samples'])} sampel data.")
            
            # Tampilkan Grafik Skor
            plot_user_scores(user)
            
            # Tampilkan Grafik PCA Boundary
            plot_pca_boundary(user, user["model_object"])
            
    except ValueError:
        print("Error: Masukkan ID berupa angka atau 'all'.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")