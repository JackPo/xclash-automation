#!/usr/bin/env python3
"""
Iterative treasure map extraction using Gemini 2.0 Flash.
Following the documented process from HANDSHAKE_ICON_EXTRACTION.md
"""
import os
import sys
import json
import cv2
from google import genai
from google.genai import types
from PIL import Image

from config import GOOGLE_API_KEY as API_KEY

def segment_with_gemini(image_path, prompt):
    """Use Gemini to get bounding box for an object."""
    client = genai.Client(api_key=API_KEY)

    img = Image.open(image_path)
    img_width, img_height = img.size

    full_prompt = f"""Find {prompt}. Return bounding box coordinates.

Return a JSON list with:
{{"box_2d": [y0, x0, y1, x1], "label": "description"}}

DO NOT include mask field. Return ONLY the bounding box coordinates."""

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json"
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[full_prompt, img],
        config=config
    )

    segments = json.loads(response.text)

    # Descale from [0, 1000] to pixels
    # Format is [y0, x0, y1, x1]
    for seg in segments:
        if 'box_2d' in seg:
            box = seg['box_2d']
            y_min = int(box[0] * img_height / 1000)
            x_min = int(box[1] * img_width / 1000)
            y_max = int(box[2] * img_height / 1000)
            x_max = int(box[3] * img_width / 1000)

            seg['normalized'] = box
            seg['pixels'] = {
                'x': x_min,
                'y': y_min,
                'width': x_max - x_min,
                'height': y_max - y_min
            }

    return {
        'segments': segments,
        'image_size': (img_width, img_height),
        'raw': response.text
    }

def crop_from_original(original_path, x, y, w, h, output_path):
    """Crop a region from the original image."""
    img = cv2.imread(original_path)
    cropped = img[y:y+h, x:x+w]
    cv2.imwrite(output_path, cropped)
    return cropped.shape

def main():
    source_image = "treasure_check.png"

    # Verify source exists
    if not os.path.exists(source_image):
        print(f"ERROR: {source_image} not found!")
        sys.exit(1)

    img = cv2.imread(source_image)
    print(f"Source image: {source_image}")
    print(f"Resolution: {img.shape[1]}x{img.shape[0]}")

    # Track global offsets
    global_x_offset = 0
    global_y_offset = 0

    iterations = []
    current_image = source_image

    # ITERATION 1: Find treasure map in full screenshot
    print("\n" + "="*60)
    print("ITERATION 1: Initial detection")
    print("="*60)

    result = segment_with_gemini(current_image, "the bouncing treasure map icon")

    if not result['segments']:
        print("ERROR: No segments found!")
        sys.exit(1)

    seg = result['segments'][0]
    pixels = seg['pixels']

    print(f"Label: {seg.get('label', 'N/A')}")
    print(f"Normalized coords: {seg['normalized']}")
    print(f"Pixel coords: x={pixels['x']}, y={pixels['y']}, w={pixels['width']}, h={pixels['height']}")

    # Crop from original
    iter1_path = "treasure_iter1.png"
    crop_from_original(source_image, pixels['x'], pixels['y'], pixels['width'], pixels['height'], iter1_path)
    print(f"Saved: {iter1_path}")

    iterations.append({
        'iteration': 1,
        'input': current_image,
        'normalized': seg['normalized'],
        'pixels': pixels,
        'global_coords': {
            'x_min': pixels['x'],
            'y_min': pixels['y'],
            'x_max': pixels['x'] + pixels['width'],
            'y_max': pixels['y'] + pixels['height']
        },
        'output': iter1_path
    })

    global_x_offset = pixels['x']
    global_y_offset = pixels['y']
    current_image = iter1_path

    # ITERATION 2: Refine
    print("\n" + "="*60)
    print("ITERATION 2: Refinement")
    print("="*60)

    result = segment_with_gemini(current_image, "the treasure map icon")

    if not result['segments']:
        print("ERROR: No segments found in iteration 2!")
        sys.exit(1)

    seg = result['segments'][0]
    pixels = seg['pixels']

    print(f"Label: {seg.get('label', 'N/A')}")
    print(f"Normalized coords: {seg['normalized']}")
    print(f"Relative pixel coords: x={pixels['x']}, y={pixels['y']}, w={pixels['width']}, h={pixels['height']}")

    # Calculate global coordinates
    global_x = global_x_offset + pixels['x']
    global_y = global_y_offset + pixels['y']

    print(f"Global coords: x={global_x}, y={global_y}")

    # Crop from ORIGINAL source image using global coords
    iter2_path = "treasure_iter2.png"
    crop_from_original(source_image, global_x, global_y, pixels['width'], pixels['height'], iter2_path)
    print(f"Saved: {iter2_path}")

    iterations.append({
        'iteration': 2,
        'input': current_image,
        'normalized': seg['normalized'],
        'pixels': pixels,
        'global_coords': {
            'x_min': global_x,
            'y_min': global_y,
            'x_max': global_x + pixels['width'],
            'y_max': global_y + pixels['height']
        },
        'output': iter2_path
    })

    # Update for next iteration
    global_x_offset = global_x
    global_y_offset = global_y
    current_image = iter2_path

    # ITERATION 3: Final refinement
    print("\n" + "="*60)
    print("ITERATION 3: Final refinement")
    print("="*60)

    result = segment_with_gemini(current_image, "the treasure map")

    if result['segments']:
        seg = result['segments'][0]
        pixels = seg['pixels']

        print(f"Label: {seg.get('label', 'N/A')}")
        print(f"Normalized coords: {seg['normalized']}")
        print(f"Relative pixel coords: x={pixels['x']}, y={pixels['y']}, w={pixels['width']}, h={pixels['height']}")

        # Calculate global coordinates
        global_x = global_x_offset + pixels['x']
        global_y = global_y_offset + pixels['y']

        print(f"Global coords: x={global_x}, y={global_y}")

        # Final template
        final_path = "templates/ground_truth/treasure_map_4k.png"
        crop_from_original(source_image, global_x, global_y, pixels['width'], pixels['height'], final_path)
        print(f"Saved FINAL: {final_path}")

        iterations.append({
            'iteration': 3,
            'input': current_image,
            'normalized': seg['normalized'],
            'pixels': pixels,
            'global_coords': {
                'x_min': global_x,
                'y_min': global_y,
                'x_max': global_x + pixels['width'],
                'y_max': global_y + pixels['height']
            },
            'output': final_path
        })

        final_global = iterations[-1]['global_coords']
    else:
        print("No further refinement possible, using iteration 2 result")
        final_path = "templates/ground_truth/treasure_map_4k.png"
        crop_from_original(source_image, global_x_offset, global_y_offset,
                          iterations[-1]['pixels']['width'], iterations[-1]['pixels']['height'],
                          final_path)
        final_global = iterations[-1]['global_coords']

    # Save summary
    summary = {
        'source': source_image,
        'iterations': iterations,
        'final': {
            'path': final_path,
            'global_coords': final_global,
            'center_for_clicking': {
                'x': (final_global['x_min'] + final_global['x_max']) // 2,
                'y': (final_global['y_min'] + final_global['y_max']) // 2
            }
        }
    }

    with open('treasure_extraction_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Final template: {final_path}")
    print(f"Global coords: ({final_global['x_min']}, {final_global['y_min']}) to ({final_global['x_max']}, {final_global['y_max']})")
    print(f"Click at: ({summary['final']['center_for_clicking']['x']}, {summary['final']['center_for_clicking']['y']})")

if __name__ == "__main__":
    main()
