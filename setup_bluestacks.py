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

    # Try connecting to common ports
    ports = [5556, 5555, 5554, 5557, 5558]

    for port in ports:
        print(f"  Trying 127.0.0.1:{port}...", end=" ")
        success, _, _ = run_adb(["connect", f"127.0.0.1:{port}"])
        if success:
            # Verify it's actually online
            time.sleep(0.5)
            success, stdout, _ = run_adb(["devices"])
            if f"127.0.0.1:{port}" in stdout and "device" in stdout:
                print("OK - Connected!")
                return f"127.0.0.1:{port}"
            print("offline")
        else:
            print("refused")

    # Also check for emulator-XXXX devices
    success, stdout, _ = run_adb(["devices"])
    if "emulator-" in stdout:
        lines = stdout.strip().split('\n')[1:]  # Skip header
        for line in lines:
            if "device" in line and "emulator-" in line:
                device = line.split()[0]
                print(f"  Found {device}")
                return device

    return None

def get_current_resolution(device):
    """Get current screen resolution."""
    success, stdout, _ = run_adb(["-s", device, "shell", "wm", "size"])
    if success:
        # Parse "Physical size: 1920x1080" or "Override size: 3088x1440"
        for line in stdout.split('\n'):
            if 'size:' in line.lower():
                parts = line.split(':')
                if len(parts) > 1:
                    res = parts[-1].strip()
                    if 'x' in res:
                        return res
    return None

def set_resolution(device):
    """Reset to native 4K resolution."""
    print(f"\nResetting to native 4K resolution (3840x2160)...")

    # Reset to native resolution (3840x2160)
    success, _, _ = run_adb(["-s", device, "shell", "wm", "size", "reset"])
    if not success:
        print("  ERROR: Failed to reset size")
        return False

    # Reset to native density (560)
    success, _, _ = run_adb(["-s", device, "shell", "wm", "density", "reset"])
    if not success:
        print("  ERROR: Failed to reset density")
        return False

    print("  OK - Native 4K resolution restored")
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

    # Reset to native 4K resolution
    print(f"\nTarget configuration:")
    print(f"  Resolution: 3840x2160 (native 4K)")
    print(f"  Density: 560 DPI (native)")
    print(f"  Note: Native 4K resolution, no scaling")

    if set_resolution(device):
        verify_resolution(device)

        # Update config file
        print("\nUpdating find_player.py config...")
        try:
            with open('find_player.py', 'r') as f:
                content = f.read()

            # Update DEVICE line
            import re
            content = re.sub(
                r'DEVICE = "[^"]*"',
                f'DEVICE = "{device}"',
                content
            )

            with open('find_player.py', 'w') as f:
                f.write(content)
            print("  OK - Config updated")
        except Exception as e:
            print(f"  ERROR: Could not update config: {e}")

        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        print("\nBenefits:")
        print("  - Native 4K rendering (3840x2160)")
        print("  - Extremely sharp text (2.25x pixels vs 2560x1440)")
        print("  - Better OCR accuracy")
        print("  - Improved template matching")
        print("\nNote: Native 4K resolution with auto-crop to 2560x1440 for templates.")
    else:
        print("\nERROR: Setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
