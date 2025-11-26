#!/usr/bin/env python3
"""Use Gemini to find the bouncing treasure map icon coordinates."""
from PIL import Image
import google.generativeai as genai
import sys
import json

api_key = 'AIzaSyBLvR_ZZ3scSldj_LX-Oax6ycG26U3rQ0A'
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Use the full resolution screenshot for accurate coordinates
img_path = sys.argv[1] if len(sys.argv) > 1 else "treasure_check.png"
img = Image.open(img_path)

print(f"Image size: {img.size}")

response = model.generate_content([
    """Look at this Clash of Clans screenshot carefully.

    At the BOTTOM of the screen there is a navigation bar with buttons like "Save the Dog", "Trial", "Hero", "Union", "World".

    I'm looking for a BOUNCING ANIMATED UI ICON that appears ABOVE one of these buttons (specifically above or near the "Hero" button area). This is a floating/bouncing reward icon that the player can click.

    It should be a small UI element (maybe 80-150 pixels) that looks like a treasure chest, treasure map scroll, or reward icon - NOT part of the game terrain/buildings.

    Look at the area just above the bottom navigation bar (y coordinates roughly 1900-2050 range) for any floating/bouncing icons.

    Please provide:
    1. Description of any floating/bouncing UI icons you see above the bottom navigation buttons
    2. The EXACT bounding box coordinates for the treasure/reward icon in this format:
       - x: left edge pixel coordinate
       - y: top edge pixel coordinate
       - width: width in pixels
       - height: height in pixels

    The image is 3840x2160 pixels (4K resolution).

    Return your answer as JSON with keys: description, x, y, width, height
    """,
    img
])
print(response.text)
