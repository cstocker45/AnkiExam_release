import json
import os
from datetime import datetime

class TokenHistoryManager:
    def __init__(self):
        self.history_file = os.path.join(os.path.dirname(__file__), 'token_history.json')
        self._ensure_history_file()

    def _ensure_history_file(self):
        """Create history file if it doesn't exist"""
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump({"entries": []}, f)

    def add_entry(self, tokens_used, request_type, details=""):
        """Add a new token usage entry
        Args:
            tokens_used (int): Number of tokens used in the request
            request_type (str): Type of request ('answer' or 'question')
            details (str): Additional details about the request
        """
        try:
            with open(self.history_file, 'r') as f:
                history = json.load(f)

            entry = {
                "timestamp": datetime.now().isoformat(),
                "tokens_used": tokens_used,
                "request_type": request_type,
                "details": details
            }

            history["entries"].append(entry)

            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)

            print(f"Added token history entry: {tokens_used} tokens for {request_type}")
            return True
        except Exception as e:
            print(f"Error adding token history entry: {str(e)}")
            return False

    def get_history(self, limit=None):
        """Get token usage history
        Args:
            limit (int, optional): Limit the number of entries to return
        Returns:
            list: List of history entries
        """
        try:
            with open(self.history_file, 'r') as f:
                history = json.load(f)
            entries = history["entries"]
            if limit:
                entries = entries[-limit:]
            return entries
        except Exception as e:
            print(f"Error getting token history: {str(e)}")
            return []

    def get_total_tokens(self):
        """Get total tokens used across all requests
        Returns:
            int: Total tokens used
        """
        try:
            with open(self.history_file, 'r') as f:
                history = json.load(f)
            return sum(entry["tokens_used"] for entry in history["entries"])
        except Exception as e:
            print(f"Error calculating total tokens: {str(e)}")
            return 0

# Create a singleton instance
token_history = TokenHistoryManager()
