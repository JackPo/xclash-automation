"""
Auto-setup BlueStacks for optimal XClash automation.
Finds the active device port and sets optimal resolution.
"""
import subprocess
import time
import sys

ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

def run_adb(args, capture=True):
    """Run ADB command."""
    cmd = [ADB] + args
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd)
        return result.returncode == 0, "", ""

def find_active_device():
    """Find active BlueStacks device by scanning ports."""
    print("Scanning for BlueStacks device...")

    # First restart ADB server to get clean state
    print("  Restarting ADB server...")
    run_adb(["kill-server"], capture=False)
    time.sleep(0.5)
    run_adb(["start-server"], capture=False)
    time.sleep(1.0)

    # Check for emulator-XXXX devices FIRST (these are the stable ones)
    success, stdout, _ = run_adb(["devices"])
    if "emulator-" in stdout:
        lines = stdout.strip().split('\n')[1:]  # Skip header
        for line in lines:
            if "\tdevice" in line and "emulator-" in line:
                device = line.split()[0]
                print(f"  Found {device} (online)")
                return device

    # Also try connecting to IP ports (but these may go offline)
    ports = [5556, 5555, 5554, 5557, 5558]
    for port in ports:
        print(f"  Trying 127.0.0.1:{port}...", end=" ")
        success, _, _ = run_adb(["connect", f"127.0.0.1:{port}"])
        if success:
            time.sleep(0.5)
            success, stdout, _ = run_adb(["devices"])
            if f"127.0.0.1:{port}\tdevice" in stdout:
                print("OK - Connected!")
                return f"127.0.0.1:{port}"
            print("offline")
        else:
            print("refused")

    return None

def get_current_resolution(device):
    """Get current screen resolution."""
    success, stdout, _ = run_adb(["-s", device, "shell", "wm", "size"])
    if success:
        # Parse "Physical size: 1920x1080" or "Override size: 3840x2160"
        for line in stdout.split('\n'):
            if 'size:' in line.lower():
                parts = line.split(':')
                if len(parts) > 1:
                    res = parts[-1].strip()
                    if 'x' in res:
                        return res
    return None

def set_resolution(device):
    """
    Set to 4K resolution (via 3088x1440 first).

    CRITICAL: The two-step resolution process is REQUIRED.
    Setting directly to 4K does NOT work reliably - the resolution
    will not stick properly. You MUST set to 3088x1440 first, then
    immediately set to 3840x2160. This has been empirically verified.

    Process:
    1. Set to 3088x1440 (intermediate step)
    2. Wait 1 second
    3. Set to 3840x2160 (final 4K resolution)
    4. Wait 1 second
    5. Set density to 560 DPI
    """
    print(f"\nSetting resolution to 4K (3840x2160)...")
    print(f"  (Using required two-step process: 3088x1440 -> 4K)")

    # Step 1: First set to 3088x1440 (REQUIRED intermediate step)
    # DO NOT SKIP THIS - direct 4K setting does not work!
    run_adb(["-s", device, "shell", "wm", "size", "3088x1440"])
    time.sleep(1)

    # Step 2: Then set to 4K (this only works after the 3088x1440 step)
    success, _, _ = run_adb(["-s", device, "shell", "wm", "size", "3840x2160"])
    if not success:
        print("  ERROR: Failed to set size")
        return False
    time.sleep(1)

    # Step 3: Set density to 560
    success, _, _ = run_adb(["-s", device, "shell", "wm", "density", "560"])
    if not success:
        print("  ERROR: Failed to set density")
        return False

    print("  OK - Resolution set to 4K")
    return True

def verify_resolution(device):
    """Verify the resolution was set correctly."""
    time.sleep(0.5)
    success, stdout, _ = run_adb(["-s", device, "shell", "wm", "size"])
    if success:
        print(f"\nCurrent configuration:")
        print(f"  {stdout.strip()}")

    success, stdout, _ = run_adb(["-s", device, "shell", "wm", "density"])
    if success:
        print(f"  {stdout.strip()}")

def main():
    print("=" * 60)
    print("BlueStacks Auto-Setup for XClash")
    print("=" * 60)

    # Find device
    device = find_active_device()
    if not device:
        print("\nERROR: No BlueStacks device found!")
        print("\nTroubleshooting:")
        print("  1. Make sure BlueStacks is running")
        print("  2. Try restarting BlueStacks")
        print("  3. Run: adb kill-server && adb start-server")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"\nOK - Found device: {device}")

    # Get current resolution
    current_res = get_current_resolution(device)
    if current_res:
        print(f"  Current resolution: {current_res}")

    # Set resolution
    print(f"\nTarget configuration:")
    print(f"  Resolution: 3840x2160 (4K)")
    print(f"  Density: 560 DPI")

    if set_resolution(device):
        verify_resolution(device)

        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        print("\nConfiguration:")
        print("  - Resolution: 3840x2160 (4K)")
        print("  - All templates and coordinates use 3840x2160")
    else:
        print("\nERROR: Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
