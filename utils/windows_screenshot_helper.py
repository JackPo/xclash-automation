"""
Windows Screenshot Helper - Fast BlueStacks window capture

Captures BlueStacks window using PrintWindow API, removes borders,
and scales to 4K resolution for compatibility with existing template matching.

Performance: ~50ms vs ~2700ms for ADB screencap
"""

import win32gui
import win32ui
import ctypes
from ctypes import windll
from PIL import Image
import numpy as np
import cv2


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

    def __init__(self, window_title="BlueStacks App Player"):
        """Initialize the screenshot helper.

        Args:
            window_title: Title of the BlueStacks window to capture
        """
        self.window_title = window_title
        self.hwnd = None
        self._find_window()

    def _find_window(self):
        """Find the BlueStacks window handle."""
        self.hwnd = win32gui.FindWindow(None, self.window_title)
        if not self.hwnd:
            raise RuntimeError(f"Could not find window: {self.window_title}")

    def capture_window(self, max_retries=3):
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

    def remove_borders(self, img):
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

    def scale_to_4k(self, img):
        """Scale image to 4K resolution for template matching.

        Args:
            img: PIL.Image to scale

        Returns:
            PIL.Image: Scaled to 3840x2160
        """
        return img.resize((self.TARGET_WIDTH, self.TARGET_HEIGHT), Image.LANCZOS)

    def get_screenshot_cv2(self):
        """Get a 4K screenshot as cv2 numpy array (compatible with template matching).

        This is the main method to use for template matching pipelines.

        Returns:
            np.ndarray: BGR image at 4K resolution (3840x2160x3)
        """
        # Capture raw window
        raw_img = self.capture_window()

        # Remove borders
        cropped_img = self.remove_borders(raw_img)

        # Scale to 4K
        scaled_img = self.scale_to_4k(cropped_img)

        # Convert PIL RGB to cv2 BGR
        img_array = np.array(scaled_img)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        return img_bgr

    def save_screenshot(self, output_path):
        """Capture and save a 4K screenshot.

        Args:
            output_path: Path to save the screenshot
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
