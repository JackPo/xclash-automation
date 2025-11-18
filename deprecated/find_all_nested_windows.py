import win32gui
import win32con

def find_bluestacks_window():
    """Find main BlueStacks window"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    windows = []
    win32gui.EnumWindows(callback, windows)

    if windows:
        return windows[0][0]
    return None

def list_all_windows_recursive(hwnd, level=0):
    """Recursively list all nested child windows"""
    indent = "  " * level
    class_name = win32gui.GetClassName(hwnd)
    title = win32gui.GetWindowText(hwnd)
    is_visible = win32gui.IsWindowVisible(hwnd)

    safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else ""
    vis = "V" if is_visible else "H"

    print(f"{indent}[{vis}] HWND:{hwnd:8d} Class:{class_name:30s} Title:\"{safe_title}\"")

    # Recursively enumerate children
    children = []
    def callback(child_hwnd, param):
        children.append(child_hwnd)

    win32gui.EnumChildWindows(hwnd, callback, None)

    for child in children:
        list_all_windows_recursive(child, level + 1)

if __name__ == "__main__":
    parent = find_bluestacks_window()
    if not parent:
        print("BlueStacks window not found!")
        exit(1)

    print("Complete Window Hierarchy:")
    print("=" * 100)
    list_all_windows_recursive(parent, 0)
