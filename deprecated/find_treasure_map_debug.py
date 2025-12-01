#!/usr/bin/env python3
"""Use Gemini to find the bouncing treasure map icon and draw debug boxes."""
from PIL import Image, ImageDraw
import google.generativeai as genai
import sys
import json
import re

from config import GOOGLE_API_KEY as api_key
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Use the full resolution screenshot for accurate coordinates
img_path = sys.argv[1] if len(sys.argv) > 1 else "treasure_check.png"
img = Image.open(img_path)
width, height = img.size

print(f"Image size: {width}x{height}")

response = model.generate_content([
    f"""Look at this Clash of Clans screenshot (resolution: {width}x{height}).

    Find ALL bouncing/floating UI icons visible on screen. These are reward icons that players can click.

    Specifically look for:
    1. A TREASURE MAP icon - looks like a rolled scroll/parchment, possibly with an X mark
    2. Any other floating/bouncing clickable reward icons

    These icons typically:
    - Float/bounce above the game area
    - Have a distinct UI appearance (not part of terrain)
    - Are clickable rewards/events

    For EACH icon you find, provide:
    - name: what the icon represents
    - x: left edge in pixels
    - y: top edge in pixels
    - width: width in pixels
    - height: height in pixels

    Return as JSON array: [{{"name": "...", "x": ..., "y": ..., "width": ..., "height": ...}}, ...]
    """,
    img
])

print("Gemini response:")
print(response.text)

# Parse JSON from response
try:
    # Extract JSON from markdown code blocks if present
    text = response.text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    icons = json.loads(text.strip())

    # Draw debug boxes on image
    draw = ImageDraw.Draw(img)

    for icon in icons:
        x, y, w, h = icon['x'], icon['y'], icon['width'], icon['height']
        name = icon.get('name', 'unknown')

        # Draw red rectangle
        draw.rectangle([x, y, x+w, y+h], outline='red', width=5)

        # Draw label
        draw.text((x, y-30), name, fill='red')

        print(f"Found: {name} at ({x}, {y}) size {w}x{h}")

    # Save debug image
    debug_path = "treasure_map_debug.png"
    img.save(debug_path)
    print(f"\nDebug image saved to: {debug_path}")

except Exception as e:
    print(f"Error parsing JSON: {e}")
