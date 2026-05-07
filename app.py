import os, json, time, subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
import numpy as np

# Load internal modules
from engine.core import BiometricCore
from config.database import Config, get_db_connection
from utils.logger import log_access, format_log

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

        conn = get_db_connection()
        if not conn:
            return render_template('auth/login.html', error="Database connection error")
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # 1. Fetch History
            cursor.execute("SELECT features FROM keystroke_data WHERE user_id = %s ORDER BY id ASC", (user['id'],))
            history_rows = cursor.fetchall()
            history = [row['features'] for row in history_rows]

            # 2. Replay Detection
            is_replay = False
            current_norm = json.dumps(input_keystroke, sort_keys=True)
            for h_str in history:
                if json.dumps(json.loads(h_str), sort_keys=True) == current_norm:
                    is_replay = True
                    break
            
            if is_replay:
                log_access('login_failed.log', f"REPLAY ATTACK | User: {username}", "Blocked replay attempt")
                return render_template('auth/login.html', error="Keamanan: Terdeteksi serangan Replay.")

            # 3. Biometric Verification
            history_dicts = [json.loads(h) for h in history]
            result = biom_core.analyze(input_keystroke, history_dicts, user['id'])

            if result['status']:
                # Login Success
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S')

                # Update History if required
                if result.get('should_update_history'):
                    cursor.execute("INSERT INTO keystroke_data (user_id, features) VALUES (%s, %s)", 
                                 (user['id'], json.dumps(input_keystroke)))
                    conn.commit()
                    
                    # Auto-Retrain Trigger (Updated every 20 samples)
                    n_samples = len(history) + 1
                    if n_samples >= 20 and (n_samples % 20 == 0 or not _model_exists(user['id'])):
                        _trigger_training(user['id'], history_dicts + [input_keystroke])

                log_access('login_success.log', f"SUCCESS | User: {username}", format_log(user['id'], result, history, input_keystroke))
                conn.close()
                return redirect(url_for('dashboard'))
            else:
                log_access('login_failed.log', f"FAILURE | User: {username}", format_log(user['id'], result, history, input_keystroke))
                conn.close()
                return render_template('auth/login.html', error=result['reason'])
        
        conn.close()
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

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            conn.close()
            return render_template('auth/register.html', error="Username sudah terdaftar")

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
            uid = cursor.lastrowid
            cursor.execute("INSERT INTO keystroke_data (user_id, features) VALUES (%s, %s)", (uid, keystroke_json))
            conn.commit()
            conn.close()
            return render_template('auth/login.html', success="Registrasi berhasil! Silakan login.")
        except Exception as e:
            conn.rollback()
            conn.close()
            return render_template('auth/register.html', error=f"Error: {str(e)}")

    return render_template('auth/register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    uid = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM keystroke_data WHERE user_id = %s", (uid,))
    total_data = cursor.fetchone()['total']
    
    cursor.execute("SELECT features FROM keystroke_data WHERE user_id = %s ORDER BY id DESC LIMIT 2", (uid,))
    rows = cursor.fetchall()
    
    all_features = [json.loads(r['features']) for r in rows]
    current = all_features[0] if len(all_features) > 0 else {'dwell': [], 'flight': []}
    prev = all_features[1] if len(all_features) > 1 else {'dwell': [], 'flight': []}
    
    # Stats calculation
    avg_dwell = 0
    avg_flight = 0
    wpm = 0
    stability = 0
    
    if current['dwell']:
        cnt_d = len(current['dwell'])
        sum_d = sum(current['dwell'])
        sum_f = sum(current.get('flight', []))
        avg_dwell = sum_d / cnt_d
        avg_flight = sum_f / len(current['flight']) if current.get('flight') else 0
        
        total_time = sum_d + sum_f
        if total_time > 0:
            wpm = (cnt_d / 5) / (total_time / 60)
        
        stability = np.std(current['dwell'])

    conn.close()
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

def _model_exists(uid):
    return os.path.exists(f"engine/ml/models/{uid}_ocsvm.joblib")

def _trigger_training(uid, history):
    scratch_dir = 'scratch/'
    if not os.path.exists(scratch_dir): os.makedirs(scratch_dir)
    train_file = os.path.join(scratch_dir, f"training_{uid}.json")
    with open(train_file, 'w') as f:
        json.dump({'history': history}, f)
    
    py_train = os.path.join('engine', 'ml', 'ai_trainer.py')
    import sys
    try:
        subprocess.Popen([sys.executable, py_train, str(uid), train_file])
    except Exception as e:
        # Jangan crash app utama jika training gagal — cukup log ke console
        print(f"[TRAINING ERROR] Gagal memulai proses training untuk user {uid}: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=8000)
