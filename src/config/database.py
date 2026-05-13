import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

from mysql.connector import pooling

class Config:
    # SECRET_KEY WAJIB dimuat dari environment variable untuk keamanan.
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        print("[CRITICAL] SECRET_KEY is not set in environment variables!")

    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASS = os.getenv('DB_PASS', '')
    DB_NAME = os.getenv('DB_NAME', 'keystroke_db')

# Inisialisasi Pool
db_pool = None
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=10,
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASS,
        database=Config.DB_NAME
    )
except Error as e:
    print(f"Error creating pool: {e}")

from mysql.connector.errors import PoolError

class DatabaseConnectionError(Exception):
    """Custom exception untuk kegagalan koneksi database."""
    pass

def get_db_connection():
    try:
        if db_pool:
            return db_pool.get_connection()
        # Fallback jika pool gagal inisialisasi
        return mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASS,
            database=Config.DB_NAME
        )
    except PoolError as e:
        print(f"CRITICAL: Database connection pool exhausted: {e}")
        raise DatabaseConnectionError("Database sedang sibuk, silakan coba beberapa saat lagi.")
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise DatabaseConnectionError("Koneksi database gagal.")
