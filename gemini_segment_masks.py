#!/usr/bin/env python3
"""
Gemini 2.5 Flash segmentation with JSON masks (proper implementation).
Based on: https://developers.googleblog.com/en/conversational-image-segmentation-gemini-2-5/
"""
import os
import sys
import json
from google import genai
from google.genai import types
from PIL import Image


def segment_with_masks(image_path, object_description, api_key=None):
    """
    Use Gemini 2.5 Flash to get segmentation masks in JSON format.

    Args:
        image_path: Path to input image
        object_description: What to segment (e.g., "the handshake icon on top of the Union button")
        api_key: Google AI API key

    Returns:
        dict with:
            - segments: list of {label, box_2d, box_2d_pixels, mask}
            - image_size: (width, height)
            - raw_response: full Gemini response
    """
    if api_key is None:
        api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found")

    # Configure Gemini client
    os.environ["GOOGLE_API_KEY"] = api_key
    client = genai.Client(api_key=api_key)

    # Load image
    img = Image.open(image_path)
    img_width, img_height = img.size

    # Craft prompt following Google's recommended format
    prompt = f"""Find {object_description}. Return bounding box coordinates.

Return a JSON list with:
{{"box_2d": [y0, x0, y1, x1], "label": "description"}}

DO NOT include mask field. Return ONLY the bounding box coordinates."""

    # Configure with thinking_budget=0 for better object detection
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json"
    )

    # Generate response
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[prompt, img],
        config=config
    )

    # Parse JSON response (no markdown removal needed with response_mime_type)
    try:
        segments = json.loads(response.text)

        # CRITICAL: Descale coordinates from [0, 1000] to actual pixels
        # From https://ai.google.dev/gemini-api/docs/image-understanding#segmentation
        # "The coordinates, relative to image dimensions, scale to [0, 1000]"
        # IMPORTANT: Gemini returns coordinates in [y0, x0, y1, x1] format!
        for seg in segments:
            if 'box_2d' in seg:
                box_norm = seg['box_2d']
                if len(box_norm) == 4:
                    # Gemini format: [y0, x0, y1, x1]
                    # Descale from [0, 1000] to actual image dimensions
                    y_min = int(box_norm[0] * img_height / 1000)
                    x_min = int(box_norm[1] * img_width / 1000)
                    y_max = int(box_norm[2] * img_height / 1000)
                    x_max = int(box_norm[3] * img_width / 1000)

                    seg['box_2d_normalized'] = box_norm  # Keep original [y0, x0, y1, x1]
                    seg['box_2d_pixels'] = [x_min, y_min, x_max, y_max]  # Convert to [x, y, x, y]

        return {
            "success": True,
            "segments": segments,
            "image_size": [img_width, img_height],
            "raw_response": response.text
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON decode error: {e}",
            "raw_response": response.text
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Gemini 2.5 segmentation with JSON masks")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("description", help="Object to segment")
    parser.add_argument("--api-key", help="Google AI API key")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    print(f"Segmenting: '{args.description}' from {args.image}")
    print("Using Gemini 2.5 Flash with segmentation masks...")

    result = segment_with_masks(args.image, args.description, args.api_key)

    if result["success"]:
        segments = result["segments"]
        print(f"\nSUCCESS: Found {len(segments)} segment(s)")

        for i, seg in enumerate(segments):
            print(f"\n  Segment {i+1}:")
            print(f"    Label: {seg.get('label', 'N/A')}")

            # Display pixel coordinates (descaled from normalized [0-1000])
            box_pixels = seg.get('box_2d_pixels', [])
            if box_pixels and len(box_pixels) == 4:
                x_min, y_min, x_max, y_max = box_pixels
                width = x_max - x_min
                height = y_max - y_min
                print(f"    Box (pixels): x={x_min}, y={y_min}, w={width}, h={height}")
                print(f"    Coordinates: ({x_min}, {y_min}) to ({x_max}, {y_max})")

            # Also show normalized coordinates for reference
            box_norm = seg.get('box_2d_normalized', [])
            if box_norm and len(box_norm) == 4:
                print(f"    Box (normalized [0-1000]): [y0={box_norm[0]}, x0={box_norm[1]}, y1={box_norm[2]}, x1={box_norm[3]}]")

            if 'mask' in seg:
                print(f"    Mask: Present ({type(seg['mask']).__name__})")

        # Save to JSON if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n  Saved to: {args.output}")
    else:
        print(f"\nFAILED: {result.get('error', 'Unknown error')}")
        print(f"\nRaw response:\n{result['raw_response']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
