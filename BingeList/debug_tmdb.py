import requests
import os
from config import Config

def test_tmdb_connection():
    api_key = Config.TMDB_API_KEY
    print(f"Attempting to connect to: {url}")
    
    session = requests.Session()
    # Retry logic (no SSL/IPv4 hacks)
    adapter = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(connect=3, backoff_factor=0.5))
    session.mount('https://', adapter)
    
    try:
        response = session.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! Connection established.")
            data = response.json()
            print(f"Found {len(data.get('results', []))} movies.")
        else:
            print("Failed.")
            print(response.text)
    except requests.exceptions.ConnectTimeout:
        print("Error: Connection Timed Out.")
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Connection Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_tmdb_connection()
