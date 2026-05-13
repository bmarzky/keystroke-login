from src.config.database import get_db_connection

def get_user_by_username(username):
    """Mengambil data user berdasarkan username."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        return user
    finally:
        conn.close()

def register_user_with_biometrics(username, hashed_password, keystroke_json):
    """Mendaftarkan user dan data biometrik awal dalam satu transaksi (Atomik)."""
    conn = get_db_connection()
    try:
        conn.start_transaction()
        cursor = conn.cursor()
        
        # 1. Create User
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        uid = cursor.lastrowid
        
        # 2. Add Biometric Data
        cursor.execute("INSERT INTO keystroke_data (user_id, features) VALUES (%s, %s)", (uid, keystroke_json))
        
        conn.commit()
        return uid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
