"""
OCR Server - Keeps Qwen model loaded in memory and serves OCR requests via HTTP.

Start the server:
    python services/ocr_server.py

The server listens on port 5123 by default.

Endpoints:
    POST /ocr - Extract text from image
        Body: multipart/form-data with 'image' file and optional 'prompt', 'region' fields
        Returns: {"text": "extracted text"}

    POST /ocr/number - Extract number from image
        Body: multipart/form-data with 'image' file and optional 'region' field
        Returns: {"number": 123} or {"number": null}

    GET /health - Health check
        Returns: {"status": "ok", "model_loaded": true}
"""

import io
import json
import base64
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
import traceback

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from PIL import Image

# Server config
HOST = "127.0.0.1"
PORT = 5123
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_IN_FLIGHT_REQUESTS = 4

# Common Windows socket disconnect errors
_CLIENT_DISCONNECT_WINERRORS = {10053, 10054}

# Global model state
model = None
processor = None
model_lock = threading.Lock()
request_slots = threading.BoundedSemaphore(MAX_IN_FLIGHT_REQUESTS)


def load_model():
    """Load Qwen model on GPU."""
    global model, processor

    MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
    print(f"Loading {MODEL_ID} on GPU...")

    # 4-bit quantization for GTX 1080 (Pascal)
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float32,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        device_map="cuda",
    )

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    print("Model loaded successfully!")


def extract_text(image: Image.Image, prompt: str = None) -> str:
    """Extract text from image using Qwen."""
    global model, processor

    if prompt is None:
        prompt = "Read the text in this image. Return only the text, nothing else."

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    inputs = processor(
        text=[text],
        images=[image],
        padding=True,
        return_tensors="pt",
    ).to("cuda")

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
        )

    generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
    result = processor.batch_decode(
        generated_ids, skip_special_tokens=True
    )[0]

    # Clean up GPU memory after each inference to prevent gradual memory accumulation
    del inputs, output_ids, generated_ids
    torch.cuda.empty_cache()

    return result.strip()


def extract_number(image: Image.Image) -> int | None:
    """Extract number from image."""
    text = extract_text(
        image,
        prompt="Read the number in this image. Return only the digits, nothing else."
    )
    digits = ''.join(c for c in text if c.isdigit())
    return int(digits) if digits else None


