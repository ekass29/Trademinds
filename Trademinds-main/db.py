# MySQL connection setup
import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='your_username',
        password='your_password',
        database='stock_app'
    )
