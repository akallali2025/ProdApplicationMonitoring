# db.py
"""
db.py
-----
Manages SQLite database initialization and connections.
"""

import sqlite3
import os

def init_db(db_path="my_datebase.db", script_path="create_tables.sql"):
    """
    Ensures that required database tables exist. Reads SQL from the given script
    and executes it within an SQLite connection to 'db_path'.
    - If tables already exist (due to IF NOT EXISTS in your SQL), no changes are made.
    - If they are missing, they get created.

    :param db_path: Path (relative or absolute) to your SQLite database file.
    :param script_path: Path to the SQL script file containing CREATE TABLE statements.
    """
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