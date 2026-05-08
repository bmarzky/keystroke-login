import os, json, time, subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
import numpy as np

# Load internal modules
from src.engine.core import BiometricCore
from src.config.database import Config, get_db_connection
from src.utils.logger import log_access, format_log
from src.services.stats_service import calculate_dashboard_stats
from src.services.biometric_service import verify_biometric
from src.models import user_model, keystroke_model

app = Flask(__name__)
app.config.from_object(Config)

# Biometric Engine Instance
biom_core = BiometricCore()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        keystroke_json = request.form.get('keystroke', '').strip()

        if not username or not password or not keystroke_json:
            return render_template('auth/login.html', error="Form tidak lengkap")

        try:
            input_keystroke = json.loads(keystroke_json)
        except json.JSONDecodeError:
            return render_template('auth/login.html', error="Data biometrik tidak valid")

        user = user_model.get_user_by_username(username)

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # 1. Fetch History
            history = keystroke_model.get_history_by_user_id(user['id'])

            # 2. Biometric Verification (Includes Replay Check)
            result = verify_biometric(biom_core, user['id'], username, input_keystroke, history)

            if result['status']:
                # Login Success
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S')

                # Update History if required
                if result.get('should_update_history'):
                    keystroke_model.add_keystroke_data(user['id'], json.dumps(input_keystroke))
                    
                    # Auto-Retrain Trigger (Updated every 20 samples)
                    n_samples = len(history) + 1
                    if n_samples >= 20 and (n_samples % 20 == 0 or not _model_exists(user['id'])):
                        history_dicts = [json.loads(h) for h in history]
                        _trigger_training(user['id'], history_dicts + [input_keystroke])

                log_access('login_success.log', f"SUCCESS | User: {username}", format_log(user['id'], result, history, input_keystroke))
                return redirect(url_for('dashboard'))
            else:
                log_access('login_failed.log', f"FAILURE | User: {username}", format_log(user['id'], result, history, input_keystroke))
                return render_template('auth/login.html', error=result['reason'])
        
        return render_template('auth/login.html', error="Username atau password salah")

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        keystroke_json = request.form.get('keystroke', '').strip()

        if not username or not password or not keystroke_json:
            return render_template('auth/register.html', error="Data tidak lengkap")

        try:
            decoded = json.loads(keystroke_json)
            if len(decoded.get('dwell', [])) < 7:
                 return render_template('auth/register.html', error="Password terlalu pendek (Min. 7 char)")
        except:
            return render_template('auth/register.html', error="Data biometrik tidak valid")

        user = user_model.get_user_by_username(username)
        if user:
            return render_template('auth/register.html', error="Username sudah terdaftar")

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        try:
            uid = user_model.create_user(username, hashed)
            keystroke_model.add_keystroke_data(uid, keystroke_json)
            return render_template('auth/login.html', success="Registrasi berhasil! Silakan login.")
        except Exception as e:
            return render_template('auth/register.html', error=f"Error: {str(e)}")

    return render_template('auth/register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    uid = session['user_id']
    total_data, rows = keystroke_model.get_dashboard_data(uid)
    
    all_features = [json.loads(r['features']) for r in rows]
    current = all_features[0] if len(all_features) > 0 else {'dwell': [], 'flight': []}
    prev = all_features[1] if len(all_features) > 1 else {'dwell': [], 'flight': []}
    
    # Stats calculation using Service
    stats = calculate_dashboard_stats(current)
    
    avg_dwell = stats['avg_dwell']
    avg_flight = stats['avg_flight']
    wpm = stats['wpm']
    stability = stats['stability']

    return render_template('dashboard/index.html', 
                         username=session['username'],
                         total_data=total_data,
                         avg_dwell=round(avg_dwell * 1000),
                         avg_flight=round(avg_flight * 1000),
                         wpm=round(wpm, 1),
                         stability=round(stability * 1000, 1),
                         last_login=session.get('last_login', 'N/A'),
                         current_features=current,
                         prev_features=prev)

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

import glob

def _model_exists(uid):
    pattern = os.path.join("src", "engine", "ml", "models", f"{uid}_ocsvm_v*.joblib")
    return len(glob.glob(pattern)) > 0

def _trigger_training(uid, history):
    scratch_dir = 'scratch/'
    if not os.path.exists(scratch_dir): os.makedirs(scratch_dir)
    train_file = os.path.join(scratch_dir, f"training_{uid}.json")
    with open(train_file, 'w') as f:
        json.dump({'history': history}, f)
    
    py_train = os.path.join('src', 'engine', 'ml', 'ai_trainer.py')
    import sys
    try:
        subprocess.Popen([sys.executable, py_train, str(uid), train_file])
    except Exception as e:
        # Jangan crash app utama jika training gagal — cukup log ke console
        print(f"[TRAINING ERROR] Gagal memulai proses training untuk user {uid}: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=8000)
