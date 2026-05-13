from src.config.database import get_db_connection

def get_history_by_user_id(user_id):
    """Mengambil semua riwayat fitur keystroke milik user."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT features FROM keystroke_data WHERE user_id = %s ORDER BY id ASC", (user_id,))
        rows = cursor.fetchall()
        return [row['features'] for row in rows]
    finally:
        conn.close()

def add_keystroke_data(user_id, keystroke_json):
    """Menambahkan data biometrik baru untuk user."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO keystroke_data (user_id, features) VALUES (%s, %s)", (user_id, keystroke_json))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_dashboard_data(user_id):
    """Mengambil total data dan 2 sampel terbaru untuk dashboard."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Count total
        cursor.execute("SELECT COUNT(*) as total FROM keystroke_data WHERE user_id = %s", (user_id,))
        total = cursor.fetchone()['total']
        
        # Get latest 2
        cursor.execute("SELECT features FROM keystroke_data WHERE user_id = %s ORDER BY id DESC LIMIT 2", (user_id,))
        rows = cursor.fetchall()
        
        return total, rows
    finally:
        conn.close()

