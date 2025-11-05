#!/usr/bin/env python3
"""
Test minitouch with a simple pinch gesture
"""

import subprocess
from find_player import Config
import time

def test_pinch_out():
    """Test zoom IN (pinch out) - two fingers move apart"""
    config = Config()

    # Minitouch protocol:
    # d = touch down
    # m = move
    # u = touch up
    # c = commit (execute all previous commands)

    # For 2560x1440, center is 1280, 720
    # Start two fingers close together, move them apart

    commands = """d 0 1200 720 50
d 1 1360 720 50
c
w 50
m 0 1100 720 50
m 1 1460 720 50
c
w 50
m 0 1000 720 50
m 1 1560 720 50
c
w 50
m 0 900 720 50
m 1 1660 720 50
c
w 50
m 0 800 720 50
m 1 1760 720 50
c
w 50
u 0
u 1
c
"""

    print("Testing minitouch pinch OUT (zoom in)...")
    print("Watch BlueStacks - should zoom IN")

    cmd = [config.ADB_PATH, "-s", config.DEVICE, "shell", "/data/local/tmp/minitouch"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        stdout, stderr = proc.communicate(input=commands, timeout=5)
        print(f"stdout: {stdout[:200]}")
        if stderr:
            print(f"stderr: {stderr[:200]}")
    except subprocess.TimeoutExpired:
        proc.kill()
        print("Timeout")

if __name__ == "__main__":
    test_pinch_out()
