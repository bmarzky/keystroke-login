from src.engine.ml.ai_engine import AIEngine
import os, json, time, subprocess, threading, secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
import numpy as np

# Load internal modules
from src.engine.core import BiometricCore
from src.config.database import Config, get_db_connection, DatabaseConnectionError
from src.utils.logger import log_access, format_log
from src.services.stats_service import calculate_dashboard_stats
from src.services.biometric_service import verify_biometric
from src.models import user_model, keystroke_model

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY or 'titanium-fusion-super-secret-key-123'

@app.errorhandler(DatabaseConnectionError)
def handle_db_error(e):
    return render_template('errors/503.html', message=str(e)), 503

# Biometric Engine Instance
biom_core = BiometricCore()

# Hosting Check: Pastikan folder models ada dan writable
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
if not os.path.exists(MODELS_DIR):
    try:
        os.makedirs(MODELS_DIR, exist_ok=True)
        with open(os.path.join(MODELS_DIR, 'test_write.txt'), 'w') as f:
            f.write('test')
        os.remove(os.path.join(MODELS_DIR, 'test_write.txt'))
    except Exception as e:
        print(f"[HOSTING WARNING] Folder models tidak writable: {e}")

# CSRF Protection Helper
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('_csrf_token')
        form_token = request.form.get('csrf_token')
        if not token or token != form_token:
            print(f"[CSRF] FAIL: session={token}, form={form_token}")
            return redirect(url_for('login', error="Sesi telah berakhir atau token CSRF tidak valid. Silakan login kembali."))

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

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
            history = keystroke_model.get_history_by_user_id(user['id'])
            result = verify_biometric(biom_core, user['id'], username, input_keystroke, history)

            if result['status']:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['last_login'] = time.strftime('%Y-%m-%d %H:%M:%S')

                if result.get('should_update_history'):
                    keystroke_model.add_keystroke_data(user['id'], json.dumps(input_keystroke))
                    
                    # Async Training Trigger
                    n_samples = len(history) + 1
                    should_train = (n_samples >= 20 and (n_samples % 20 == 0 or result.get('score', 0) > 0.99)) or not _model_exists(user['id'])
                    
                    if should_train and n_samples >= 15:
                        history_dicts = [json.loads(h) for h in history]
                        threading.Thread(target=train_user_model_in_memory, 
                                       args=(user['id'], history_dicts + [input_keystroke])).start()

                current_time = time.strftime('%Y-%m-%d %H:%M:%S')
                log_access('login_success.log', f"{current_time} | SUCCESS | User: {username}", format_log(user['id'], result, history, input_keystroke))
                return redirect(url_for('dashboard'))
            else:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S')
                log_access('login_failed.log', f"{current_time} | FAILURE | User: {username}", format_log(user['id'], result, history, input_keystroke))
                return render_template('auth/login.html', error=result['reason'])
        
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        log_access('login_failed.log', f"{current_time} | FAILURE | User: {username}", f"  Reason: Password Salah atau User Tidak Ditemukan")
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
            # Atomic Transaction
            uid = user_model.register_user_with_biometrics(username, hashed, keystroke_json)
            if uid:
                return render_template('auth/login.html', success="Registrasi berhasil! Silakan login.")
            else:
                raise Exception("Gagal menyimpan data ke database")
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
    
    # Stats calculation using Service
    stats = calculate_dashboard_stats(current, all_features)
    
    # 2. Get Recent Security Activity (Parsing Logs)
    # Note: In production, this should ideally be in a DB table for efficiency.
    recent_activity = []
    try:
        username = session['username']
        log_files = [
            ('SUCCESS', os.path.join('logs', 'login_success.log')),
            ('FAILED', os.path.join('logs', 'login_failed.log'))
        ]
        
        for status, path in log_files:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read()
                    blocks = content.split("-" * 60)
                    for block in blocks:
                        if not block.strip(): continue
                        if f"User: {username}" in block:
                            lines = block.strip().split('\n')
                            header_line = lines[0]
                            parts = header_line.split(' | ')
                            
                            # Extract All Metrics from block
                            metrics = {
                                'ai_score': 'N/A',
                                'stability': 'N/A',
                                'rhythm': 'N/A',
                                'corr': 'N/A',
                                'speed': 'N/A',
                                'flow': 'N/A',
                                'ratio': 'N/A',
                                'method': 'N/A',
                                'history_count': 'N/A'
                            }
                            for l in lines:
                                if "AI Score      :" in l: metrics['ai_score'] = l.split(":")[1].strip()
                                if "Stability     :" in l: metrics['stability'] = l.split(":")[1].strip().replace('%', '')
                                if "Rhythm        :" in l: metrics['rhythm'] = l.split(":")[1].split('[')[0].strip()
                                if "Corr.         :" in l: metrics['corr'] = l.split(":")[1].split('[')[0].strip()
                                if "Speed         :" in l: metrics['speed'] = l.split(":")[1].split('[')[0].strip()
                                if "Flow          :" in l: metrics['flow'] = l.split(":")[1].split('[')[0].strip()
                                if "Ratio         :" in l: metrics['ratio'] = l.split(":")[1].strip()
                                if "Method        :" in l: metrics['method'] = l.split(":")[1].strip()
                                if "History Count :" in l: metrics['history_count'] = l.split(":")[1].strip()
                            
                            if len(parts) >= 3:
                                time_str = parts[0]
                                status_str = parts[1]
                            elif len(parts) >= 2:
                                time_str = "Legacy Event"
                                status_str = parts[0]
                            else:
                                time_str = "Recent Event"
                                status_str = status
                                
                            recent_activity.append({
                                'time': time_str,
                                'status': status_str,
                                **metrics
                            })
        
        # Sort by time desc
        recent_activity.sort(key=lambda x: x['time'] if x['time'] != 'Legacy Event' else '0000-00-00', reverse=True)
        recent_activity = recent_activity[:5]

        # Get latest metrics for health profile
        latest_metrics = {}
        if recent_activity:
            latest_metrics = recent_activity[0]

        # Aliases for template compatibility
        latest_ai = latest_metrics.get('ai_score', 'N/A')
        latest_stability = latest_metrics.get('stability', 'N/A')

    except Exception as e:
        print(f"Log Parse Error: {e}")

    # 3. Model Metadata for Transparency
    ai = AIEngine()
    model_path = ai._get_latest_model_path(uid)
    model_status = {
        "exists": False,
        "n_train": 0,
        "version": 0,
        "is_synced": False
    }
    
    if model_path:
        try:
            import joblib
            m_data = joblib.load(model_path)
            model_status["exists"] = True
            model_status["n_train"] = m_data.get('n_train', 0)
            model_status["version"] = m_data.get('version', 1)
            # Anggap sinkron jika selisih data < 5 (karena training biasanya per 20 data atau skor tinggi)
            model_status["is_synced"] = (total_data - model_status["n_train"]) < 5
        except: pass

    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)

    return render_template('dashboard/index.html', 
                         username=session['username'],
                         total_data=total_data,
                         avg_dwell=round(stats['avg_dwell'] * 1000),
                         avg_flight=round(stats['avg_flight'] * 1000),
                         wpm=round(stats['wpm'], 1),
                         stability=round(stats['stability'] * 1000, 1),
                         health_ai=latest_ai,
                         health_stability=latest_stability,
                         latest_metrics=latest_metrics,
                         last_login=session.get('last_login', 'N/A'),
                         recent_activity=recent_activity,
                         session_id=session['session_id'],
                         model_status=model_status,
                         current_date=time.strftime('%B %Y'))

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

from src.engine.ml.ai_trainer import train_user_model_in_memory

def _model_exists(uid):
    ai = AIEngine()
    return ai._get_latest_model_path(uid) is not None

if __name__ == '__main__':
    app.run(debug=True, port=8000)

