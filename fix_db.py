import os
import sqlite3
from config import Config

print("Starting database fix...")

# 1. Determine DB path
uri = Config.SQLALCHEMY_DATABASE_URI
db_path = "bingelist.db" # Default fallback
if uri and uri.startswith('sqlite:///'):
    db_path = uri.replace('sqlite:///', '')

target_path = None
possible_paths = [
    db_path,
    os.path.join('instance', db_path),
    os.path.abspath(db_path)
]

for p in possible_paths:
    if os.path.exists(p):
        target_path = p
        break

if not target_path:
    # If not found, create it in instance usually, but here we expect it to exist
    print(f"Database file not found in: {possible_paths}")
    if os.path.exists(os.path.join(os.getcwd(), 'instance', 'bingelist.db')):
        target_path = os.path.join(os.getcwd(), 'instance', 'bingelist.db')
    else:
        exit(1)

print(f"Found database at: {target_path}")

# 2. Apply Fix
try:
    conn = sqlite3.connect(target_path)
    cur = conn.cursor()
    
    # Check if columns exist in movie table
    cur.execute("PRAGMA table_info(movie)")
    columns_info = cur.fetchall()
    columns = [info[1] for info in columns_info]
    
    print(f"Current columns in 'movie' table: {columns}")

    # Fix tmdb_id
    if 'tmdb_id' in columns:
        print("Column 'tmdb_id' already exists.")
    else:
        print("Adding 'tmdb_id' column...")
        cur.execute("ALTER TABLE movie ADD COLUMN tmdb_id INTEGER")
        print("Success: Column 'tmdb_id' added.")

    # Fix list_id
    if 'list_id' in columns:
        print("Column 'list_id' already exists.")
    else:
        print("Adding 'list_id' column...")
        cur.execute("ALTER TABLE movie ADD COLUMN list_id INTEGER REFERENCES movie_list(id)")
        print("Success: Column 'list_id' added.")

    conn.commit()
    conn.close()
    print("Database fix completed.")

except Exception as e:
    print(f"Error applying fix: {e}")
