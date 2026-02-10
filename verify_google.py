import requests

BASE_URL = "http://127.0.0.1:5001"

def verify_buttons():
    print("Checking Login Page...")
    try:
        r = requests.get(f"{BASE_URL}/login")
        if "Sign in with Google" in r.text:
            print("PASS: Google Login button found.")
        else:
            print("FAIL: Google Login button NOT found.")
    except Exception as e:
        print(f"Error accessing login: {e}")

    print("\nChecking Signup Page...")
    try:
        r = requests.get(f"{BASE_URL}/signup")
        if "Sign up with Google" in r.text:
            print("PASS: Google Signup button found.")
        else:
            print("FAIL: Google Signup button NOT found.")
    except Exception as e:
        print(f"Error accessing signup: {e}")

if __name__ == "__main__":
    verify_buttons()
