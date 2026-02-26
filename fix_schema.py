
from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    # Use text() to safely execute raw SQL
    try:
        print("Dropping search_history table to fix schema...")
        db.session.execute(text('DROP TABLE IF EXISTS search_history'))
        db.session.commit()
        print("Table dropped.")
        
        print("Creating all tables...")
        db.create_all()
        print("Tables created.")
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
