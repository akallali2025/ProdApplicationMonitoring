
"""
db.py
"""

import sqlite3
import os

def init_db(db_path="my_datebase.db", script_path="create_tables.sql"):

    #check if db exists -> test
    if os.path.exists(db_path):
        return 

    # Ensure the SQL file exists
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"SQL script not found: {script_path}")
    
    print("SQL File existist")

    # Connect to the SQLite database (creates file if it doesn't exist)
    conn = sqlite3.connect(db_path)

    # Read the SQL script from file
    with open(script_path, "r", encoding="utf-8") as sql_file:
        sql_script = sql_file.read()

    # Execute the script
    conn.executescript(sql_script)
    conn.close()

    print(f"Database initialized using {script_path}. Tables are ready (if not already).")