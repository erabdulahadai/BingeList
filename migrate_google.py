import sqlite3
import os

db_path = 'instance/bingelist.db'
if os.path.exists(db_path):
    print(f"Migrating {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'google_id' not in columns:
            print("Adding google_id column...")
            cursor.execute("ALTER TABLE user ADD COLUMN google_id VARCHAR(100)")
            conn.commit()
            print("Creating unique index...")
            cursor.execute("CREATE UNIQUE INDEX idx_user_google_id ON user(google_id)")
            conn.commit()
            print("Successfully added google_id column and index.")
        else:
            print("google_id column already exists.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{db_path} not found.")
