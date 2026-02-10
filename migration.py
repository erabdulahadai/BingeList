import sqlite3
import os

def migrate():
    # Check for DB files
    db_files = ['bingelist.db', 'database.db', 'instance/bingelist.db']
    target_db = None
    
    for db_file in db_files:
        if os.path.exists(db_file):
            target_db = db_file
            break
            
    if not target_db:
        print("No database found. Creating new one via app startup later.")
        return

    print(f"Migrating database: {target_db}")
    
    try:
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        
        # Check if email column exists in user table
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'email' not in columns:
            print("Adding email column to user table...")
            cursor.execute("ALTER TABLE user ADD COLUMN email VARCHAR(120) UNIQUE")
            conn.commit()
            print("Migration successful.")
        else:
            print("Email column already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
