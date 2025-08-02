import uuid
import subprocess
import platform
import re

def get_stable_mac_address():
    """Get a stable MAC address that won't change between network interfaces"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        try:
            # Get the MAC address of en0 (usually the primary interface on macOS)
            output = subprocess.check_output(["networksetup", "-getmacaddress", "en0"]).decode()
            mac = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", output)
            if mac:
                return mac.group(0).replace(":", "").lower()
        except:
            pass
    elif system == "Windows":
        try:
            # Get the MAC address of the active interface on Windows
            output = subprocess.check_output("getmac /v /fo csv /nh", shell=True).decode()
            mac = re.search(r"([0-9A-Fa-f]{2}-){5}([0-9A-Fa-f]{2})", output)
            if mac:
                return mac.group(0).replace("-", "").lower()
        except:
            pass
    elif system == "Linux":
        try:
            # Try to get the MAC address of the default interface on Linux
            output = subprocess.check_output(["ip", "route", "get", "1"]).decode()
            default_interface = re.search(r"dev\s+(\S+)", output).group(1)
            with open(f"/sys/class/net/{default_interface}/address") as f:
                return f.read().strip().replace(":", "").lower()
        except:
            pass
    
    # Fallback to uuid.getnode() if platform-specific methods fail
    return format(uuid.getnode(), '012x').lower()
