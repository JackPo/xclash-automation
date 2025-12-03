"""
OCR Client - Drop-in replacement for QwenOCR that talks to the OCR server.

Usage:
    from utils.ocr_client import OCRClient

    ocr = OCRClient()  # Connects to server at localhost:5123
    text = ocr.extract_text(image)  # numpy array or PIL Image
    number = ocr.extract_number(image, region=(x, y, w, h))

If server is not running, falls back to loading Qwen locally (slow).

Start the server with:
    python services/ocr_server.py
"""

import io
import json
import urllib.request
import urllib.error
from typing import Tuple

import numpy as np
from PIL import Image

# Server config
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5123
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Connection timeout (must be long enough for 4-bit quantized model on GTX 1080)
TIMEOUT = 120


class OCRClient:
    """OCR client that talks to the OCR server."""

    _server_checked = False
    _server_available = False

    def __init__(self):
        """Initialize OCR client. Server must be running."""
        pass

    @classmethod
    def check_server(cls) -> bool:
        """Check if server is available. Returns True if server is up."""
        try:
            req = urllib.request.Request(f"{SERVER_URL}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                cls._server_available = data.get("status") == "ok"
                cls._server_checked = True
                return cls._server_available
        except:
            cls._server_available = False
            cls._server_checked = True
            return False

    @classmethod
    def require_server(cls):
        """Require server to be running. Raises RuntimeError if not."""
        if not cls.check_server():
            raise RuntimeError(
                "OCR server is not running!\n"
                "Start it with: python services/ocr_server.py"
            )

    def _ensure_server(self):
        """Ensure server is available, raise if not."""
        # Always recheck if not available (server might have started)
        if not OCRClient._server_checked or not OCRClient._server_available:
            OCRClient.check_server()
        if not OCRClient._server_available:
            raise RuntimeError(
                "OCR server is not running!\n"
                "Start it with: python services/ocr_server.py"
            )

    def _image_to_bytes(self, image, region=None) -> bytes:
        """Convert image to PNG bytes."""
        # Convert numpy to PIL
        if isinstance(image, np.ndarray):
            if len(image.shape) == 3 and image.shape[2] == 3:
                # BGR to RGB
                image = Image.fromarray(image[:, :, ::-1])
            else:
                image = Image.fromarray(image)

        # Crop if region specified
        if region is not None:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))

        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _post_multipart(self, endpoint: str, image_bytes: bytes, fields: dict = None) -> dict:
        """Post multipart form data to server."""
        boundary = b"----OCRClientBoundary"

        # Build body
        body = b""

        # Add image
        body += b"--" + boundary + b"\r\n"
        body += b'Content-Disposition: form-data; name="image"; filename="image.png"\r\n'
        body += b"Content-Type: image/png\r\n\r\n"
        body += image_bytes + b"\r\n"

        # Add other fields
        if fields:
            for name, value in fields.items():
                if value is not None:
                    body += b"--" + boundary + b"\r\n"
                    body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                    if isinstance(value, (list, tuple, dict)):
                        body += json.dumps(value).encode() + b"\r\n"
                    else:
                        body += str(value).encode() + b"\r\n"

        body += b"--" + boundary + b"--\r\n"

        # Send request
        req = urllib.request.Request(
            f"{SERVER_URL}{endpoint}",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary.decode()}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())

    def extract_text(self, image, region: Tuple[int, int, int, int] = None,
                     prompt: str = None) -> str:
        """
        Extract text from image.

        Args:
            image: numpy array (BGR) or PIL Image
            region: Optional (x, y, w, h) to crop before OCR
            prompt: Custom prompt for extraction

        Returns:
            str: Extracted text
        """
        self._ensure_server()
        image_bytes = self._image_to_bytes(image, region)
        fields = {"prompt": prompt} if prompt else {}
        result = self._post_multipart("/ocr", image_bytes, fields)
        return result.get("text", "")

    def extract_number(self, image, region: Tuple[int, int, int, int] = None) -> int | None:
        """
        Extract number from image.

        Args:
            image: numpy array or PIL Image
            region: Optional (x, y, w, h) to crop

        Returns:
            int or None if no number found
        """
        self._ensure_server()
        image_bytes = self._image_to_bytes(image, region)
        result = self._post_multipart("/ocr/number", image_bytes)
        return result.get("number")


# Convenience functions (drop-in replacement for qwen_ocr functions)
_client = None


def get_ocr_client() -> OCRClient:
    """Get or create shared OCR client."""
    global _client
    if _client is None:
        _client = OCRClient()
    return _client


def ocr_extract_text(image, region=None, prompt=None) -> str:
    """Extract text from image using OCR server."""
    return get_ocr_client().extract_text(image, region, prompt)


def ocr_extract_number(image, region=None) -> int | None:
    """Extract number from image using OCR server."""
    return get_ocr_client().extract_number(image, region)


# For backwards compatibility with QwenOCR class
class QwenOCR(OCRClient):
    """Alias for OCRClient for backwards compatibility."""
    pass


if __name__ == "__main__":
    import sys
    import cv2

    # Test the client
    print("Testing OCR Client...")

    client = OCRClient()

    if OCRClient.check_server():
        print("Server is running!")
    else:
        print("Server not running!")
        sys.exit(1)

    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        image = cv2.imread(image_path)

        if image is None:
            print(f"Failed to load: {image_path}")
            sys.exit(1)

        region = None
        if len(sys.argv) >= 6:
            region = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
            print(f"Region: {region}")

        print("\n--- Text extraction ---")
        text = client.extract_text(image, region)
        print(f"Text: {text}")

        print("\n--- Number extraction ---")
        number = client.extract_number(image, region)
        print(f"Number: {number}")
