
import requests
import json
import os
from app import app
from extensions import db
from models import APICache

# Function to inject dummy data into cache if API fails
def inject_dummy_data(url, category_name):
    print(f"Injecting dummy data for {category_name}...")
    
    # Pre-defined dummy movies
    dummy_movies = [
        {"id": 1, "title": "The Simulation", "poster_path": None, "overview": "A glitch in the matrix."},
        {"id": 2, "title": "Code Worriers", "poster_path": None, "overview": "Developers fighting bugs."},
        {"id": 3, "title": "Infinite Loop", "poster_path": None, "overview": "It never ends."},
        {"id": 4, "title": "Null Pointer", "poster_path": None, "overview": "Something is missing."},
        {"id": 5, "title": "The Algorithm", "poster_path": None, "overview": "It knows everything."}
    ]
    
    # Adjust titles based on category
    for i, m in enumerate(dummy_movies):
        m['title'] = f"{m['title']} ({category_name})"
        
    dummy_response = {
        "results": dummy_movies
    }
    
    # Store in DB
    try:
        # Check if exists
        existing = APICache.query.filter_by(url=url).first()
        if not existing:
            new_cache = APICache(url=url, response_json=json.dumps(dummy_response))
            db.session.add(new_cache)
            db.session.commit()
            print(f"Inserted dummy data for {category_name}")
        else:
            print(f"Data already exists for {category_name}")
            
    except Exception as e:
        print(f"Error injecting data: {e}")
        db.session.rollback()

def populate():
    with app.app_context():
        api_key = app.config['TMDB_API_KEY']
        
        # 1. Popular URL
        popular_url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=en-US&page=1"
        
        # 2. Horror URL
        horror_url = f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}&with_genres=27&sort_by=popularity.desc&page=1"
        
        # Try fetching real data first
        print("Attempting to fetch fresh data from TMDB...")
        session = requests.Session()
        
        # POPULAR
        try:
            resp = session.get(popular_url, timeout=5)
            if resp.status_code == 200:
                print("Successfully fetched Popular movies.")
                # Logic in fetch_tmdb_data handles saving if we use app logic, 
                # but let's manually save here to be sure.
                existing = APICache.query.filter_by(url=popular_url).first()
                if not existing:
                    new_cache = APICache(url=popular_url, response_json=json.dumps(resp.json()))
                    db.session.add(new_cache)
                    db.session.commit()
            else:
                raise Exception("Non-200 status")
        except Exception as e:
            print(f"Failed to fetch Popular movies: {e}")
            inject_dummy_data(popular_url, "Popular")

        # HORROR
        try:
            resp = session.get(horror_url, timeout=5)
            if resp.status_code == 200:
                print("Successfully fetched Horror movies.")
                existing = APICache.query.filter_by(url=horror_url).first()
                if not existing:
                    new_cache = APICache(url=horror_url, response_json=json.dumps(resp.json()))
                    db.session.add(new_cache)
                    db.session.commit()
            else:
                 raise Exception("Non-200 status")
        except Exception as e:
            print(f"Failed to fetch Horror movies: {e}")
            inject_dummy_data(horror_url, "Horror")
            
        print("Population complete.")

if __name__ == "__main__":
    populate()
