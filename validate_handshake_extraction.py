#!/usr/bin/env python3
"""
Programmatic validator for handshake icon extraction.
Analyzes the extracted image to determine if it's the correct white handshake icon.
"""
import cv2
import numpy as np
import sys
from pathlib import Path


def analyze_extraction(image_path):
    """
    Analyze an extracted icon to determine if it's the white handshake icon.

    Returns:
        dict: Analysis results with validation status
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "valid": False,
            "reason": f"Could not load image: {image_path}",
            "feedback": "Image file not found or corrupted"
        }

    h, w = img.shape[:2]

    # Convert to HSV for color analysis
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Define white color range (handshake icon should be white/light gray)
    lower_white = np.array([0, 0, 180])
    upper_white = np.array([180, 30, 255])
    white_mask = cv2.inRange(hsv, lower_white, upper_white)
    white_pixels = np.count_nonzero(white_mask)
    total_pixels = h * w
    white_ratio = white_pixels / total_pixels

    # Define blue color range (Union button background)
    lower_blue = np.array([100, 50, 50])
    upper_blue = np.array([130, 255, 255])
    blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
    blue_pixels = np.count_nonzero(blue_mask)
    blue_ratio = blue_pixels / total_pixels

    # Convert to grayscale for edge detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_pixels = np.count_nonzero(edges)
    edge_ratio = edge_pixels / total_pixels

    # Check if edges are on borders (indicating cut-off icon)
    border_thickness = 2
    top_border = edges[:border_thickness, :]
    bottom_border = edges[-border_thickness:, :]
    left_border = edges[:, :border_thickness]
    right_border = edges[:, -border_thickness:]

    border_edge_pixels = (np.count_nonzero(top_border) +
                          np.count_nonzero(bottom_border) +
                          np.count_nonzero(left_border) +
                          np.count_nonzero(right_border))

    total_border_pixels = (top_border.size + bottom_border.size +
                           left_border.size + right_border.size)
    border_edge_ratio = border_edge_pixels / total_border_pixels

    # Validation criteria
    results = {
        "dimensions": f"{w}x{h}",
        "white_ratio": f"{white_ratio:.2%}",
        "blue_ratio": f"{blue_ratio:.2%}",
        "edge_ratio": f"{edge_ratio:.2%}",
        "border_edge_ratio": f"{border_edge_ratio:.2%}",
    }

    # Decision logic
    feedback_points = []

    # Expect significant white content for handshake icon
    if white_ratio < 0.15:
        feedback_points.append(f"WARNING: Low white content ({white_ratio:.2%}) - handshake should have more white pixels")
    elif white_ratio > 0.60:
        feedback_points.append(f"WARNING: Too much white ({white_ratio:.2%}) - may have captured too much background")
    else:
        feedback_points.append(f"PASS: Good white content ({white_ratio:.2%})")

    # Expect some blue background (Union button)
    if blue_ratio < 0.20:
        feedback_points.append(f"WARNING: Low blue background ({blue_ratio:.2%}) - should capture some Union button blue")
    elif blue_ratio > 0.60:
        feedback_points.append(f"WARNING: Too much blue ({blue_ratio:.2%}) - may be mostly button background")
    else:
        feedback_points.append(f"PASS: Good blue background ({blue_ratio:.2%})")

    # Check for cut-off edges
    if border_edge_ratio > 0.15:
        feedback_points.append(f"WARNING: High border edges ({border_edge_ratio:.2%}) - icon may be cut off")
    else:
        feedback_points.append(f"PASS: Clean borders ({border_edge_ratio:.2%})")

    # Check reasonable dimensions (handshake should be roughly square-ish, 30-70 pixels)
    aspect_ratio = w / h
    if w < 25 or h < 25:
        feedback_points.append(f"WARNING: Too small ({w}x{h}) - icon likely incomplete")
    elif w > 80 or h > 80:
        feedback_points.append(f"WARNING: Too large ({w}x{h}) - may have captured too much")
    else:
        feedback_points.append(f"PASS: Good size ({w}x{h})")

    if aspect_ratio < 0.7 or aspect_ratio > 1.5:
        feedback_points.append(f"WARNING: Unusual aspect ratio ({aspect_ratio:.2f}) - handshake should be roughly square")
    else:
        feedback_points.append(f"PASS: Good aspect ratio ({aspect_ratio:.2f})")

    # Overall validation
    warning_count = sum(1 for f in feedback_points if "WARNING:" in f)

    if warning_count == 0:
        valid = True
        summary = "EXCELLENT - Extraction looks correct!"
    elif warning_count <= 2:
        valid = True
        summary = "ACCEPTABLE - Minor issues but likely correct"
    else:
        valid = False
        summary = f"FAILED - {warning_count} issues detected, needs adjustment"

    results["valid"] = valid
    results["summary"] = summary
    results["feedback"] = "\n".join(feedback_points)
    results["warning_count"] = warning_count

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_handshake_extraction.py <image_path>")
        sys.exit(1)

    image_path = Path(sys.argv[1])

    print(f"Analyzing: {image_path}")
    print("=" * 60)

    results = analyze_extraction(image_path)

    print(f"Dimensions: {results['dimensions']}")
    print(f"White ratio: {results['white_ratio']}")
    print(f"Blue ratio: {results['blue_ratio']}")
    print(f"Edge ratio: {results['edge_ratio']}")
    print(f"Border edge ratio: {results['border_edge_ratio']}")
    print()
    print("Feedback:")
    print(results['feedback'])
    print()
    print(results['summary'])

    return 0 if results['valid'] else 1


if __name__ == "__main__":
    sys.exit(main())
