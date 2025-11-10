"""
World/Town View Detection Utility

Clean, reusable API for detecting and switching between WORLD and TOWN views
using template matching on the lower-right toggle button.

IMPORTANT: The toggle button shows your DESTINATION (where you can switch TO),
not your current location:
  - When IN World view → button shows "TOWN" (can switch to town)
  - When IN Town view → button shows "WORLD" (can switch to world)

This module handles the inversion automatically, so ViewState.WORLD means
you ARE CURRENTLY in World view (button shows TOWN).

Usage Examples:
    # Simple detection (returns CURRENT view, not button label)
    from view_detection import detect_current_view, ViewState
    state = detect_current_view(adb_controller)
    if state == ViewState.WORLD:
        print("Currently in World view")  # Button shows TOWN

    # Simple switching
    from view_detection import switch_to_view
    success = switch_to_view(adb_controller, ViewState.TOWN)

    # Advanced usage
    from view_detection import ViewDetector, ViewSwitcher
    detector = ViewDetector()
    result = detector.detect_from_adb(adb_controller)
    print(f"Currently in: {result.state}, Confidence: {result.confidence:.2f}")
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path
import time
import numpy as np
import cv2

from button_matcher import ButtonMatcher, TemplateMatch


class ViewState(Enum):
    """Type-safe view state enumeration."""
    WORLD = "WORLD"
    TOWN = "TOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class MinimapViewport:
    """Yellow rectangle position and size in minimap."""
    x: int  # Bounding box top-left X
    y: int  # Bounding box top-left Y
    width: int
    height: int
    area: int
    center_x: int
    center_y: int
    # 4 corner coordinates
    top_left: Tuple[int, int]
    top_right: Tuple[int, int]
    bottom_left: Tuple[int, int]
    bottom_right: Tuple[int, int]


@dataclass
class ViewDetectionResult:
    """
    Structured result from view detection.

    Attributes:
        state: The detected view state (WORLD, TOWN, or UNKNOWN)
        confidence: Match confidence score (0.0-1.0)
        match: Full template match result if detected, None otherwise
        minimap_present: True if zoomed-out button variant detected (indicates minimap visible)
        minimap_viewport: Yellow rectangle in minimap (position/zoom indicator), None if not detected
    """
    state: ViewState
    confidence: float
    match: Optional[TemplateMatch] = None
    minimap_present: bool = False
    minimap_viewport: Optional[MinimapViewport] = None


class ViewDetector:
    """
    World/Town view detector using template matching.

    Wraps ButtonMatcher with a semantic layer and provides clean API
    for detection from frames or ADB screenshots.

    Attributes:
        button_matcher: Underlying ButtonMatcher instance
        threshold: Minimum confidence score for positive detection (default: 0.97)
    """

    def __init__(
        self,
        button_matcher: Optional[ButtonMatcher] = None,
        threshold: float = 0.90
    ):
        """
        Initialize ViewDetector.

        Args:
            button_matcher: ButtonMatcher instance. If None, creates default.
            threshold: Minimum score for positive detection (0.97 recommended)
        """
        if button_matcher is None:
            template_dir = Path(__file__).parent / "templates" / "ground_truth"
            debug_dir = Path(__file__).parent / "templates" / "debug"
            button_matcher = ButtonMatcher(
                template_dir=template_dir,
                debug_dir=debug_dir,
                threshold=0.85  # ButtonMatcher internal threshold
            )

        self.button_matcher = button_matcher
        self.threshold = threshold
        self._last_match = None

    def detect_from_frame(
        self,
        frame: np.ndarray,
        save_debug: bool = False
    ) -> ViewDetectionResult:
        """
        Detect view state from a BGR image frame.

        Args:
            frame: OpenCV BGR image (numpy array)
            save_debug: If True, save debug visualization

        Returns:
            ViewDetectionResult with state, confidence, and match details
        """
        match = self.button_matcher.match(frame, save_debug=save_debug)

        if match is None or match.score < self.threshold:
            return ViewDetectionResult(
                state=ViewState.UNKNOWN,
                confidence=match.score if match else 0.0,
                match=match,
                minimap_present=False,
                minimap_viewport=None
            )

        self._last_match = match

        # Check if this is the zoomed-out button variant (TOWN_ZOOMED)
        # This button ONLY appears when minimap is visible
        minimap_present = (match.template_key == "TOWN_ZOOMED")

        # Detect yellow viewport rectangle in minimap if present
        minimap_viewport = None
        if minimap_present:
            minimap_viewport = self._detect_minimap_viewport(frame)

        return ViewDetectionResult(
            state=ViewState(match.label),
            confidence=match.score,
            match=match,
            minimap_present=minimap_present,
            minimap_viewport=minimap_viewport
        )

    def detect_from_adb(
        self,
        adb_controller,
        temp_path: str = "temp_screenshot.png",
        fallback_fullframe: bool = True
    ) -> ViewDetectionResult:
        """
        Detect view state via ADB screenshot.

        Args:
            adb_controller: ADBController instance
            temp_path: Temporary file path for screenshot
            fallback_fullframe: If True, search full frame if ROI fails

        Returns:
            ViewDetectionResult with state, confidence, and match details
        """
        match = self.button_matcher.match_from_adb(
            adb_controller,
            temp_path=temp_path,
            fallback_fullframe=fallback_fullframe
        )

        if match is None or match.score < self.threshold:
            return ViewDetectionResult(
                state=ViewState.UNKNOWN,
                confidence=match.score if match else 0.0,
                match=match,
                minimap_present=False
            )

        self._last_match = match

        # Check if this is the zoomed-out button variant (TOWN_ZOOMED)
        # This button ONLY appears when minimap is visible
        minimap_present = (match.template_key == "TOWN_ZOOMED")

        return ViewDetectionResult(
            state=ViewState(match.label),
            confidence=match.score,
            match=match,
            minimap_present=minimap_present
        )

    def _detect_minimap_viewport(self, frame: np.ndarray) -> Optional[MinimapViewport]:
        """
        Detect cyan viewport rectangle in minimap.

        This rectangle is THE KEY METRIC for zoom level calibration and adjustment.

        **ZOOM CALIBRATION USE CASE**:
        When adjusting zoom levels, THIS viewport rectangle area percentage is what
        you're looking for. The size of this rectangle directly indicates zoom level:

        - Small rectangle (< 1% of minimap) = Very ZOOMED IN (close view, good for OCR)
        - Medium rectangle (5-25% of minimap) = Medium zoom
        - Large rectangle (> 30% of minimap) = ZOOMED OUT (wide map view)

        **Returns**:
        MinimapViewport with:
        - Position: (x, y) top-left corner in minimap coordinates
        - Size: width × height in pixels
        - Area: Total pixels (compare to 226×226 = 51,076 minimap total)
        - Center: Center point for navigation reference
        - 4 Corners: All corner coordinates for precise boundary detection

        **Color Detection**:
        - Cyan/bright blue rectangle: HSV(22-26, 180-230, 160-240)
        - High saturation and value to filter out map background
        """
        # Extract minimap region
        minimap = frame[MINIMAP_Y:MINIMAP_Y+MINIMAP_H, MINIMAP_X:MINIMAP_X+MINIMAP_W]

        # Convert to HSV for viewport detection
        hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)

        # Viewport rectangle color range (bright cyan)
        # H=22-26, S=180-230, V=160-240
        lower_viewport = np.array([22, 180, 160])
        upper_viewport = np.array([26, 230, 240])

        # Create mask for viewport rectangle
        yellow_mask = cv2.inRange(hsv, lower_viewport, upper_viewport)

        # Find contours
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Get the largest contour (yellow rectangle outline)
        largest = max(contours, key=cv2.contourArea)

        # Get bounding box from contour - this includes the hollow interior
        x, y, w, h = cv2.boundingRect(largest)

        return MinimapViewport(
            x=x,
            y=y,
            width=w,
            height=h,
            area=w * h,
            center_x=x + w // 2,
            center_y=y + h // 2,
            top_left=(x, y),
            top_right=(x + w, y),
            bottom_left=(x, y + h),
            bottom_right=(x + w, y + h)
        )

    @property
    def last_match(self) -> Optional[TemplateMatch]:
        """Get the last successful template match."""
        return self._last_match


class ViewSwitcher:
    """
    Handles switching between WORLD and TOWN views.

    Uses ViewDetector to identify current state and clicks the toggle button
    to switch to the target state.
    """

    def __init__(self, detector: ViewDetector, adb_controller):
        """
        Initialize ViewSwitcher.

        Args:
            detector: ViewDetector instance for state detection
            adb_controller: ADBController for clicking
        """
        self.detector = detector
        self.adb = adb_controller

    def switch_to_view(
        self,
        target_state: ViewState,
        max_attempts: int = 4,
        wait_time: float = 1.2
    ) -> bool:
        """
        Switch to target view state with retries.

        Args:
            target_state: Desired state (ViewState.WORLD or ViewState.TOWN)
            max_attempts: Maximum number of click attempts
            wait_time: Seconds to wait after each click

        Returns:
            True if successfully switched to target state, False otherwise
        """
        if target_state == ViewState.UNKNOWN:
            raise ValueError("Cannot switch to UNKNOWN state")

        for attempt in range(1, max_attempts + 1):
            # Check current state
            result = self.detector.detect_from_adb(self.adb)

            if result.state == target_state:
                print(f"Already in {target_state.value} view")
                return True

            if result.match is None:
                print(f"  [Attempt {attempt}] Button not detected. Retrying...")
                time.sleep(wait_time)
                continue

            # Click to switch
            print(f"  [Attempt {attempt}] Switching from {result.state.value} to {target_state.value}...")
            self._click_toggle(result.match, target_state)
            time.sleep(wait_time)

        print(f"Failed to switch to {target_state.value} after {max_attempts} attempts")
        return False

    def _click_toggle(self, match: TemplateMatch, target_state: ViewState) -> None:
        """
        Click the toggle button to switch states.

        The button is a simple toggle - clicking at x_frac=0.75 (right side)
        toggles between WORLD and TOWN states regardless of current state.

        Args:
            match: Current button match result
            target_state: Desired state to switch to (used for logging only)
        """
        # Get button dimensions
        template_h, template_w = self.detector.button_matcher.template_shape
        x, y = match.top_left

        # Simple toggle: always click at 75% from left (right side)
        # This position toggles between WORLD <-> TOWN
        x_frac = 0.75
        y_frac = 0.5

        target_x = int(x + template_w * x_frac)
        target_y = int(y + template_h * y_frac)

        print(f"    Toggling at ({target_x}, {target_y}) [x_frac={x_frac}, confidence: {match.score:.3f}]")
        self.adb.tap(target_x, target_y)


# ============================================================================
# Convenience Functions - Simple API for Quick Usage
# ============================================================================

_global_detector: Optional[ViewDetector] = None


def _get_detector() -> ViewDetector:
    """Get or create global detector instance."""
    global _global_detector
    if _global_detector is None:
        _global_detector = ViewDetector()
    return _global_detector


def detect_current_view(adb_controller) -> ViewState:
    """
    Detect current view state (simple API).

    Args:
        adb_controller: ADBController instance

    Returns:
        ViewState enum (WORLD, TOWN, or UNKNOWN)

    Example:
        from view_detection import detect_current_view, ViewState

        state = detect_current_view(adb)
        if state == ViewState.WORLD:
            print("In World view")
    """
    detector = _get_detector()
    result = detector.detect_from_adb(adb_controller)
    return result.state


def switch_to_view(
    adb_controller,
    target_state: ViewState,
    max_attempts: int = 4
) -> bool:
    """
    Switch to target view state (simple API).

    Args:
        adb_controller: ADBController instance
        target_state: Desired state (ViewState.WORLD or ViewState.TOWN)
        max_attempts: Maximum number of attempts

    Returns:
        True if successful, False otherwise

    Example:
        from view_detection import switch_to_view, ViewState

        if switch_to_view(adb, ViewState.TOWN):
            print("Successfully switched to Town view")
    """
    detector = _get_detector()
    switcher = ViewSwitcher(detector, adb_controller)
    return switcher.switch_to_view(target_state, max_attempts=max_attempts)


def get_detection_result(adb_controller) -> ViewDetectionResult:
    """
    Get full detection result with confidence and match details (simple API).

    Args:
        adb_controller: ADBController instance

    Returns:
        ViewDetectionResult with state, confidence, and match

    Example:
        from view_detection import get_detection_result

        result = get_detection_result(adb)
        print(f"State: {result.state}, Confidence: {result.confidence:.2f}")
    """
    detector = _get_detector()
    return detector.detect_from_adb(adb_controller)


# ============================================================================
# Minimap Detection - Detects if zoomed out enough to see world map
# ============================================================================

# Minimap constants (from extract_minimap.py auto-detection)
MINIMAP_X = 2334
MINIMAP_Y = 0
MINIMAP_W = 226
MINIMAP_H = 226
MINIMAP_TEMPLATE_PATH = Path(__file__).parent / "templates" / "ground_truth" / "minimap_base.png"

_minimap_template: Optional[np.ndarray] = None


def _load_minimap_template() -> np.ndarray:
    """Load minimap template (cached)."""
    global _minimap_template
    if _minimap_template is None:
        _minimap_template = cv2.imread(str(MINIMAP_TEMPLATE_PATH))
        if _minimap_template is None:
            raise FileNotFoundError(f"Minimap template not found: {MINIMAP_TEMPLATE_PATH}")
    return _minimap_template


def detect_minimap_present(
    adb_controller,
    threshold: float = 0.7,
    temp_path: str = "temp_minimap_check.png"
) -> bool:
    """
    Detect if minimap is visible in upper-right corner.

    The minimap ONLY appears when:
    - In WORLD view (button shows "TOWN")
    - Zoomed out sufficiently

    Args:
        adb_controller: ADBController instance
        threshold: Minimum template match score (0.7 recommended)
        temp_path: Temporary screenshot path

    Returns:
        True if minimap detected, False otherwise

    Example:
        from view_detection import detect_minimap_present

        if detect_minimap_present(adb):
            print("Minimap visible - in World view and zoomed out")
    """
    # Take screenshot
    adb_controller.screenshot(temp_path)
    frame = cv2.imread(temp_path)
    if frame is None:
        return False

    # Extract minimap region
    minimap_roi = frame[MINIMAP_Y:MINIMAP_Y+MINIMAP_H, MINIMAP_X:MINIMAP_X+MINIMAP_W]

    # Load template
    template = _load_minimap_template()

    # Direct similarity comparison (same size images)
    # Convert to grayscale for more robust comparison
    roi_gray = cv2.cvtColor(minimap_roi, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Compute normalized correlation coefficient
    correlation = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_CCOEFF_NORMED)[0, 0]

    return correlation >= threshold


def is_world_view_with_minimap(
    adb_controller,
    view_threshold: float = 0.97,
    minimap_threshold: float = 0.7
) -> bool:
    """
    Check if in WORLD view AND minimap is visible (zoomed out).

    This is the ideal state for zoom calibration and map analysis.

    Args:
        adb_controller: ADBController instance
        view_threshold: Threshold for view detection
        minimap_threshold: Threshold for minimap detection

    Returns:
        True if both conditions met, False otherwise

    Example:
        from view_detection import is_world_view_with_minimap

        if is_world_view_with_minimap(adb):
            print("Ready for zoom calibration!")
    """
    # Check 1: Are we in WORLD view?
    view_state = detect_current_view(adb_controller)
    if view_state != ViewState.WORLD:
        return False

    # Check 2: Is minimap visible?
    return detect_minimap_present(adb_controller, threshold=minimap_threshold)


if __name__ == "__main__":
    import sys
    from find_player import ADBController, Config

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        config = Config()
        adb = ADBController(config)

        # Take screenshot
        adb.screenshot("temp_test.png")
        frame = cv2.imread("temp_test.png")

        # View detection
        detector = ViewDetector()
        result = detector.detect_from_frame(frame)

        print("VIEW DETECTION:")
        print(f"  State: {result.state.value}")
        print(f"  Score: {result.confidence:.4f}")
        print(f"  Minimap Present (from button): {result.minimap_present}")
        if result.minimap_viewport:
            vp = result.minimap_viewport
            minimap_total_area = MINIMAP_W * MINIMAP_H
            zoom_pct = (vp.area / minimap_total_area) * 100
            print(f"\n  Minimap Viewport (Yellow Rectangle):")
            print(f"    Position: ({vp.x}, {vp.y})")
            print(f"    Size: {vp.width}x{vp.height}")
            print(f"    Area: {vp.area} pixels ({zoom_pct:.1f}% of minimap)")
            print(f"    Center: ({vp.center_x}, {vp.center_y})")
            print(f"    Corners:")
            print(f"      Top-Left: {vp.top_left}")
            print(f"      Top-Right: {vp.top_right}")
            print(f"      Bottom-Left: {vp.bottom_left}")
            print(f"      Bottom-Right: {vp.bottom_right}")
            print(f"    Zoom: {'OUT' if zoom_pct > 25 else 'IN'} (larger rectangle = more zoomed OUT)")

        # Minimap detection
        minimap_roi = frame[MINIMAP_Y:MINIMAP_Y+MINIMAP_H, MINIMAP_X:MINIMAP_X+MINIMAP_W]
        template = _load_minimap_template()

        roi_gray = cv2.cvtColor(minimap_roi, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        correlation = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_CCOEFF_NORMED)[0, 0]

        print("\nMINIMAP DETECTION:")
        print(f"  Score: {correlation:.4f}")
        print(f"  Present: {correlation >= 0.7}")
