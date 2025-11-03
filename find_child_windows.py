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

def list_child_windows(parent_hwnd):
    """List all child windows and their classes"""
    children = []

    def callback(hwnd, param):
        class_name = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        is_visible = win32gui.IsWindowVisible(hwnd)
        children.append((hwnd, class_name, title, is_visible))

    win32gui.EnumChildWindows(parent_hwnd, callback, None)
    return children

if __name__ == "__main__":
    parent = find_bluestacks_window()
    if not parent:
        print("BlueStacks window not found!")
        exit(1)

    print(f"Parent Window: {parent}")
    print(f"Parent Title: {win32gui.GetWindowText(parent)}")
    print(f"Parent Class: {win32gui.GetClassName(parent)}")
    print("\nChild Windows:")
    print("-" * 80)

    children = list_child_windows(parent)
    for hwnd, class_name, title, visible in children:
        vis_str = "VISIBLE" if visible else "hidden"
        # Handle unicode safely
        safe_title = title.encode('ascii', errors='replace').decode('ascii') if title else "(no title)"
        title_str = f'"{safe_title}"' if title else "(no title)"
        print(f"HWND: {hwnd:8d} | Class: {class_name:30s} | {vis_str:7s} | {title_str}")

    print(f"\nTotal child windows: {len(children)}")
