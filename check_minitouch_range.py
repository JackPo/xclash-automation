#!/usr/bin/env python3
"""
Check minitouch touch range
"""

import subprocess
import time
from find_player import Config

def check_range():
    config = Config()
    adb = config.ADB_PATH
    device = config.DEVICE

    print("Checking minitouch touch range...")

    # Run minitouch in interactive mode and capture first few lines
    cmd = [adb, "-s", device, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Read first 5 lines
    for i in range(5):
        line = proc.stdout.readline()
        print(line.strip())

    # Kill the process
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    check_range()
