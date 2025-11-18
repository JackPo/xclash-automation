#!/usr/bin/env python3
"""Crop image using Gemini segmentation coordinates."""

import cv2
import sys

def crop_image(input_path, x, y, w, h, output_path):
    """Crop image at specified coordinates."""
    img = cv2.imread(input_path)
    if img is None:
        print(f"ERROR: Could not read image from {input_path}")
        sys.exit(1)

    # Crop using the bounding box
    cropped = img[y:y+h, x:x+w]

    # Save the cropped image
    cv2.imwrite(output_path, cropped)
    print(f"Cropped image saved to: {output_path}")
    print(f"Cropped dimensions: {w}x{h}")

    return cropped.shape

if __name__ == "__main__":
    # Gemini coordinates: x=936, y=926, w=31, h=24
    input_path = "C:/Users/mail/xclash/current_screenshot_llm.png"
    output_path = "C:/Users/mail/xclash/templates/ground_truth/agent_iteration_1.png"

    x, y, w, h = 936, 926, 31, 24

    shape = crop_image(input_path, x, y, w, h, output_path)
    print(f"Final shape (height, width, channels): {shape}")
