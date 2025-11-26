#!/usr/bin/env python3
"""
Object detection using Gemini following official documentation.
https://ai.google.dev/gemini-api/docs/image-understanding#object_detection
"""
from google import genai
from google.genai import types
from PIL import Image
import json
import cv2

API_KEY = 'AIzaSyBLvR_ZZ3scSldj_LX-Oax6ycG26U3rQ0A'

client = genai.Client(api_key=API_KEY)

# Load image
image_path = "treasure_check.png"
image = Image.open(image_path)
width, height = image.size

print(f"Image size: {width}x{height}")

# Prompt following documentation format
prompt = """Detect the bouncing treasure map icon that is floating above the Hero button at the bottom navigation bar.
The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."""

config = types.GenerateContentConfig(
    response_mime_type="application/json"
)

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-05-20",
    contents=[image, prompt],
    config=config
)

print("Raw response:")
print(response.text)

# Parse and convert coordinates
bounding_boxes = json.loads(response.text)

print("\nParsed bounding boxes:")
for i, bbox in enumerate(bounding_boxes):
    print(f"\nBox {i+1}: {bbox}")

    if "box_2d" in bbox:
        box = bbox["box_2d"]
        # Descale from 0-1000 to actual pixels
        # Format: [ymin, xmin, ymax, xmax]
        abs_y1 = int(box[0] / 1000 * height)
        abs_x1 = int(box[1] / 1000 * width)
        abs_y2 = int(box[2] / 1000 * height)
        abs_x2 = int(box[3] / 1000 * width)

        print(f"  Label: {bbox.get('label', 'N/A')}")
        print(f"  Normalized: {box}")
        print(f"  Pixels: x={abs_x1}, y={abs_y1} to x={abs_x2}, y={abs_y2}")
        print(f"  Size: {abs_x2 - abs_x1}x{abs_y2 - abs_y1}")

        # Draw on image for verification
        img_cv = cv2.imread(image_path)
        cv2.rectangle(img_cv, (abs_x1, abs_y1), (abs_x2, abs_y2), (0, 255, 0), 5)
        cv2.putText(img_cv, bbox.get('label', 'detected')[:20], (abs_x1, abs_y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        # Save debug image
        scaled = cv2.resize(img_cv, (1920, 1080))
        cv2.imwrite('treasure_detected.png', scaled)
        print(f"\nSaved debug image: treasure_detected.png")

        # Also crop and save the detected region
        cropped = img_cv[abs_y1:abs_y2, abs_x1:abs_x2]
        cv2.imwrite('treasure_crop.png', cropped)
        print(f"Saved crop: treasure_crop.png ({abs_x2-abs_x1}x{abs_y2-abs_y1})")
