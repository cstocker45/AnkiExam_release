import requests
import time

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
                # Save credentials after successful login
                from .shared import credential_manager
                credential_manager.save_credentials(username, password, self.user_access_key)
                return True
            else:
                print(f"Login failed: {r.text}")
                self.clear_auth()
                return False
        except Exception as e:
            print(f"Error connecting to server: {e}")
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
            print("Not authenticated when trying to add tokens.")
            return False
        
        url = f"{SERVER_URL}/api/update_tokens"
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "username": self.username,
                "tokens": str(amount)
            }
            print(f"Sending token update request. Amount: {amount}, Username: {self.username}")  # Debug logging
            
            r = requests.post(url, data=data, headers=headers)
            response_data = r.json() if r.text else {}
            print(f"Token update response: {response_data}")  # Debug logging
            
            if r.status_code == 200:
                # Wait briefly for the server to process
                time.sleep(1)
                return True
            else:
                print(f"Failed to update tokens. Status code: {r.status_code}, Response: {r.text}")
                return False
        except Exception as e:
            print(f"Error updating tokens: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
            
    def get_token_usage(self):
        if not self.is_authenticated():
            print("Not authenticated.")
            return 0
            
        url = f"{SERVER_URL}/api/get_tokens/{self.username}"
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                return r.json()["token_usage"]
            else:
                print("Failed to get token usage:", r.text)
                return 0
        except Exception as e:
            print("Error getting token usage:", e)
            return 0
        except Exception as e:
            print(f"Error getting token usage: {str(e)}")
            return 0

    def get_me(self):
        if not self.is_authenticated():
            print("Not authenticated.")
            return None
        url = f"{SERVER_URL}/me"
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers)
        return r.json()

    def register(self, username, password, email, device_id):
        url = f"{SERVER_URL}/register_request"
        data = {
            "username": username,
            "password": password,
            "email": email,
            "device_id": device_id
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
        
