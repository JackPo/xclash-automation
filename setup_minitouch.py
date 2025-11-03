#!/usr/bin/env python3
"""
Setup minitouch on BlueStacks
"""

import subprocess
from find_player import Config

def setup_minitouch():
    config = Config()
    adb = config.ADB_PATH
    device = config.DEVICE

    print("Setting up minitouch on BlueStacks...")

    # Push minitouch binary
    print("Pushing minitouch binary...")
    push_cmd = [adb, "-s", device, "push", "minitouch", "/data/local/tmp/minitouch"]
    result = subprocess.run(push_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR pushing: {result.stderr}")
        return False

    print(f"Push result: {result.stdout}")

    # Set permissions
    print("Setting permissions...")
    chmod_cmd = [adb, "-s", device, "shell", "chmod", "755", "/data/local/tmp/minitouch"]
    result = subprocess.run(chmod_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR chmod: {result.stderr}")
        return False

    # Verify it exists
    print("Verifying installation...")
    ls_cmd = [adb, "-s", device, "shell", "ls", "-l", "/data/local/tmp/minitouch"]
    result = subprocess.run(ls_cmd, capture_output=True, text=True)
    print(f"File info: {result.stdout}")

    print("\nSUCCESS! minitouch is installed.")
    return True

if __name__ == "__main__":
    setup_minitouch()
