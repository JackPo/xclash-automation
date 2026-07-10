"""
Windows Screenshot Helper - Fast BlueStacks window capture

Captures BlueStacks window using PrintWindow API, removes borders,
and scales to 4K resolution for compatibility with existing template matching.

Performance: ~50ms vs ~2700ms for ADB screencap
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import win32gui
import win32ui
import ctypes
from ctypes import windll
from PIL import Image
import numpy as np
import numpy.typing as npt
import cv2

logger = logging.getLogger(__name__)


class WindowsScreenshotHelper:
    """Fast screenshot capture for BlueStacks using Windows API."""

    # BlueStacks window border sizes (empirically determined)
    TOP_BORDER = 30  # pixels
    RIGHT_BORDER = 30  # pixels
    LEFT_BORDER = 0
    BOTTOM_BORDER = 0

    # Target resolution for template matching
    TARGET_WIDTH = 3840  # 4K width
    TARGET_HEIGHT = 2160  # 4K height

    # Target window size for consistent scaling
    TARGET_WINDOW_WIDTH = 1822
    TARGET_WINDOW_HEIGHT = 1040

    # Class-level lock: daemon loop and flow threads each hold their own
    # helper instance, but all capture the same HWND - concurrent GDI
    # calls (PrintWindow/DC handling) crash, so serialize across instances.
    _capture_lock = threading.Lock()

    # Corrupt-frame guard: PrintWindow intermittently returns a frame with a
    # wide near-black band across the top while the rest renders fine, which
    # silently breaks fixed-region template detection (rally panel, tavern
    # tabs, harvest bubbles). Detect that signature - a large dark band in an
    # otherwise BRIGHT frame - and re-capture. The brightness gate ensures a
    # genuinely dark screen (loading/night) is NOT treated as corrupt.
    CORRUPT_BRIGHT_MIN = 60       # frame mean below this = legitimately dark, skip check
    CORRUPT_DARK_MAX = 8          # pixel value <= this = PURE-black "unwritten" memory (game
                                  # sub-menus use dark grays ~15-50, not <=8, so they're excluded)
    CORRUPT_BLOB_MIN_FRAC = 0.20  # largest CONTIGUOUS pure-black blob must cover >=20% of the
                                  # frame to count as the PrintWindow black-band artifact. Was
                                  # 0.3% - absurdly sensitive: any game sub-menu with a dark panel
                                  # / black inset / icon got FALSELY flagged corrupt -> stale frame
                                  # returned + log spam. A real black band is a huge strip, not 0.3%.
    MAX_CORRUPT_RETRIES = 2       # extra re-captures when a corrupt frame is seen
    CORRUPT_RETRY_DELAY = 0.12    # seconds between corrupt-frame re-captures

    def __init__(self, window_title: str = "BlueStacks App Player") -> None:
        """Initialize the screenshot helper.

        Args:
            window_title: Title of the BlueStacks window to capture
        """
        self.window_title = window_title
        self.hwnd: int | None = None
        self._find_window()

    def _find_window(self) -> None:
        """Find the BlueStacks window handle."""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if not self.hwnd:
            raise RuntimeError(f"Could not find window: {self.window_title}")

    def ensure_window_size(self) -> None:
        """Resize BlueStacks window to target size for consistent scaling."""
        import win32con
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        if (right - left) != self.TARGET_WINDOW_WIDTH or (bottom - top) != self.TARGET_WINDOW_HEIGHT:
            win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOP, left, top,
                                  self.TARGET_WINDOW_WIDTH, self.TARGET_WINDOW_HEIGHT,
                                  win32con.SWP_NOZORDER)

    def capture_window(self, max_retries: int = 3) -> Image.Image:
        """Capture window content using PrintWindow API.

        Args:
            max_retries: Number of retry attempts if PrintWindow fails

        Returns:
            PIL.Image: Raw captured window content (includes borders)
        """
        import time

        for attempt in range(max_retries):
            try:
                # Re-find window handle in case it changed
                if attempt > 0:
                    self._find_window()
                    time.sleep(0.1)

                # Get window dimensions
                left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
                width = right - left
                height = bottom - top

                # Create device contexts
                hwnd_dc = win32gui.GetWindowDC(self.hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()

                # Create bitmap
                save_bitmap = win32ui.CreateBitmap()
                save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(save_bitmap)

                # Print window to bitmap using ctypes
                PW_RENDERFULLCONTENT = 0x00000002
                result = windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

                if result == 0:
                    # Cleanup before retry
                    win32gui.DeleteObject(save_bitmap.GetHandle())
                    save_dc.DeleteDC()
                    mfc_dc.DeleteDC()
                    win32gui.ReleaseDC(self.hwnd, hwnd_dc)
                    raise RuntimeError("PrintWindow returned 0")

                # Convert to PIL Image
                bmpinfo = save_bitmap.GetInfo()
                bmpstr = save_bitmap.GetBitmapBits(True)
                img = Image.frombuffer('RGB',
                                      (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                      bmpstr, 'raw', 'BGRX', 0, 1)

                # Cleanup
                win32gui.DeleteObject(save_bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwnd_dc)

                return img

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.2)  # Brief delay before retry
                    continue
                raise RuntimeError(f"PrintWindow failed after {max_retries} attempts: {e}")
        # This should never be reached due to the raise in the loop, but mypy needs it
        raise RuntimeError(f"PrintWindow failed after {max_retries} attempts")

    def remove_borders(self, img: Image.Image) -> Image.Image:
        """Remove BlueStacks window borders from captured image.

        Args:
            img: PIL.Image with borders

        Returns:
            PIL.Image: Cropped image without borders
        """
        width, height = img.size
        return img.crop((
            self.LEFT_BORDER,
            self.TOP_BORDER,
            width - self.RIGHT_BORDER,
            height - self.BOTTOM_BORDER
        ))

    def scale_to_4k(self, img: Image.Image) -> npt.NDArray[Any]:
        """Scale image to 4K resolution for template matching.

        Uses cv2 INTER_LINEAR for speed (9ms vs 163ms for PIL LANCZOS).
        Template matching results are functionally identical.

        Args:
            img: PIL.Image to scale

        Returns:
            np.ndarray: RGB image scaled to 3840x2160
        """
        # Convert PIL to numpy and use cv2 for fast scaling
        arr = np.array(img)
        scaled: npt.NDArray[Any] = cv2.resize(arr, (self.TARGET_WIDTH, self.TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)
        return scaled

    def _capture_once(self) -> npt.NDArray[Any]:
        """Perform a single capture and return a 4K BGR numpy array.

        Holds the class capture lock only for the GDI section (concurrent
        PrintWindow/DC access on the shared HWND crashes); border removal,
        scaling and color conversion run outside the lock.
        """
        with WindowsScreenshotHelper._capture_lock:
            # Re-find window handle in case it became stale
            self._find_window()

            # Ensure consistent window size before capture
            self.ensure_window_size()

            # Capture raw window
            raw_img = self.capture_window()

        # Remove borders
        cropped_img = self.remove_borders(raw_img)

        # Scale to 4K (returns numpy RGB array)
        scaled_rgb = self.scale_to_4k(cropped_img)

        # Convert RGB to BGR for cv2/template matching
        img_bgr: npt.NDArray[Any] = cv2.cvtColor(scaled_rgb, cv2.COLOR_RGB2BGR)

        return img_bgr

    def _frame_looks_corrupt(self, img_bgr: npt.NDArray[Any]) -> bool:
        """True if the frame shows the PrintWindow partial-capture artifact: a
        large CONTIGUOUS near-black region (the "unwritten" band/rectangle) in
        an otherwise bright frame.

        Cheap (~3ms): operates on a downscaled grayscale. The brightness gate
        returns False for genuinely dark screens (loading/night) so the capture
        loop never spins on a legitimate dark frame. Requiring contiguity (a
        connected blob, not a total dark-pixel count) avoids false positives
        from the game's scattered black art outlines.
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (256, 144), interpolation=cv2.INTER_AREA)

        if float(small.mean()) < self.CORRUPT_BRIGHT_MIN:
            return False  # legitimately dark screen, not a capture artifact

        mask = (small <= self.CORRUPT_DARK_MAX).astype(np.uint8)
        num, _labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        if num <= 1:
            return False  # no near-black pixels at all

        # stats[0] is the background label; take the largest foreground blob.
        largest = int(stats[1:, cv2.CC_STAT_AREA].max())
        frac = largest / float(small.shape[0] * small.shape[1])
        return frac >= self.CORRUPT_BLOB_MIN_FRAC

    def get_screenshot_cv2(self) -> npt.NDArray[Any]:
        """Get a 4K screenshot as cv2 numpy array (compatible with template matching).

        This is the main method to use for template matching pipelines.

        Re-captures up to MAX_CORRUPT_RETRIES times if the frame shows the
        PrintWindow black-band artifact; always returns a frame (never raises
        or hangs on persistent corruption).

        Returns:
            np.ndarray: BGR image at 4K resolution (3840x2160x3)
        """
        last: npt.NDArray[Any] | None = None
        for attempt in range(self.MAX_CORRUPT_RETRIES + 1):
            last = self._capture_once()
            if not self._frame_looks_corrupt(last):
                return last
            logger.warning(
                "Corrupt capture frame detected (black band), re-capturing "
                "(attempt %d/%d)", attempt + 1, self.MAX_CORRUPT_RETRIES
            )
            time.sleep(self.CORRUPT_RETRY_DELAY)

        logger.warning(
            "Capture still corrupt after %d retries; returning last frame",
            self.MAX_CORRUPT_RETRIES
        )
        assert last is not None  # loop runs at least once
        return last

    def save_screenshot(self, output_path: str) -> str:
        """Capture and save a 4K screenshot.

        Args:
            output_path: Path to save the screenshot

        Returns:
            str: The output path where the screenshot was saved
        """
        img_bgr = self.get_screenshot_cv2()
        cv2.imwrite(output_path, img_bgr)
        return output_path


if __name__ == "__main__":
    import time

    # Benchmark the screenshot capture
    helper = WindowsScreenshotHelper()

    print("Testing Windows screenshot capture...")
    start = time.time()
    img = helper.get_screenshot_cv2()
    elapsed = time.time() - start

    print(f"Capture time: {elapsed:.3f}s")
    print(f"Image shape: {img.shape}")
    print(f"Expected: (2160, 3840, 3) for 4K")

    # Save test screenshot
    output = "temp_windows_screenshot_test.png"
    helper.save_screenshot(output)
    print(f"Saved test screenshot to: {output}")
