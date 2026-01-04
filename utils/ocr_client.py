from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    import numpy.typing as npt

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5123
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

TIMEOUT = 120

RETRY_COOLDOWN = 300

HEALTH_CHECK_TTL = 30

SERVER_STARTUP_TIMEOUT = 120
SERVER_STARTUP_CHECK_INTERVAL = 2

_OCR_SERVER_SCRIPT = Path(__file__).parent.parent / "services" / "ocr_server.py"

_OCR_SERVER_LOG = Path(__file__).parent.parent / "logs" / "ocr_server.log"

_server_process: subprocess.Popen[bytes] | None = None
_server_log_file: Any = None


def kill_ocr_servers() -> int:
    killed = 0

    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             "commandline like '%ocr_server.py%' and name like '%python%'",
             'get', 'processid'],
            capture_output=True, text=True, timeout=10
        )

        lines = result.stdout.strip().split('\n')
        for line in lines[1:]:
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
        time.sleep(1)

    return killed


def start_ocr_server() -> bool:
    global _server_process, _server_log_file

    if not _OCR_SERVER_SCRIPT.exists():
        print(f"ERROR: OCR server script not found: {_OCR_SERVER_SCRIPT}")
        return False

    kill_ocr_servers()

    print(f"Starting OCR server ({_OCR_SERVER_SCRIPT})...")
    print("  This may take 30-60 seconds to load the model...")

    try:
        _OCR_SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)

        _server_log_file = open(_OCR_SERVER_LOG, 'a', buffering=1)
        print(f"  OCR server output will be logged to: {_OCR_SERVER_LOG}")

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        _server_process = subprocess.Popen(
            [sys.executable, str(_OCR_SERVER_SCRIPT)],
            stdout=_server_log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags
        )

        start_time = time.time()
        while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
            if OCRClient.check_server(force=True):
                print("  OCR server started successfully!")
                return True
            time.sleep(SERVER_STARTUP_CHECK_INTERVAL)

        print(f"  ERROR: Server did not respond within {SERVER_STARTUP_TIMEOUT}s")
        return False

    except Exception as e:
        print(f"  ERROR: Failed to start server: {e}")
        return False


def ensure_ocr_server(auto_start: bool = True) -> bool:
    if OCRClient.check_server():
        return True

    if not auto_start:
        return False

    return start_ocr_server()