def _is_client_disconnect_error(error: Exception) -> bool:
    """Return True when client closed connection before response write completed."""
    if isinstance(error, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True

    winerror = getattr(error, "winerror", None)
    return isinstance(winerror, int) and winerror in _CLIENT_DISCONNECT_WINERRORS


def _parse_region(region_raw, image_size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """Parse region payload as (left, upper, right, lower) crop box."""
    if region_raw is None:
        return None

    region = region_raw
    if isinstance(region_raw, str):
        region = json.loads(region_raw)

    if not isinstance(region, (list, tuple)) or len(region) != 4:
        raise ValueError("region must be [x, y, width, height]")

    try:
        x, y, width, height = [int(v) for v in region]
    except (TypeError, ValueError) as e:
        raise ValueError("region values must be integers") from e

    if width <= 0 or height <= 0:
        raise ValueError("region width and height must be > 0")
    if x < 0 or y < 0:
        raise ValueError("region x and y must be >= 0")

    image_w, image_h = image_size
    left = min(max(0, x), image_w)
    top = min(max(0, y), image_h)
    right = min(max(left, x + width), image_w)
    bottom = min(max(top, y + height), image_h)

    if left >= right or top >= bottom:
        raise ValueError("region is outside image bounds")

    return (left, top, right, bottom)


class OCRHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OCR requests."""

    def log_message(self, format, *args):
        """Custom logging."""
        message = format % args
        print(f"[OCR] {message}")

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def parse_multipart(self):
        """Parse multipart/form-data request."""
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length <= 0:
            return {}
        if content_length > MAX_REQUEST_BYTES:
            raise ValueError(f"Request too large ({content_length} bytes > {MAX_REQUEST_BYTES} bytes)")

        if "multipart/form-data" in content_type:
            # Extract boundary (handles optional quoted boundary and trailing params)
            if "boundary=" not in content_type:
                raise ValueError("multipart/form-data missing boundary")
            boundary = content_type.split("boundary=", 1)[1].split(";", 1)[0].strip().strip('"').encode()
            if not boundary:
                raise ValueError("multipart/form-data boundary is empty")

            body = self.rfile.read(content_length)

            parts = body.split(b"--" + boundary)
            result = {}

            for part in parts:
                if b"Content-Disposition" not in part:
                    continue

                # Parse headers and content
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue

                headers = part[:header_end].decode(errors="ignore")
                content = part[header_end + 4:]

                # Remove trailing \r\n--
                if content.endswith(b"\r\n"):
                    content = content[:-2]
                if content.endswith(b"--"):
                    content = content[:-2]
                if content.endswith(b"\r\n"):
                    content = content[:-2]

                # Extract field name
                if 'name="' in headers:
                    name = headers.split('name="')[1].split('"')[0]

                    if 'filename="' in headers:
                        # File field
                        result[name] = content
                    else:
                        # Text field
                        result[name] = content.decode(errors="ignore")

            return result

        elif "application/json" in content_type:
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON body: {e.msg}") from e

            # Handle base64 image
            if "image_base64" in data:
                try:
                    data["image"] = base64.b64decode(data["image_base64"], validate=True)
                except (ValueError, TypeError) as e:
                    raise ValueError("Invalid image_base64 payload") from e

            return data

        return {}

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_json({
                "status": "ok",
                "model_loaded": model is not None
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path not in ("/ocr", "/ocr/number"):
            self.send_json({"error": "Not found"}, 404)
            return

        acquired = request_slots.acquire(blocking=False)
        if not acquired:
            self.send_json({"error": "Server busy, retry shortly"}, 503)
            return

        try:
            data = self.parse_multipart()

            if self.path == "/ocr":
                self._handle_ocr(data)
            elif self.path == "/ocr/number":
                self._handle_ocr_number(data)
            else:
                self.send_json({"error": "Not found"}, 404)

        except Exception as e:
            if _is_client_disconnect_error(e):
                print(f"[OCR] Client disconnected during {self.path}: {e}")
                return

            if isinstance(e, ValueError):
                print(f"[OCR] Bad request on {self.path}: {e}")
                self.send_json({"error": str(e)}, 400)
                return

            print(f"[OCR] ERROR handling {self.path}: {e}")
            traceback.print_exc()
            try:
                self.send_json({"error": str(e)}, 500)
            except Exception as response_error:
                if _is_client_disconnect_error(response_error):
                    print(f"[OCR] Client disconnected before error response on {self.path}")
                else:
                    raise
        finally:
            request_slots.release()

    def _handle_ocr(self, data):
        """Handle /ocr endpoint."""
        if "image" not in data:
            self.send_json({"error": "No image provided"}, 400)
            return

        image_bytes = data["image"]
        try:
            with Image.open(io.BytesIO(image_bytes)) as pil_image:
                image = pil_image.convert("RGB")
        except Exception as e:
            raise ValueError("Invalid image data") from e

        try:
            # Apply region crop if specified
            crop_box = _parse_region(data.get("region"), image.size)
            if crop_box:
                image = image.crop(crop_box)

            # Get prompt
            prompt = data.get("prompt")

            # Extract text (thread-safe)
            with model_lock:
                text = extract_text(image, prompt)

            self.send_json({"text": text})
        finally:
            image.close()  # Prevent memory leak

    def _handle_ocr_number(self, data):
        """Handle /ocr/number endpoint."""
        if "image" not in data:
            self.send_json({"error": "No image provided"}, 400)
            return

        image_bytes = data["image"]
        try:
            with Image.open(io.BytesIO(image_bytes)) as pil_image:
                image = pil_image.convert("RGB")
        except Exception as e:
            raise ValueError("Invalid image data") from e

        try:
            # Apply region crop if specified
            crop_box = _parse_region(data.get("region"), image.size)
            if crop_box:
                image = image.crop(crop_box)

            # Extract number (thread-safe)
            with model_lock:
                number = extract_number(image)

            self.send_json({"number": number})
        finally:
            image.close()  # Prevent memory leak


def main():
    """Start the OCR server."""
    print("=" * 60)
    print("OCR Server")
    print("=" * 60)

    # Load model
    load_model()

    # Start server
    server = ThreadingHTTPServer((HOST, PORT), OCRHandler)
    server.daemon_threads = True
    print(f"\nServer listening on http://{HOST}:{PORT}")
    print("Endpoints:")
    print("  POST /ocr        - Extract text from image")
    print("  POST /ocr/number - Extract number from image")
    print("  GET  /health     - Health check")
    print("\nPress Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
