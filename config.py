import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'futuristic_secret_123'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///bingelist.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY') or 'ee499b4c77b749e072962081091122c0'
