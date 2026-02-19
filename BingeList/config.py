import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'futuristic_secret_123'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///bingelist.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads/avatars'
    TMDB_API_KEY = "ee499b4c77b749e072962081091122c0" # Hardcoded for now per user request
