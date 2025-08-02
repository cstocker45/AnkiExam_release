from aqt import mw
from aqt.qt import *
from .ClientAuth import AuthClient
import os

def update_token_display():
    auth_client = AuthClient()
    if auth_client.is_authenticated():
        total_tokens = auth_client.get_token_usage()
        mw.statusBar().showMessage(f"Total Tokens Used: {total_tokens}")

# Create a QTimer for periodic updates
token_update_timer = QTimer()
token_update_timer.timeout.connect(update_token_display)
token_update_timer.start(30000)  # Update every 30 seconds

# Initial update
update_token_display()
