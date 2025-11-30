"""
Qwen2.5-VL-3B-Instruct OCR - GPU-accelerated vision model for text extraction.

Usage:
    from utils.qwen_ocr import QwenOCR

    ocr = QwenOCR()  # Loads model on first use
    text = ocr.extract_text(image)  # numpy array or PIL Image

    # Or extract from specific region
    text = ocr.extract_text(image, region=(x, y, w, h))
"""
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from PIL import Image
import numpy as np


class QwenOCR:
    """Qwen2.5-VL-3B for OCR tasks."""

    MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"

    _instance = None
    _model = None
    _processor = None

    def __new__(cls):
        """Singleton pattern - only load model once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize model on GPU."""
        if QwenOCR._model is None:
            print(f"Loading {self.MODEL_ID} on GPU...")

            # Use 4-bit quantization with float32 compute for GTX 1080 (Pascal)
            # Pascal GPUs are crippled for float16, must use float32 for compute
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float32,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )

            QwenOCR._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.MODEL_ID,
                quantization_config=quantization_config,
                device_map="cuda",
            )

            QwenOCR._processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            print("Qwen2.5-VL loaded successfully!")

    @property
    def model(self):
        return QwenOCR._model

    @property
    def processor(self):
        return QwenOCR._processor

    def extract_text(self, image, region=None, prompt="Read the text in this image. Return only the text, nothing else."):
        """
        Extract text from image using Qwen2.5-VL.

        Args:
            image: numpy array (BGR or RGB) or PIL Image
            region: Optional (x, y, w, h) to crop before OCR
            prompt: Custom prompt for extraction

        Returns:
            str: Extracted text
        """
        # Convert to PIL if needed
        if isinstance(image, np.ndarray):
            # Assume BGR from OpenCV, convert to RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = Image.fromarray(image[:, :, ::-1])
            else:
                image = Image.fromarray(image)

        # Crop region if specified
        if region is not None:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))

        # Prepare message
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        # Process
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        ).to("cuda")

        # Generate
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
            )

        # Decode - only get the new tokens
        generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
        result = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        return result.strip()

    def extract_number(self, image, region=None):
        """
        Extract a number from image.

        Args:
            image: numpy array or PIL Image
            region: Optional (x, y, w, h) to crop

        Returns:
            int or None if no number found
        """
        text = self.extract_text(
            image,
            region=region,
            prompt="Read the number in this image. Return only the digits, nothing else."
        )

        # Extract digits
        digits = ''.join(c for c in text if c.isdigit())
        return int(digits) if digits else None


# Convenience function
_ocr_instance = None

def qwen_ocr(image, region=None, prompt=None):
    """
    Quick OCR using Qwen2.5-VL.

    Args:
        image: numpy array or PIL Image
        region: Optional (x, y, w, h)
        prompt: Optional custom prompt

    Returns:
        str: Extracted text
    """
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = QwenOCR()

    if prompt:
        return _ocr_instance.extract_text(image, region, prompt)
    return _ocr_instance.extract_text(image, region)


def qwen_extract_number(image, region=None):
    """
    Quick number extraction using Qwen2.5-VL.

    Args:
        image: numpy array or PIL Image
        region: Optional (x, y, w, h)

    Returns:
        int or None
    """
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = QwenOCR()

    return _ocr_instance.extract_number(image, region)


if __name__ == "__main__":
    import sys
    import cv2

    if len(sys.argv) < 2:
        print("Usage: python qwen_ocr.py <image_path> [x y w h]")
        sys.exit(1)

    image_path = sys.argv[1]
    image = cv2.imread(image_path)

    if image is None:
        print(f"Failed to load: {image_path}")
        sys.exit(1)

    region = None
    if len(sys.argv) >= 6:
        region = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
        print(f"Region: {region}")

    ocr = QwenOCR()

    print("\n--- Text extraction ---")
    text = ocr.extract_text(image, region)
    print(f"Text: {text}")

    print("\n--- Number extraction ---")
    number = ocr.extract_number(image, region)
    print(f"Number: {number}")
