import win32gui
import win32con

def find_all_windows_system_wide():
    """Find ALL windows in the entire system, filter for anything related to BlueStacks or Android"""
    all_windows = []

    def callback(hwnd, param):
        if win32gui.IsWindow(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            is_visible = win32gui.IsWindowVisible(hwnd)

            # Look for ANY window that might be related
            keywords = ["bluestacks", "android", "hd-", "plugin", "player", "emulator", "qt", "blue"]

            title_lower = title.lower()
            class_lower = class_name.lower()

            if any(kw in title_lower or kw in class_lower for kw in keywords):
                all_windows.append((hwnd, class_name, title, is_visible))

    win32gui.EnumWindows(callback, None)
    return all_windows

if __name__ == "__main__":
    print("=" * 100)
    print("SEARCHING ENTIRE SYSTEM FOR BLUESTACKS/ANDROID RELATED WINDOWS")
    print("=" * 100)

    windows = find_all_windows_system_wide()

    for hwnd, class_name, title, visible in windows:
        vis = "VISIBLE" if visible else "HIDDEN"
        safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else "(no title)"
        print(f"[{vis:7s}] HWND:{hwnd:8d} | Class:{class_name:35s} | Title:\"{safe_title}\"")

    print(f"\nTotal found: {len(windows)}")

    # Also specifically look for "Android" in title
    print("\n" + "=" * 100)
    print("WINDOWS WITH 'Android' IN TITLE:")
    print("=" * 100)

    android_windows = [w for w in windows if 'android' in w[2].lower()]
    if android_windows:
        for hwnd, class_name, title, visible in android_windows:
            vis = "VISIBLE" if visible else "HIDDEN"
            safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else "(no title)"
            print(f"[{vis:7s}] HWND:{hwnd:8d} | Class:{class_name:35s} | Title:\"{safe_title}\"")
    else:
        print("No windows with 'Android' in title found")
