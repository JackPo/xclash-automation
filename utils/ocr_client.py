"""
OCR Client - Drop-in replacement for QwenOCR that talks to the OCR server.

Usage:
    from utils.ocr_client import OCRClient

    ocr = OCRClient()  # Connects to server at localhost:5123
    text = ocr.extract_text(image)  # numpy array or PIL Image
    number = ocr.extract_number(image, region=(x, y, w, h))

The client will auto-start the OCR server if not running.

Start the server manually with:
    python services/ocr_server.py
"""

import io
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image

# Server config
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5123
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Connection timeout (must be long enough for 4-bit quantized model on GTX 1080)
TIMEOUT = 120

# Server startup config
SERVER_STARTUP_TIMEOUT = 120  # Wait up to 2 minutes for server to start
SERVER_STARTUP_CHECK_INTERVAL = 2  # Check every 2 seconds

# Path to OCR server script
_OCR_SERVER_SCRIPT = Path(__file__).parent.parent / "services" / "ocr_server.py"

# Path to OCR server log file
_OCR_SERVER_LOG = Path(__file__).parent.parent / "logs" / "ocr_server.log"

# Global server process handle
_server_process = None
_server_log_file = None  # Keep file handle open to prevent closure


def kill_ocr_servers() -> int:
    """
    Kill all existing OCR server processes.

    Returns:
        int: Number of processes killed
    """
    import subprocess

    killed = 0

    # Find all python processes running ocr_server.py
    try:
        # Use wmic to find python processes with ocr_server.py in command line
        result = subprocess.run(
            ['wmic', 'process', 'where',
             "commandline like '%ocr_server.py%' and name like '%python%'",
             'get', 'processid'],
            capture_output=True, text=True, timeout=10
        )

        # Parse PIDs from output (format: "ProcessId\n1234\n5678\n")
        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:  # Skip header
            line = line.strip()
            if line and line.isdigit():
                pid = int(line)
                print(f"  Killing OCR server process (PID {pid})...")
                subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                             capture_output=True, timeout=5)
                killed += 1

    except Exception as e:
        print(f"  Warning: Error finding OCR processes: {e}")

    if killed > 0:
        print(f"  Killed {killed} OCR server process(es)")
        time.sleep(1)  # Wait for processes to die

    return killed


def start_ocr_server() -> bool:
    """
    Start the OCR server in a background process.

    Kills any existing OCR server processes first to prevent accumulation.

    Returns:
        bool: True if server started successfully, False otherwise
    """
    global _server_process, _server_log_file

    if not _OCR_SERVER_SCRIPT.exists():
        print(f"ERROR: OCR server script not found: {_OCR_SERVER_SCRIPT}")
        return False

    # Kill existing OCR servers first to prevent accumulation
    kill_ocr_servers()

    print(f"Starting OCR server ({_OCR_SERVER_SCRIPT})...")
    print("  This may take 30-60 seconds to load the model...")

    try:
        # Ensure logs directory exists
        _OCR_SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)

        # Open log file for OCR server output
        # CRITICAL: Do NOT use subprocess.PIPE - it causes buffer deadlock on Windows!
        # If stdout buffer fills (~64KB) and parent doesn't read, child blocks on print()
        _server_log_file = open(_OCR_SERVER_LOG, 'w')
        print(f"  OCR server output will be logged to: {_OCR_SERVER_LOG}")

        # Start server as background process
        # Use CREATE_NEW_PROCESS_GROUP on Windows to prevent CTRL+C from killing it
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        _server_process = subprocess.Popen(
            [sys.executable, str(_OCR_SERVER_SCRIPT)],
            stdout=_server_log_file,
            stderr=subprocess.STDOUT,
            **kwargs
        )

        # Wait for server to become available
        start_time = time.time()
        while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
            if OCRClient.check_server():
                print("  OCR server started successfully!")
                return True
            time.sleep(SERVER_STARTUP_CHECK_INTERVAL)

        print(f"  ERROR: Server did not respond within {SERVER_STARTUP_TIMEOUT}s")
        return False

    except Exception as e:
        print(f"  ERROR: Failed to start server: {e}")
        return False


def ensure_ocr_server(auto_start: bool = True) -> bool:
    """
    Ensure OCR server is running, optionally starting it if not.

    Args:
        auto_start: If True, start the server if it's not running

    Returns:
        bool: True if server is available (running or started), False otherwise
    """
    if OCRClient.check_server():
        return True

    if not auto_start:
        return False

    return start_ocr_server()


class OCRClient:
    """OCR client that talks to the OCR server."""

    _server_checked = False
    _server_available = False
    _auto_start_attempted = False

    def __init__(self, auto_start: bool = True):
        """
        Initialize OCR client.

        Args:
            auto_start: If True, automatically start the server if not running
        """
        self._auto_start = auto_start

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
    def require_server(cls, auto_start: bool = True):
        """
        Require server to be running.

        Args:
            auto_start: If True, attempt to start the server if not running

        Raises:
            RuntimeError: If server is not running and couldn't be started
        """
        if cls.check_server():
            return

        if auto_start and not cls._auto_start_attempted:
            cls._auto_start_attempted = True
            if start_ocr_server():
                return

        raise RuntimeError(
            "OCR server is not running and could not be started!\n"
            "Try manually: python services/ocr_server.py"
        )

    def _ensure_server(self):
        """Ensure server is available, starting it if needed."""
        # Check if server is up
        if OCRClient.check_server():
            return

        # Try to start if auto_start enabled
        if self._auto_start and not OCRClient._auto_start_attempted:
            OCRClient._auto_start_attempted = True
            if start_ocr_server():
                return

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

    def extract_json(self, image, region: Tuple[int, int, int, int] = None,
                     prompt: str = None) -> dict | None:
        """
        Extract structured JSON data from image.

        Args:
            image: numpy array (BGR) or PIL Image
            region: Optional (x, y, w, h) to crop before OCR
            prompt: Custom prompt for extraction (should request JSON output)

        Returns:
            dict: Parsed JSON object, or None if parsing fails
        """
        import json

        text = self.extract_text(image, region=region, prompt=prompt)

        # Try to extract JSON from response
        # Qwen might wrap JSON in markdown code blocks
        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]  # Remove trailing ```

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[OCR-CLIENT] Failed to parse JSON: {e}")
            print(f"[OCR-CLIENT] Raw response: {text!r}")
            return None


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
