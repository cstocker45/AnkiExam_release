from aqt.utils import tooltip, showInfo
from aqt.main import AnkiQt
from aqt import mw
import os
import sys
from PyQt6.QtCore import QFile, QIODevice
from PyQt6.QtGui import QIcon

def compile_resources():
    """Compile the Qt resources file"""
    try:
        from PyQt6.uic import compileUi
        from PyQt6.QtCore import QResource
        
        # Compile resources
        os.system('pyrcc5 resources.qrc -o resources_rc.py')
        showInfo("Resources compiled successfully")
        return True
    except Exception as e:
        showInfo(f"Error compiling resources: {str(e)}")
        return False

def setup():
    """Setup function that runs when the add-on is loaded"""
    try:
        # First compile resources
        if not compile_resources():
            showInfo("Failed to compile resources. Icons may not be available.")
        
        # Install required packages
        packages = [
            "cryptography>=41.0.0",
            "requests>=2.25.1",
            "PyQt6>=6.4.0"
        ]
        
        for package in packages:
            try:
                __import__(package.split(">=")[0])
            except ImportError:
                showInfo(f"Installing {package}...")
                from aqt.qt import pip_install
                pip_install(package)
        
        showInfo("Setup completed successfully!")
    except Exception as e:
        showInfo(f"Error during setup: {str(e)}")

if __name__ == "__main__":
    setup() 