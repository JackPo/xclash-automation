#!/usr/bin/env python3
"""
Check minitouch info
"""

import subprocess
from find_player import Config

config = Config()

print("Running minitouch to see its header...")

cmd = [config.ADB_PATH, "-s", config.DEVICE, "shell", "/data/local/tmp/minitouch -i"]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Send a simple single touch and quit
commands = """d 0 100 100 50
c
u 0
c
q
"""

try:
    stdout, stderr = proc.communicate(input=commands, timeout=3)
    print("STDOUT:")
    print(stdout)
    if stderr:
        print("STDERR:")
        print(stderr)
except subprocess.TimeoutExpired:
    proc.kill()
    stdout, stderr = proc.communicate()
    print("Timeout, but got:")
    print(stdout)