class OCRClient:

    _server_checked = False
    _server_available = False
    _last_health_check = 0.0
    _auto_start_attempted = False
    _last_start_attempt = 0.0

    def __init__(self, auto_start: bool = True) -> None:
        self._auto_start = auto_start

    @classmethod
    def check_server(cls, force: bool = False) -> bool:
        now = time.time()
        if not force and cls._server_checked and (now - cls._last_health_check) < HEALTH_CHECK_TTL:
            return cls._server_available
        try:
            req = urllib.request.Request(f"{SERVER_URL}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                cls._server_available = data.get("status") == "ok"
                cls._server_checked = True
                cls._last_health_check = now
                return cls._server_available
        except Exception:
            cls._server_available = False
            cls._server_checked = True
            cls._last_health_check = now
            return False

    @classmethod
    def require_server(cls, auto_start: bool = True) -> None:
        if cls.check_server():
            return

        now = time.time()
        can_retry = not cls._auto_start_attempted or (now - cls._last_start_attempt) >= RETRY_COOLDOWN

        if auto_start and can_retry:
            cls._auto_start_attempted = True
            cls._last_start_attempt = now
            if start_ocr_server():
                return

        raise RuntimeError(
            "OCR server is not running and could not be started!\n"
            "Try manually: python services/ocr_server.py"
        )

    def _ensure_server(self) -> None:
        if OCRClient.check_server():
            return

        now = time.time()
        can_retry = not OCRClient._auto_start_attempted or (now - OCRClient._last_start_attempt) >= RETRY_COOLDOWN

        if self._auto_start and can_retry:
            OCRClient._auto_start_attempted = True
            OCRClient._last_start_attempt = now
            if start_ocr_server():
                return

        raise RuntimeError(
            "OCR server is not running!\n"
            "Start it with: python services/ocr_server.py"
        )

    def _image_to_bytes(
        self,
        image: npt.NDArray[Any] | Image.Image,
        region: tuple[int, int, int, int] | None = None
    ) -> bytes:
        pil_image: Image.Image
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

        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _post_multipart(
        self,
        endpoint: str,
        image_bytes: bytes,
        fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        boundary = b"----OCRClientBoundary"

        body = b""

        body += b"--" + boundary + b"\r\n"
        body += b'Content-Disposition: form-data; name="image"; filename="image.png"\r\n'
        body += b"Content-Type: image/png\r\n\r\n"
        body += image_bytes + b"\r\n"

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

        req = urllib.request.Request(
            f"{SERVER_URL}{endpoint}",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary.decode()}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                result: dict[str, Any] = json.loads(resp.read())
                return result
        except urllib.error.URLError as e:
            return {"error": f"URL error: {e}", "text": None}
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP error {e.code}: {e.reason}", "text": None}
        except Exception as e:
            return {"error": str(e), "text": None}

    def extract_text(
        self,
        image: npt.NDArray[Any] | Image.Image,
        region: tuple[int, int, int, int] | None = None,
        prompt: str | None = None
    ) -> str:
        self._ensure_server()
        image_bytes = self._image_to_bytes(image, region)
        fields: dict[str, Any] = {"prompt": prompt} if prompt else {}
        result = self._post_multipart("/ocr", image_bytes, fields)
        text = result.get("text", "")
        return str(text) if text else ""

    def extract_number(
        self,
        image: npt.NDArray[Any] | Image.Image,
        region: tuple[int, int, int, int] | None = None
    ) -> int | None:
        self._ensure_server()
        image_bytes = self._image_to_bytes(image, region)
        result = self._post_multipart("/ocr/number", image_bytes)
        number = result.get("number")
        if number is None:
            return None
        return int(number)

    def extract_json(
        self,
        image: npt.NDArray[Any] | Image.Image,
        region: tuple[int, int, int, int] | None = None,
        prompt: str | None = None
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
            parsed: dict[str, Any] = json.loads(text)
            return parsed
        except json.JSONDecodeError as e:
            print(f"[OCR-CLIENT] Failed to parse JSON: {e}")
            print(f"[OCR-CLIENT] Raw response: {text!r}")
            return None


_client: OCRClient | None = None


def get_ocr_client() -> OCRClient:
    global _client
    if _client is None:
        _client = OCRClient()
    return _client


def ocr_extract_text(
    image: npt.NDArray[Any] | Image.Image,
    region: tuple[int, int, int, int] | None = None,
    prompt: str | None = None
) -> str:
    return get_ocr_client().extract_text(image, region, prompt)


def ocr_extract_number(
    image: npt.NDArray[Any] | Image.Image,
    region: tuple[int, int, int, int] | None = None
) -> int | None:
    return get_ocr_client().extract_number(image, region)


class QwenOCR(OCRClient):
    pass


if __name__ == "__main__":
    import cv2

    def _main() -> int:
        print("Testing OCR Client...")

        client = OCRClient()

        if not OCRClient.check_server():
            print("Server not running!")
            return 1
        print("Server is running!")

        if len(sys.argv) <= 1:
            return 0

        image_path = sys.argv[1]
        image = cv2.imread(image_path)

        if image is None:
            print(f"Failed to load: {image_path}")  # type: ignore[unreachable]
            return 1

        region: tuple[int, int, int, int] | None = None
        if len(sys.argv) >= 6:
            region = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
            print(f"Region: {region}")

        print("\n--- Text extraction ---")
        text = client.extract_text(image, region)
        print(f"Text: {text}")

        print("\n--- Number extraction ---")
        number = client.extract_number(image, region)
        print(f"Number: {number}")
        return 0

    sys.exit(_main())
