# Claude Instructions for xclash Project

## CRITICAL: Image Viewing Policy

**NEVER use the Read tool directly to view images (PNG, JPG, etc.)** - this causes system crashes.

**ALWAYS use the Task tool with a general-purpose agent to view images** instead.

### Example - WRONG ❌:
```
Read(screenshot.png)  # This will crash!
```

### Example - CORRECT ✓:
```
Task(
  subagent_type="general-purpose",
  model="haiku",
  description="View screenshot",
  prompt="Please read and examine the file 'screenshot.png' and describe what you see..."
)
```

This applies to ALL image files including:
- Screenshots (.png)
- Debug visualizations (.png)
- Templates (.png)
- Any other image formats (.jpg, .jpeg, etc.)

## Project Context

This is an automation project for Clash of Clans using BlueStacks Android emulator.

Key components:
- ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554`
- Screen resolution: 2560x1440 (constant)
- Python path: `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`

## Game Controls

### World/Town View Switching (ADB)
Use the `view_detection.py` utility for switching between WORLD and TOWN views.

```python
from view_detection import switch_to_view, ViewState
from find_player import ADBController, Config

config = Config()
adb = ADBController(config)

# Switch to WORLD view
switch_to_view(adb, ViewState.WORLD)

# Switch to TOWN view
switch_to_view(adb, ViewState.TOWN)
```

**How it works**:
- Clicks at position (2460, 1315) which is x_frac=0.75, y_frac=0.5 of the button
- This single position toggles between WORLD ↔ TOWN states
- No need to click different sides - same position works for both directions

See `templates/buttons/WORLD_TOWN_DETECTION.md` for full documentation.

### Arrow Keys (Windows API)
Arrow key input uses Windows API (not ADB) with foreground focus required.

Location: `send_arrow_proper.py`

```python
import win32api
import win32con
import win32gui

# Must bring BlueStacks window to foreground
hwnd = win32gui.FindWindow(None, "BlueStacks App Player")
win32gui.SetForegroundWindow(hwnd)

# Send arrow key
VK_LEFT = 0x25   # Left arrow
VK_UP = 0x26     # Up arrow
VK_RIGHT = 0x27  # Right arrow
VK_DOWN = 0x28   # Down arrow

# Press and release
win32api.keybd_event(VK_RIGHT, 0, 0, 0)  # Press
win32api.keybd_event(VK_RIGHT, 0, win32con.KEYEVENT_KEYUP, 0)  # Release
```

**Key points**:
- BlueStacks window MUST have foreground focus
- Cannot send arrow keys to background window
- ADB input commands do NOT work for arrow keys in this game

### Zoom In/Out (Windows API)
Zoom uses Windows keyboard input (I/O keys) with foreground focus.

Location: `send_zoom.py`

```python
import win32api
import win32con
import win32gui

hwnd = win32gui.FindWindow(None, "BlueStacks App Player")
win32gui.SetForegroundWindow(hwnd)

# Zoom in: Press 'I' key
win32api.keybd_event(0x49, 0, 0, 0)  # 0x49 = 'I'
win32api.keybd_event(0x49, 0, win32con.KEYEVENT_KEYUP, 0)

# Zoom out: Press 'O' key
win32api.keybd_event(0x4F, 0, 0, 0)  # 0x4F = 'O'
win32api.keybd_event(0x4F, 0, win32con.KEYEVENT_KEYUP, 0)
```

**Key points**:
- 'I' key = Zoom IN
- 'O' key = Zoom OUT
- Requires foreground focus like arrow keys
- ADB input does NOT work for zoom

### Clicking/Tapping (ADB)
For clicking UI elements, use ADB tap commands.

```python
from find_player import ADBController, Config

config = Config()
adb = ADBController(config)

# Click at specific coordinates
adb.tap(x, y)

# Swipe (for dragging)
adb.swipe(x1, y1, x2, y2, duration_ms=300)
```

**Key points**:
- ADB tap works for clicking buttons, UI elements
- No foreground focus required
- Coordinates are absolute (2560x1440 screen)
- For World/Town toggle: use `view_detection.py` utility instead of raw tapping

### Summary Table

| Control | Method | Focus Required | Implementation |
|---------|--------|----------------|----------------|
| World/Town Toggle | ADB tap | No | `view_detection.py` |
| UI Clicking | ADB tap | No | `adb.tap(x, y)` |
| Arrow Keys | Win32 API | Yes | `send_arrow_proper.py` |
| Zoom In/Out | Win32 API (I/O keys) | Yes | `send_zoom.py` |
| Map Dragging | ADB swipe | No | `adb.swipe(x1, y1, x2, y2)` |
