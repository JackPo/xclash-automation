#!/usr/bin/env python3
"""Extract treasure map template using Gemini coordinates."""
import cv2
import sys
import json

def crop_image(input_path, x, y, w, h, output_path):
    """Crop image at specified coordinates."""
    img = cv2.imread(input_path)
    if img is None:
        print(f"ERROR: Could not read image from {input_path}")
        sys.exit(1)

    print(f"Original image size: {img.shape[1]}x{img.shape[0]}")
    print(f"Cropping at: x={x}, y={y}, w={w}, h={h}")

    # Crop using the bounding box
    cropped = img[y:y+h, x:x+w]

    # Save the cropped image
    cv2.imwrite(output_path, cropped)
    print(f"Cropped image saved to: {output_path}")
    print(f"Cropped dimensions: {cropped.shape[1]}x{cropped.shape[0]}")

    return cropped.shape

if __name__ == "__main__":
    # Load coordinates from Gemini JSON output
    with open("treasure_map_coords.json", "r") as f:
        data = json.load(f)

    seg = data["segments"][0]
    box = seg["box_2d_pixels"]
    x_min, y_min, x_max, y_max = box
    w = x_max - x_min
    h = y_max - y_min

    print(f"Coordinates from Gemini: {box}")
    print(f"Label: {seg.get('label', 'N/A')}")

    input_path = "treasure_check.png"
    output_path = "templates/ground_truth/treasure_map_4k.png"

    shape = crop_image(input_path, x_min, y_min, w, h, output_path)
    print(f"Final shape (height, width, channels): {shape}")
