from src.engine.ml.ai_engine import AIEngine
import os, json, time, subprocess, threading, secrets
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
app.secret_key = Config.SECRET_KEY or 'sequential-mahalanobis-svm-secure-key-123'


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
                    # Simpan data ke DB dan periksa hasilnya.
                    # Training HANYA boleh dijalankan jika data berhasil tersimpan —
                    # mencegah model di-train dengan sampel yang tidak ada di DB (race condition).
                    saved = keystroke_model.add_keystroke_data(user['id'], json.dumps(input_keystroke))

                    if not saved:
                        log_access('ai_training.log',
                                   f"{time.strftime('%Y-%m-%d %H:%M:%S')} | DB_SAVE_FAIL | User: {username}",
                                   "  add_keystroke_data() mengembalikan False — training dibatalkan.")
                    else:
                        # Async Training Trigger untuk riset Cold-Start:
                        #   - Periodic: setiap 10 sampel baru (mulai dari 15)
                        #   - High-score: langsung train jika skor sangat tinggi (> 0.99)
                        #   - Bootstrap: train sekali jika model belum ada sama sekali (min. 15 sampel)
                        # Catatan: minimum 15 sampel diperlukan agar SVM bisa diinisialisasi.
                        # n_samples dihitung SETELAH insert sukses agar hitungan akurat.
                        n_samples = len(history) + 1
                        has_enough_data = n_samples >= 15
                        is_periodic     = has_enough_data and (n_samples % 10 == 0)
                        is_high_score   = has_enough_data and result.get('score', 0) > 0.99
                        is_bootstrap    = has_enough_data and not _model_exists(user['id'])
                        should_train    = is_periodic or is_high_score or is_bootstrap

                        if should_train:
                            try:
                                # Guard: handle both raw JSON strings and pre-parsed dicts
                                history_dicts = [json.loads(h) if isinstance(h, str) else h for h in history]
                                # Spawn daemon thread — async_train_user_model menangani exception & logging
                                t = threading.Thread(target=async_train_user_model,
                                                     args=(user['id'], history_dicts + [input_keystroke]),
                                                     daemon=True)
                                t.start()
                            except Exception as e:
                                # Log kegagalan spawn thread agar admin bisa investigasi
                                log_access('ai_training.log', f"{time.strftime('%Y-%m-%d %H:%M:%S')} | TRAIN_THREAD_FAIL | User: {username}", str(e))

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

    # Jika ada pesan error/success lewat query params (mis. CSRF redirect), teruskan ke template
    return render_template('auth/login.html', error=request.args.get('error'), success=request.args.get('success'))

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
        except (json.JSONDecodeError, ValueError):
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
    latest_metrics = {}
    latest_ai = 'N/A'
    latest_stability = 'N/A'
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
                        if f"User ID       : {uid}" in block:
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
                                try:
                                    if "AI Score      :" in l: metrics['ai_score'] = l.split(":", 1)[1].strip()
                                    if "Stability     :" in l: metrics['stability'] = l.split(":", 1)[1].strip().replace('%', '')
                                    if "Rhythm        :" in l: metrics['rhythm'] = l.split(":", 1)[1].split('[')[0].strip()
                                    if "Corr.         :" in l: metrics['corr'] = l.split(":", 1)[1].split('[')[0].strip()
                                    if "Speed         :" in l: metrics['speed'] = l.split(":", 1)[1].split('[')[0].strip()
                                    if "Flow          :" in l: metrics['flow'] = l.split(":", 1)[1].split('[')[0].strip()
                                    if "Ratio         :" in l: metrics['ratio'] = l.split(":", 1)[1].strip()
                                    if "Method        :" in l: metrics['method'] = l.split(":", 1)[1].strip()
                                    if "History Count :" in l: metrics['history_count'] = l.split(":", 1)[1].strip()
                                except Exception:
                                    # Safely ignore malformed metric lines
                                    continue
                            
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

        # Get latest metrics for health profile (if any)
        if recent_activity:
            latest_metrics = recent_activity[0]
            # Aliases for template compatibility
            latest_ai = latest_metrics.get('ai_score', 'N/A')
            latest_stability = latest_metrics.get('stability', 'N/A')

    except Exception as e:
        print(f"Log Parse Error: {e}")

    # 2.5 Count Biometric Anomalies (REJECT) for this user
    total_failures = 0
    try:
        fail_log_path = os.path.join('logs', 'login_failed.log')
        if os.path.exists(fail_log_path):
            with open(fail_log_path, 'r') as f:
                content = f.read()
                blocks = content.split("-" * 60)
                u_lower = session['username'].lower()
                for block in blocks:
                    if not block.strip(): continue
                    b_lower = block.lower()
                    # Hitung sebagai anomali jika User ID cocok DAN bukan karena "Password Salah"
                    if f"user id       : {uid}" in b_lower and "password salah" not in b_lower:
                        total_failures += 1
    except Exception as e:
        print(f"Fail Count Error: {e}")

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
        except Exception as model_load_err:
            # Log eksplisit agar admin tahu jika file model korup atau tidak bisa diakses.
            # Jangan biarkan error ini ditelan diam-diam — dashboard tetap tampil tapi model_status
            # akan menunjukkan exists=False sebagai sinyal bahwa model perlu diregenerasi.
            import logging
            logging.getLogger(__name__).warning(
                "Dashboard: gagal memuat model '%s' — %s", model_path, model_load_err
            )

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
                         total_failures=total_failures,
                         session_id=session['session_id'],
                         model_status=model_status,
                         current_date=time.strftime('%B %Y'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

from src.engine.ml.ai_trainer import train_user_model_in_memory

def _model_exists(uid):
    ai = AIEngine()
    return ai._get_latest_model_path(uid) is not None


def async_train_user_model(user_id, history):
    """Wrapper to run model training in a background thread with logging and basic health recording.

    This wrapper ensures any exceptions are logged and the training result is recorded
    to `logs/ai_training.log`. It uses the existing `train_user_model_in_memory` function
    which returns (success: bool, message: str).
    """
    try:
        success, msg = train_user_model_in_memory(user_id, history)
        header = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | TRAIN | User: {user_id} | Success: {success}"
        log_access('ai_training.log', header, msg)

        # If training failed, record a small health file for operator inspection
        if not success:
            try:
                os.makedirs(MODELS_DIR, exist_ok=True)
                with open(os.path.join(MODELS_DIR, f"{user_id}_training_fail.log"), 'a', encoding='utf-8') as fh:
                    fh.write(header + "\n" + msg + "\n")
            except Exception as e:
                log_access('ai_training.log', f"{time.strftime('%Y-%m-%d %H:%M:%S')} | TRAIN_LOG_FAIL | User: {user_id}", str(e))
    except Exception as e:
        log_access('ai_training.log', f"{time.strftime('%Y-%m-%d %H:%M:%S')} | TRAIN_EXCEPTION | User: {user_id}", str(e))

if __name__ == '__main__':
    app.run(debug=True, port=8000)

