"""
Set BlueStacks resolution to 2560x1440 via ADB.
Run this after BlueStacks starts.
"""
import subprocess
import time

adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

print("Connecting to BlueStacks...")
# Try multiple ports
for port in [5556, 5555, 5554]:
    result = subprocess.run([adb, "connect", f"127.0.0.1:{port}"],
                          capture_output=True, text=True)
    if "connected" in result.stdout:
        print(f"Connected on port {port}")
        device = f"127.0.0.1:{port}"
        break
else:
    print("ERROR: Could not connect to any device!")
    input("Press Enter to exit...")
    exit(1)

print(f"Setting resolution to 3088x1440 (supersampled for sharp rendering)...")
subprocess.run([adb, "-s", device, "shell", "wm", "size", "3088x1440"])
subprocess.run([adb, "-s", device, "shell", "wm", "density", "560"])

# Verify
time.sleep(1)
result = subprocess.run([adb, "-s", device, "shell", "wm", "size"],
                       capture_output=True, text=True)
print(f"Current resolution: {result.stdout.strip()}")

result = subprocess.run([adb, "-s", device, "shell", "wm", "density"],
                       capture_output=True, text=True)
print(f"Current density: {result.stdout.strip()}")

print("\nResolution set to 3088x1440!")
print("Note: Game renders at 3088x1440, downsampled to 2560x1440 for display (supersampling)")
print("This will reset when BlueStacks restarts - run this script again after restart.")
