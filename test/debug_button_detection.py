#!/usr/bin/env python3
"""Debug script to visualize what we're actually detecting."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
from find_player import Config, ADBController
from button_matcher import ButtonMatcher

config = Config()
adb = ADBController(config)

# Capture current screenshot
temp_path = Path("test/temp_button_debug.png")
adb.screenshot(temp_path)

# Load the screenshot
frame = cv2.imread(str(temp_path))
print(f"Screenshot size: {frame.shape}")

# Initialize button matcher
matcher = ButtonMatcher()

# Get match result
match = matcher.match(frame, save_debug=True)

if match:
    print(f"\nMatch found:")
    print(f"  Label: {match.label}")
    print(f"  Score: {match.score:.3f}")
    print(f"  Center: {match.center}")
    print(f"  Top-left: {match.top_left}")
    print(f"  Bottom-right: {match.bottom_right}")
    print(f"  Threshold: {matcher.threshold}")
    print(f"  Above threshold: {match.score >= matcher.threshold}")

    # Draw a rectangle around the detected region
    annotated = frame.copy()
    cv2.rectangle(annotated, match.top_left, match.bottom_right, (0, 255, 0), 3)
    cv2.circle(annotated, match.center, 10, (0, 0, 255), -1)

    # Add label text
    label_text = f"{match.label} ({match.score:.3f})"
    cv2.putText(annotated, label_text,
                (match.top_left[0], match.top_left[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Save annotated image
    output_path = Path("test/debug_button_annotated.png")
    cv2.imwrite(str(output_path), annotated)
    print(f"\nAnnotated screenshot saved to: {output_path}")
    print(f"Debug crop saved to: templates/debug/button_match_{match.label.lower()}.png")
else:
    print("\nNo match found!")
    print("Check if templates exist and are correct")

# Show template info
print(f"\nTemplate info:")
print(f"  Template dir: {matcher.template_dir}")
print(f"  Templates loaded: {list(matcher.templates.keys())}")
print(f"  Template shape: {matcher.template_shape}")
