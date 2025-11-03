"""
Create template image of World/Town button for template matching
"""
import subprocess
import cv2

ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

# Capture screenshot
print("Capturing screenshot...")
subprocess.run([ADB, '-s', DEVICE, 'shell', 'screencap', '-p', '/sdcard/temp.png'],
               capture_output=True)
subprocess.run([ADB, '-s', DEVICE, 'pull', '/sdcard/temp.png', 'current_screen.png'],
               capture_output=True)

# Load image
img = cv2.imread('current_screen.png')
if img is None:
    print("ERROR: Could not load screenshot")
    exit(1)

height, width = img.shape[:2]
print(f"Screenshot size: {width}x{height}")

# Extract lower-right corner where button should be
# Based on game_utils.py: WORLD_TOGGLE_X = 2350, WORLD_TOGGLE_Y = 1350
# Let's extract a region around that area
button_x = 2350
button_y = 1350
margin = 100

# Crop area around button
x1 = max(0, button_x - margin)
y1 = max(0, button_y - margin)
x2 = min(width, button_x + margin)
y2 = min(height, button_y + margin)

button_region = img[y1:y2, x1:x2]

# Save for manual inspection
cv2.imwrite('button_region_full.png', button_region)
print(f"Saved button region ({x2-x1}x{y2-y1}) to button_region_full.png")
print(f"Region coordinates: ({x1},{y1}) to ({x2},{y2})")
print("\nPlease crop this image to just the button and save as 'town_button_template.png'")
print("Then we'll use it for template matching!")
