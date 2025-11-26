#!/usr/bin/env python3
"""
Generic object detection using Gemini.
Usage: python detect_object.py <image_path> "<prompt>"

Example:
  python detect_object.py screenshot.png "the bouncing treasure map icon above the Hero button"
"""
from google import genai
from google.genai import types
from PIL import Image
import json
import cv2
import sys
import os

API_KEY = 'AIzaSyBLvR_ZZ3scSldj_LX-Oax6ycG26U3rQ0A'

def detect_object(image_path: str, object_description: str, output_dir: str = "."):
    """
    Detect an object in an image using Gemini.

    Args:
        image_path: Path to the input image
        object_description: What to detect
        output_dir: Where to save output files

    Returns:
        dict with detection results
    """
    client = genai.Client(api_key=API_KEY)

    # Load image
    image = Image.open(image_path)
    width, height = image.size

    print(f"Image: {image_path}")
    print(f"Size: {width}x{height}")
    print(f"Detecting: {object_description}")
    print("-" * 60)

    # Prompt following official documentation format
    prompt = f"""Detect {object_description}.
The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."""

    config = types.GenerateContentConfig(
        response_mime_type="application/json"
    )

    response = client.models.generate_content(
        model="gemini-3-pro-preview",
        contents=[image, prompt],
        config=config
    )

    print("Raw response:")
    print(response.text)
    print("-" * 60)

    # Parse response
    try:
        bounding_boxes = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        return None

    if not bounding_boxes:
        print("ERROR: No objects detected")
        return None

    # Process first detection
    bbox = bounding_boxes[0] if isinstance(bounding_boxes, list) else bounding_boxes

    if "box_2d" not in bbox:
        print(f"ERROR: No box_2d in response: {bbox}")
        return None

    box = bbox["box_2d"]
    label = bbox.get("label", "detected")

    # Descale from 0-1000 to actual pixels
    # Format: [ymin, xmin, ymax, xmax]
    abs_y1 = int(box[0] / 1000 * height)
    abs_x1 = int(box[1] / 1000 * width)
    abs_y2 = int(box[2] / 1000 * height)
    abs_x2 = int(box[3] / 1000 * width)

    w = abs_x2 - abs_x1
    h = abs_y2 - abs_y1

    print(f"Label: {label}")
    print(f"Normalized coords: {box}")
    print(f"Pixel coords: ({abs_x1}, {abs_y1}) to ({abs_x2}, {abs_y2})")
    print(f"Size: {w}x{h}")
    print(f"Center: ({abs_x1 + w//2}, {abs_y1 + h//2})")

    # Draw debug image
    img_cv = cv2.imread(image_path)
    cv2.rectangle(img_cv, (abs_x1, abs_y1), (abs_x2, abs_y2), (0, 255, 0), 5)
    cv2.putText(img_cv, label[:30], (abs_x1, abs_y1-15),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

    # Save debug image (scaled for viewing)
    debug_path = os.path.join(output_dir, "detect_debug.png")
    scaled = cv2.resize(img_cv, (1920, 1080))
    cv2.imwrite(debug_path, scaled)
    print(f"\nDebug image: {debug_path}")

    # Save cropped region
    crop_path = os.path.join(output_dir, "detect_crop.png")
    cropped = cv2.imread(image_path)[abs_y1:abs_y2, abs_x1:abs_x2]
    cv2.imwrite(crop_path, cropped)
    print(f"Crop: {crop_path}")

    # Save results JSON
    result = {
        "image": image_path,
        "image_size": [width, height],
        "prompt": object_description,
        "label": label,
        "normalized": box,
        "pixels": {
            "x": abs_x1,
            "y": abs_y1,
            "width": w,
            "height": h
        },
        "center": {
            "x": abs_x1 + w // 2,
            "y": abs_y1 + h // 2
        }
    }

    json_path = os.path.join(output_dir, "detect_result.json")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Result JSON: {json_path}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python detect_object.py <image_path> \"<prompt>\"")
        print()
        print("Example:")
        print("  python detect_object.py screenshot.png \"the bouncing treasure map icon\"")
        sys.exit(1)

    image_path = sys.argv[1]
    prompt = sys.argv[2]

    if not os.path.exists(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    result = detect_object(image_path, prompt)

    if result:
        print("\n" + "=" * 60)
        print("SUCCESS")
        print(f"Detected at: ({result['pixels']['x']}, {result['pixels']['y']})")
        print(f"Size: {result['pixels']['width']}x{result['pixels']['height']}")
    else:
        print("\nFAILED")
        sys.exit(1)
