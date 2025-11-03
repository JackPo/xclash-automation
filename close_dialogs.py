#!/usr/bin/env python3
"""
Close any open dialogs by tapping outside them
"""

import subprocess
from find_player import ADBController, Config

def close_dialogs():
    config = Config()
    adb = ADBController(config)

    print("Closing any open dialogs...")

    # Tap in upper left corner (usually safe area with no UI)
    # Try ESC key first
    cmd = [config.ADB_PATH, "-s", config.DEVICE, "shell", "input", "keyevent", "4"]  # KEYCODE_BACK
    subprocess.run(cmd)

    print("Sent BACK key")

if __name__ == "__main__":
    close_dialogs()
