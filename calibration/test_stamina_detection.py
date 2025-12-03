#!/usr/bin/env python3
"""
Test script to verify stamina claim detection logic.

This script checks:
1. Current stamina value (via OCR)
2. Whether red notification dot is present
3. Whether claim flow should be triggered

Run this to verify the fix for false positive stamina claim detections.
"""

import sys
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.stamina_red_dot_detector import has_stamina_red_dot
from utils.ocr_client import OCRClient, ensure_ocr_server
from config import STAMINA_REGION, ARMS_RACE_STAMINA_CLAIM_THRESHOLD

print("=" * 60)
print("Stamina Claim Detection Test")
print("=" * 60)

# Get screenshot
print("\n[1/3] Capturing screenshot...")
win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()
print("    Screenshot captured (4K)")

# Check stamina value
print("\n[2/3] Reading stamina value (OCR)...")
if not ensure_ocr_server(auto_start=True):
    print("ERROR: Could not start OCR server!")
    sys.exit(1)
ocr = OCRClient()
stamina = ocr.extract_number(frame, region=STAMINA_REGION)
print(f"    Stamina detected: {stamina}")

# Check for red dot
print("\n[3/3] Checking for red notification dot...")
has_dot, red_count = has_stamina_red_dot(frame, debug=False)
print(f"    Red pixels: {red_count}")
print(f"    Has red dot: {has_dot}")

# Decision
print("\n" + "=" * 60)
print("DECISION:")
print("=" * 60)

if stamina is None:
    print("RESULT: SKIP - Could not read stamina value")
elif stamina >= ARMS_RACE_STAMINA_CLAIM_THRESHOLD:
    print(f"RESULT: SKIP - Stamina {stamina} >= threshold {ARMS_RACE_STAMINA_CLAIM_THRESHOLD}")
elif not has_dot:
    print(f"RESULT: SKIP - Stamina {stamina} < {ARMS_RACE_STAMINA_CLAIM_THRESHOLD}, but NO red dot detected")
    print("         (Free claim not available yet)")
else:
    print(f"RESULT: TRIGGER CLAIM - Stamina {stamina} < {ARMS_RACE_STAMINA_CLAIM_THRESHOLD} AND red dot present")
    print("         (Free claim is available!)")

print("=" * 60)
