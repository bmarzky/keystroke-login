import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import secrets

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(24))
    
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
