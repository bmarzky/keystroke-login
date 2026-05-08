from src.config.database import get_db_connection

def get_user_by_username(username):
    """Mengambil data user berdasarkan username."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        return user
    finally:
        conn.close()

def create_user(username, hashed_password):
    """Mendaftarkan user baru ke database."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        uid = cursor.lastrowid
        conn.commit()
        return uid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
