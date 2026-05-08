import os
import hashlib
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def _derive_secret_key() -> str:
    """
    Menghasilkan SECRET_KEY yang deterministik (tidak berubah saat restart).
    Prioritas: nilai dari .env -> fallback statis berbasis DB_NAME.
    Tanpa ini, Flask akan generate key acak setiap restart sehingga
    semua sesi user langsung invalid (ter-logout paksa).
    """
    key_from_env = os.getenv('SECRET_KEY', '').strip()
    if key_from_env:
        return key_from_env
    # Fallback: hash stabil dari nama database + salt tetap
    db_name = os.getenv('DB_NAME', 'keystroke_db')
    salt = "titanium-fusion-salt-2024"
    return hashlib.sha256(f"{db_name}:{salt}".encode()).hexdigest()

class Config:
    SECRET_KEY = _derive_secret_key()
    
    # Database Config
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASS = os.getenv('DB_PASS', '')
    DB_NAME = os.getenv('DB_NAME', 'keystroke_db')

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASS,
            database=Config.DB_NAME
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
