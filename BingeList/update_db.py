from app import app
from extensions import db
from models import APICache

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables updated successfully.")
