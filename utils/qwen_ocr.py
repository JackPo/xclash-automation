"""
Qwen2.5-VL-3B-Instruct OCR - GPU-accelerated vision model for text extraction.

Usage:
    from utils.qwen_ocr import QwenOCR

    ocr = QwenOCR()  # Loads model on first use
    text = ocr.extract_text(image)  # numpy array or PIL Image

    # Or extract from specific region
    text = ocr.extract_text(image, region=(x, y, w, h))
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import torch
from PIL import Image
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


class QwenOCR:
    """Qwen2.5-VL-3B for OCR tasks."""

    MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"

    _instance: QwenOCR | None = None
    _model: Any = None
    _processor: Any = None

    def __new__(cls) -> QwenOCR:
        """Singleton pattern - only load model once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize model on GPU."""
        if QwenOCR._model is None:
            print(f"Loading {self.MODEL_ID} on GPU...")

            quantization_config = BitsAndBytesConfig(  # type: ignore[no-untyped-call]
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

            QwenOCR._processor = AutoProcessor.from_pretrained(self.MODEL_ID)  # type: ignore[no-untyped-call]
            print("Qwen2.5-VL loaded successfully!")

    @property
    def model(self) -> Any:
        return QwenOCR._model

    @property
    def processor(self) -> Any:
        return QwenOCR._processor

    def extract_text(
        self,
        image: npt.NDArray[Any] | PILImage,
        region: tuple[int, int, int, int] | None = None,
        prompt: str = "Read the text in this image. Return only the text, nothing else.",
    ) -> str:
        pil_image: PILImage
        if isinstance(image, np.ndarray):
            if len(image.shape) == 3 and image.shape[2] == 3:
                pil_image = Image.fromarray(image[:, :, ::-1])
            else:
                pil_image = Image.fromarray(image)
        else:
            pil_image = image

        if region is not None:
            x, y, w, h = region
            pil_image = pil_image.crop((x, y, x + w, y + h))

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text: str = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.processor(
            text=[text],
            images=[pil_image],
            padding=True,
            return_tensors="pt",
        ).to("cuda")

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
            )

        generated_ids = output_ids[:, inputs.input_ids.shape[1] :]
        result: str = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return result.strip()

    def extract_number(
        self,
        image: npt.NDArray[Any] | PILImage,
        region: tuple[int, int, int, int] | None = None,
    ) -> int | None:
        text = self.extract_text(
            image,
            region=region,
            prompt="Read the number in this image. Return only the digits, nothing else.",
        )

        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else None

    def extract_json(
        self,
        image: npt.NDArray[Any] | PILImage,
        region: tuple[int, int, int, int] | None = None,
        prompt: str = "Extract information from this image and return it as JSON.",
    ) -> dict[str, Any] | None:
        text = self.extract_text(image, region=region, prompt=prompt)

        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            result: dict[str, Any] = json.loads(text)
            return result
        except json.JSONDecodeError as e:
            print(f"[QWEN-OCR] Failed to parse JSON: {e}")
            print(f"[QWEN-OCR] Raw response: {text!r}")
            return None


_ocr_instance: QwenOCR | None = None


def qwen_ocr(
    image: npt.NDArray[Any] | PILImage,
    region: tuple[int, int, int, int] | None = None,
    prompt: str | None = None,
) -> str:
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = QwenOCR()

    if prompt:
        return _ocr_instance.extract_text(image, region, prompt)
    return _ocr_instance.extract_text(image, region)


def qwen_extract_number(
    image: npt.NDArray[Any] | PILImage,
    region: tuple[int, int, int, int] | None = None,
) -> int | None:
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
    img: npt.NDArray[Any] | None = cv2.imread(image_path)

    if img is None:
        print(f"Failed to load: {image_path}")
        sys.exit(1)

    rgn: tuple[int, int, int, int] | None = None
    if len(sys.argv) >= 6:
        rgn = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
        print(f"Region: {rgn}")

    ocr = QwenOCR()

    print("\n--- Text extraction ---")
    txt = ocr.extract_text(img, rgn)
    print(f"Text: {txt}")

    print("\n--- Number extraction ---")
    number = ocr.extract_number(img, rgn)
    print(f"Number: {number}")
