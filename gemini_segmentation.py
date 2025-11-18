#!/usr/bin/env python3
"""
Gemini-based conversational image segmentation for extracting UI elements.
Uses Gemini 2.5 Flash for accurate bounding box detection.
"""
import os
import sys
from pathlib import Path
from PIL import Image
import google.generativeai as genai


class GeminiSegmenter:
    """
    Use Gemini 2.5 Flash for conversational image segmentation.
    Gemini excels at spatial reasoning and bounding box detection.
    """

    def __init__(self, api_key=None):
        """
        Initialize Gemini client.

        Args:
            api_key: Google AI API key (or set GOOGLE_API_KEY environment variable)
        """
        if api_key is None:
            api_key = os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found. Set environment variable or pass api_key parameter.")

        genai.configure(api_key=api_key)

        # Use Gemini 2.5 Flash for best spatial reasoning
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def extract_element(self, image_path, element_description, output_path=None):
        """
        Extract a UI element from an image using conversational segmentation.

        Args:
            image_path: Path to input image
            element_description: Natural language description of what to extract
                               (e.g., "the white handshake icon on the Union button")
            output_path: Optional path to save extracted element

        Returns:
            dict with keys:
                - bbox: (x, y, width, height) bounding box coordinates
                - cropped_image: PIL Image of the extracted element
                - confidence: confidence score if available
                - reasoning: Gemini's explanation of the detection
        """
        # Load image
        img = Image.open(image_path)

        # Craft prompt for bounding box detection
        prompt = f"""
You are an expert at image segmentation and spatial reasoning.

Task: Locate and provide the bounding box for the following UI element in this screenshot:
"{element_description}"

Instructions:
1. Carefully examine the entire image
2. Identify the exact location of the requested element
3. Provide a tight bounding box around JUST that element
4. Return the coordinates in JSON format

Return ONLY a JSON object with this exact structure:
{{
    "element_found": true/false,
    "bbox": {{
        "x": <left pixel coordinate>,
        "y": <top pixel coordinate>,
        "width": <width in pixels>,
        "height": <height in pixels>
    }},
    "confidence": <0.0 to 1.0>,
    "reasoning": "<brief explanation of how you found it>",
    "visual_description": "<what the element looks like>"
}}

Be precise with coordinates. The bounding box should tightly fit the element.
"""

        # Generate response with image
        response = self.model.generate_content([prompt, img])

        # Parse response
        result = self._parse_response(response.text, img)

        # Crop if we got valid bbox
        if result.get("bbox"):
            bbox = result["bbox"]
            cropped = img.crop((
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["width"],
                bbox["y"] + bbox["height"]
            ))
            result["cropped_image"] = cropped

            # Save if output path provided
            if output_path:
                cropped.save(output_path)
                result["output_path"] = output_path

        return result

    def _parse_response(self, response_text, img):
        """Parse Gemini response to extract bounding box."""
        import json
        import re

        # Try to extract JSON from response
        # Gemini might wrap it in markdown code blocks
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return {
                    "element_found": False,
                    "error": "Could not parse JSON from response",
                    "raw_response": response_text
                }

        try:
            data = json.loads(json_str)

            # Validate bbox is within image bounds
            if data.get("bbox"):
                bbox = data["bbox"]
                img_width, img_height = img.size

                # Clamp coordinates
                bbox["x"] = max(0, min(bbox["x"], img_width))
                bbox["y"] = max(0, min(bbox["y"], img_height))
                bbox["width"] = min(bbox["width"], img_width - bbox["x"])
                bbox["height"] = min(bbox["height"], img_height - bbox["y"])

            return data
        except json.JSONDecodeError as e:
            return {
                "element_found": False,
                "error": f"JSON decode error: {e}",
                "raw_response": response_text
            }

    def iterative_refinement(self, image_path, element_description, max_iterations=3):
        """
        Iteratively refine extraction with conversational feedback.

        Args:
            image_path: Path to input image
            element_description: Description of element to extract
            max_iterations: Maximum refinement attempts

        Returns:
            Final extraction result with best bounding box
        """
        # Initial extraction
        result = self.extract_element(image_path, element_description)

        if not result.get("element_found"):
            return result

        # TODO: Implement conversational refinement
        # - Show cropped result back to Gemini
        # - Ask if it's correct
        # - If not, ask for refined coordinates
        # - Iterate until satisfied or max_iterations reached

        return result


def main():
    """CLI for Gemini segmentation."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract UI elements using Gemini 2.5 Flash")
    parser.add_argument("image", help="Input image path")
    parser.add_argument("description", help="Natural language description of element to extract")
    parser.add_argument("-o", "--output", help="Output path for extracted element")
    parser.add_argument("--api-key", help="Google AI API key (or set GOOGLE_API_KEY env var)")

    args = parser.parse_args()

    # Initialize segmenter
    segmenter = GeminiSegmenter(api_key=args.api_key)

    # Extract element
    print(f"Extracting: '{args.description}' from {args.image}")
    result = segmenter.extract_element(args.image, args.description, args.output)

    # Display results
    if result.get("element_found"):
        bbox = result["bbox"]
        print(f"\nSUCCESS - Element found!")
        print(f"  Bounding box: x={bbox['x']}, y={bbox['y']}, w={bbox['width']}, h={bbox['height']}")
        print(f"  Confidence: {result.get('confidence', 'N/A')}")
        print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
        print(f"  Visual: {result.get('visual_description', 'N/A')}")

        if args.output:
            print(f"\n  Saved to: {args.output}")
    else:
        print(f"\nFAILED - Element not found")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        if result.get("raw_response"):
            print(f"\n  Raw response:\n{result['raw_response']}")


if __name__ == "__main__":
    main()
