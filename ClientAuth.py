import requests

SERVER_URL = "https://colestocker.fly.dev"  # Your Fly.io server URL

class AuthClient:
    def __init__(self):
        self.token = None
        self.username = None
        self.user_access_key = None

    def login(self, username, password):
        url = f"{SERVER_URL}/token"
        data = {"username": username, "password": password}
        try:
            r = requests.post(url, data=data)
            if r.status_code == 200:
                self.token = r.json()["access_token"]
                self.username = username
                # Generate a unique access key from the token
                self.user_access_key = f"ak_{self.token[:16]}"
                return True
            else:
                print("Login failed:", r.text)
                self.clear_auth()
                return False
        except Exception as e:
            print("Error connecting to server:", e)
            self.clear_auth()
            return False

    def clear_auth(self):
        """Clear all authentication data"""
        self.token = None
        self.username = None
        self.user_access_key = None

    def get_access_key(self):
        """Get the current user access key"""
        return self.user_access_key

    def is_authenticated(self):
        """Check if user is authenticated and has valid access key"""
        return bool(self.token and self.user_access_key)

    def add_tokens(self, amount):
        if not self.is_authenticated():
            print("Not authenticated.")
            return None
        url = f"{SERVER_URL}/add_tokens"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"amount": amount}
        r = requests.post(url, params=params, headers=headers)
        return r.json()

    def get_me(self):
        if not self.is_authenticated():
            print("Not authenticated.")
            return None
        url = f"{SERVER_URL}/me"
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers)
        return r.json()

    def register(self, username, password, email, mac_address):
        url = f"{SERVER_URL}/register_request"
        data = {
            "username": username,
            "password": password,
            "email": email,
            "mac_address": mac_address
        }
        try:
            r = requests.post(url, data=data)
            if r.status_code == 200:
                return True, "Registration successful! Check your email for verification code."
            else:
                return False, r.json().get("detail", "Registration failed.")
        except Exception as e:
            return False, f"Error connecting to server: {e}"

    def verify_code(self, username, code):
        url = f"{SERVER_URL}/verify_code"
        data = {
            "username": username,
            "code": code
        }
        try:
            r = requests.post(url, data=data)
            if r.status_code == 200:
                return True, "Account verified successfully! You can now log in."
            else:
                return False, r.json().get("detail", "Verification failed.")
        except Exception as e:
            return False, f"Error connecting to server: {e}"