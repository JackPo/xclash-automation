"""
World/Town View Detection Utility

Clean, reusable API for detecting and switching between WORLD and TOWN views
using template matching on the lower-right toggle button.

Usage Examples:
    # Simple detection
    from view_detection import detect_current_view, ViewState
    state = detect_current_view(adb_controller)
    if state == ViewState.WORLD:
        print("In World view")

    # Simple switching
    from view_detection import switch_to_view
    success = switch_to_view(adb_controller, ViewState.TOWN)

    # Advanced usage
    from view_detection import ViewDetector, ViewSwitcher
    detector = ViewDetector()
    result = detector.detect_from_adb(adb_controller)
    print(f"State: {result.state}, Confidence: {result.confidence:.2f}")
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path
import time
import numpy as np

from button_matcher import ButtonMatcher, TemplateMatch


class ViewState(Enum):
    """Type-safe view state enumeration."""
    WORLD = "WORLD"
    TOWN = "TOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class ViewDetectionResult:
    """
    Structured result from view detection.

    Attributes:
        state: The detected view state (WORLD, TOWN, or UNKNOWN)
        confidence: Match confidence score (0.0-1.0)
        match: Full template match result if detected, None otherwise
    """
    state: ViewState
    confidence: float
    match: Optional[TemplateMatch] = None


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
        threshold: float = 0.97
    ):
        """
        Initialize ViewDetector.

        Args:
            button_matcher: ButtonMatcher instance. If None, creates default.
            threshold: Minimum score for positive detection (0.97 recommended)
        """
        if button_matcher is None:
            template_dir = Path(__file__).parent / "templates" / "buttons"
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
                match=match
            )

        self._last_match = match
        return ViewDetectionResult(
            state=ViewState(match.label),
            confidence=match.score,
            match=match
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
                match=match
            )

        self._last_match = match
        return ViewDetectionResult(
            state=ViewState(match.label),
            confidence=match.score,
            match=match
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
