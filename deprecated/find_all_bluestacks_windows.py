import win32gui
import win32con

def find_all_windows_with_bluestacks():
    """Find ALL windows in the system related to BlueStacks"""
    all_windows = []

    def callback(hwnd, param):
        if win32gui.IsWindow(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            is_visible = win32gui.IsWindowVisible(hwnd)

            # Check if related to BlueStacks
            if ("BlueStacks" in title or
                "BlueStacks" in class_name or
                "plr" in class_name.lower() or
                "HD-" in title):
                all_windows.append((hwnd, class_name, title, is_visible))

    win32gui.EnumWindows(callback, None)
    return all_windows

def find_windows_by_class_pattern(pattern):
    """Find windows matching a class name pattern"""
    matching = []

    def callback(hwnd, param):
        if win32gui.IsWindow(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            if pattern.lower() in class_name.lower():
                title = win32gui.GetWindowText(hwnd)
                is_visible = win32gui.IsWindowVisible(hwnd)
                matching.append((hwnd, class_name, title, is_visible))

    win32gui.EnumWindows(callback, None)
    return matching

if __name__ == "__main__":
    print("=" * 100)
    print("ALL BLUESTACKS-RELATED WINDOWS:")
    print("=" * 100)

    windows = find_all_windows_with_bluestacks()
    for hwnd, class_name, title, visible in windows:
        vis = "VISIBLE" if visible else "HIDDEN"
        safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else ""
        print(f"[{vis:7s}] HWND:{hwnd:8d} | Class:{class_name:35s} | Title:\"{safe_title}\"")

    print(f"\nTotal found: {len(windows)}")

    print("\n" + "=" * 100)
    print("SEARCHING FOR 'plrNativeInputWindowClass':")
    print("=" * 100)

    plr_windows = find_windows_by_class_pattern("plr")
    if plr_windows:
        for hwnd, class_name, title, visible in plr_windows:
            vis = "VISIBLE" if visible else "HIDDEN"
            safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else ""
            print(f"[{vis:7s}] HWND:{hwnd:8d} | Class:{class_name:35s} | Title:\"{safe_title}\"")
    else:
        print("No windows with 'plr' in class name found.")

    print("\n" + "=" * 100)
    print("SEARCHING FOR INPUT/NATIVE RELATED CLASSES:")
    print("=" * 100)

    input_windows = find_windows_by_class_pattern("input")
    native_windows = find_windows_by_class_pattern("native")

    all_special = input_windows + native_windows
    if all_special:
        for hwnd, class_name, title, visible in all_special:
            vis = "VISIBLE" if visible else "HIDDEN"
            safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else ""
            print(f"[{vis:7s}] HWND:{hwnd:8d} | Class:{class_name:35s} | Title:\"{safe_title}\"")
    else:
        print("No input/native windows found.")
