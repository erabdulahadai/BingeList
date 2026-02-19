from app import app
from extensions import db
from sqlalchemy import text

def update_schema():
    with app.app_context():
        try:
            # Check if column exists first to avoid error
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE user ADD COLUMN avatar VARCHAR(500)"))
                    print("Successfully added 'avatar' column to 'user' table.")
                except Exception as e:
                    if "duplicate column name" in str(e):
                        print("Column 'avatar' already exists.")
                    else:
                        print(f"Error adding column: {e}")
        except Exception as e:
            print(f"Database connection error: {e}")

if __name__ == "__main__":
    update_schema()
