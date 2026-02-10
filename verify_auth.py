import requests
import re

BASE_URL = "http://127.0.0.1:5001"
s = requests.Session()

def test_auth_flow():
    print("1. Testing Home Page Redirect...")
    r = s.get(BASE_URL, allow_redirects=True)
    if 'login' in r.url or 'Access Terminal' in r.text or 'Login' in r.text:
        print("PASS: Redirected to login or saw login page.")
    else:
        print(f"FAIL: Did not redirect to login. URL: {r.url}")

    print("\n2. Testing Weak Password Signup...")
    # Generate unique user
    import time
    timestamp = int(time.time())
    username = f"user_{timestamp}"
    email = f"user_{timestamp}@test.com"
    
    payload = {
        'username': username,
        'email': email,
        'password': 'weak'
    }
    r = s.post(f"{BASE_URL}/signup", data=payload, allow_redirects=True)
    if 'Password must be at least 8 chars' in r.text or 'signup' in r.url:
        print("PASS: Weak password rejected.")
    else:
        print("FAIL: Weak password might have been accepted.")

    print("\n3. Testing Valid Signup...")
    payload['password'] = 'StrongP@ss1'
    r = s.post(f"{BASE_URL}/signup", data=payload, allow_redirects=True)
    if 'login' in r.url or 'Access Terminal' in r.text:
        print("PASS: Signup successful, redirected to login.")
    else:
        print(f"FAIL: Signup failed. URL: {r.url}")

    print("\n4. Testing Login with Username...")
    login_payload = {
        'username': username,
        'password': 'StrongP@ss1'
    }
    r = s.post(f"{BASE_URL}/login", data=login_payload, allow_redirects=True)
    if 'dashboard' in r.url or 'Dashboard' in r.text or 'Logout' in r.text:
        print("PASS: Login with Username successful.")
    else:
        print(f"FAIL: Login with Username failed. Text: {r.text[:100]}...")

    print("\n5. Testing Logout...")
    s.get(f"{BASE_URL}/logout")
    
    print("\n6. Testing Login with Email...")
    login_payload = {
        'username': email,
        'password': 'StrongP@ss1'
    }
    r = s.post(f"{BASE_URL}/login", data=login_payload, allow_redirects=True)
    if 'dashboard' in r.url or 'Dashboard' in r.text:
        print("PASS: Login with Email successful.")
    else:
        print("FAIL: Login with Email failed.")

if __name__ == "__main__":
    try:
        test_auth_flow()
    except Exception as e:
        print(f"Error: {e}")
