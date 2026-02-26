import requests
import sqlite3
import json

api_key = "ee499b4c77b749e072962081091122c0"

def test_url(name, url):
    print(f"Testing {name}: {url}")
    try:
        resp = requests.get(url, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('results', [])
            print(f"  Results: {len(results)}")
        else:
            print(f"  Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

# Check Cache
print("\n--- CACHE INSPECTION ---")
try:
    conn = sqlite3.connect('instance/bingelist.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url, length(response_json) FROM api_cache")
    rows = cursor.fetchall()
    print(f"Total Cache Entries: {len(rows)}")
    for url, length in rows:
        print(f"  {length} bytes: {url}")
except Exception as e:
    print(f"Cache access error: {e}")

# Test API
print("\n--- API TESTING ---")
test_url("Popular", f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=en-US&page=1")
test_url("Trending", f"https://api.themoviedb.org/3/trending/movie/week?api_key={api_key}")
test_url("Genre Action", f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}&with_genres=28&sort_by=popularity.desc&page=1")
