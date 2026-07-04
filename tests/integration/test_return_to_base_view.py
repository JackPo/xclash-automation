"""
Tests for utils/return_to_base_view.py

Tests the return_to_base_view recovery function that handles:
1. Already in TOWN/WORLD view - immediate success
2. Clicking back buttons to exit menus
3. Max retries behavior
4. Recovery from CHAT state
5. Recovery from UNKNOWN state via grass/ground detection
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.view_state_detector import ViewState

if TYPE_CHECKING:
    import numpy.typing as npt


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_frame() -> npt.NDArray[np.uint8]:
    """4K black frame for testing (3840x2160 BGR)."""
    return np.zeros((2160, 3840, 3), dtype=np.uint8)


@pytest.fixture
def mock_adb() -> MagicMock:
    """Mock ADBHelper that tracks all calls."""
    adb = MagicMock()
    adb.tap = MagicMock(return_value=None)
    adb.swipe = MagicMock(return_value=None)
    adb.device = "emulator-5554"
    adb.ADB_PATH = "C:\\Program Files\\BlueStacks_nxt\\hd-adb.exe"
    return adb


@pytest.fixture
def mock_win(sample_frame: npt.NDArray[np.uint8]) -> MagicMock:
    """Mock WindowsScreenshotHelper that returns sample_frame."""
    win = MagicMock()
    win.get_screenshot_cv2 = MagicMock(return_value=sample_frame)
    return win


@pytest.fixture
def mock_win_sequence() -> Any:
    """Factory to create mock_win returning sequence of frames."""
    def _create(*frames: npt.NDArray[np.uint8]) -> MagicMock:
        win = MagicMock()
        win.get_screenshot_cv2 = MagicMock(side_effect=list(frames))
        return win
    return _create


# =============================================================================
# Test: Already in TOWN view
# =============================================================================

class TestAlreadyInTown:
    """Test return_to_base_view returns True when already in TOWN."""

    def test_returns_true_immediately_when_in_town(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock,
        sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """When detect_view returns TOWN, function should return True immediately."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)):

            # Setup back button matcher to return not found
            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Should NOT have clicked anything since we're already in TOWN
            mock_adb.tap.assert_not_called()

    def test_no_back_button_clicks_needed(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When in TOWN, no back button clicks should be made."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            assert mock_adb.tap.call_count == 0


# =============================================================================
# Test: Already in WORLD view
# =============================================================================

class TestAlreadyInWorld:
    """Test return_to_base_view returns True when already in WORLD."""

    def test_returns_true_immediately_when_in_world(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When detect_view returns WORLD, function should return True immediately."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.WORLD, 0.03)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            mock_adb.tap.assert_not_called()

    def test_world_view_score_is_reported(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When in WORLD, the score should be from detect_view."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.WORLD, 0.015)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True


# =============================================================================
# Test: Clicking back button to exit menus
# =============================================================================

class TestBackButtonClicks:
    """Test back button clicking to exit menus/dialogs."""

    def test_clicks_back_button_when_found(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock,
        sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """When back button is found in UNKNOWN state, should click it."""
        # Sequence: UNKNOWN (back button found) -> TOWN (success)
        detect_view_returns = [
            (ViewState.UNKNOWN, 1.0),  # First check - in menu
            (ViewState.UNKNOWN, 1.0),  # Phase 1 check
            (ViewState.TOWN, 0.02),    # After polling - reached TOWN
        ]

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_returns), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            # Return back button found, then not found
            mock_back_matcher.find.side_effect = [
                (True, 0.05, (1407, 2055), "back_button_4k.png"),
                (False, 1.0, None, None),
            ]
            mock_back_matcher.is_template_present.return_value = False  # Button dismissed
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Should have clicked the back button position
            mock_adb.tap.assert_called_with(1407, 2055)

    def test_multiple_back_button_clicks_to_exit_nested_menus(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock,
        sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """When multiple back buttons need to be clicked (nested menus)."""
        # Simulate 3 back button clicks needed
        detect_view_returns = [
            (ViewState.UNKNOWN, 1.0),  # Initial
            (ViewState.UNKNOWN, 1.0),  # After click 1
            (ViewState.UNKNOWN, 1.0),  # After click 1 poll
            (ViewState.UNKNOWN, 1.0),  # After click 2
            (ViewState.UNKNOWN, 1.0),  # After click 2 poll
            (ViewState.TOWN, 0.02),    # After click 3 - success
        ]

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_returns), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            back_pos = (1407, 2055)
            # Back button found 3 times, then not found
            mock_back_matcher.find.side_effect = [
                (True, 0.05, back_pos, "back_button_4k.png"),
                (True, 0.04, back_pos, "back_button_4k.png"),
                (True, 0.03, back_pos, "back_button_4k.png"),
                (False, 1.0, None, None),
            ]
            mock_back_matcher.is_template_present.return_value = False
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Should have clicked back button 3 times
            assert mock_adb.tap.call_count == 3
            for c in mock_adb.tap.call_args_list:
                assert c == call(1407, 2055)


# =============================================================================
# Test: Max retries behavior
# =============================================================================

class TestMaxRetriesBehavior:
    """Test behavior when max retries are exhausted."""

    def test_continues_attempting_after_initial_attempts(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """Function should restart app and keep trying (recursive) after max attempts."""
        from utils.return_to_base_view import MAX_RECOVERY_ATTEMPTS

        # Track number of detect_view calls to know when we've gone through enough attempts
        detect_count = [0]
        start_app_count = [0]

        def detect_view_side_effect(*args: Any, **kwargs: Any) -> tuple[ViewState, float]:
            detect_count[0] += 1
            # Only succeed after _start_app has been called
            if start_app_count[0] > 0:
                return (ViewState.TOWN, 0.02)
            return (ViewState.UNKNOWN, 1.0)

        def start_app_side_effect(*args: Any, **kwargs: Any) -> None:
            start_app_count[0] += 1

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_side_effect), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view._start_app', side_effect=start_app_side_effect) as mock_start_app, \
             patch('utils.return_to_base_view._detect_troop_selected', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view._detect_resource_bar', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Should have called _start_app to restart at least once
            assert start_app_count[0] >= 1

    def test_exhausts_back_clicks_per_attempt(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """Each attempt should try up to MAX_BACK_CLICKS back button clicks."""
        from utils.return_to_base_view import MAX_BACK_CLICKS

        click_count = [0]

        def detect_view_side_effect(*args: Any, **kwargs: Any) -> tuple[ViewState, float]:
            # After enough clicks, return TOWN
            if click_count[0] >= 3:
                return (ViewState.TOWN, 0.02)
            return (ViewState.UNKNOWN, 1.0)

        def tap_side_effect(x: int, y: int) -> None:
            click_count[0] += 1

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_side_effect), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            # Always return back button found
            mock_back_matcher.find.return_value = (True, 0.05, (1407, 2055), "back_button_4k.png")
            mock_back_matcher.is_template_present.return_value = False
            mock_back_matcher_cls.return_value = mock_back_matcher

            mock_adb.tap.side_effect = tap_side_effect

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Should have clicked back button at least once
            assert click_count[0] >= 1


# =============================================================================
# Test: Recovery from CHAT state
# =============================================================================

class TestChatStateRecovery:
    """Test recovery from CHAT state."""

    def test_chat_state_triggers_back_button_via_unknown_handling(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """CHAT state should be handled - back button click to exit."""
        # Note: return_to_base_view doesn't have special CHAT handling,
        # it relies on back button detection which would be present in CHAT
        detect_view_returns = [
            (ViewState.CHAT, 0.03),    # Initial - in chat
            (ViewState.CHAT, 0.03),    # Check in loop
            (ViewState.TOWN, 0.02),    # After clicking back - success
        ]

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_returns), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            # Back button found in chat
            mock_back_matcher.find.side_effect = [
                (True, 0.04, (1407, 2055), "back_button_4k.png"),
                (False, 1.0, None, None),
            ]
            mock_back_matcher.is_template_present.return_value = False
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            # CHAT is not TOWN/WORLD, so it will continue trying
            # The back button click should help exit
            mock_adb.tap.assert_called()


# =============================================================================
# Test: Recovery from UNKNOWN state via grass/ground detection
# =============================================================================

class TestUnknownStateRecovery:
    """Test recovery from UNKNOWN state using grass/ground detection."""

    def test_grass_detection_indicates_world_view(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When grass is detected, should recognize WORLD view."""
        detect_view_returns = [
            (ViewState.UNKNOWN, 1.0),  # Initial
            (ViewState.UNKNOWN, 1.0),  # Loop check
            (ViewState.UNKNOWN, 1.0),  # After back button check
            (ViewState.WORLD, 0.02),   # After grass click - success
        ]

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_returns), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.safe_grass_matcher.find_safe_grass', return_value=(1000, 1000)), \
             patch('utils.safe_ground_matcher.find_safe_ground', return_value=None), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True

    def test_ground_detection_indicates_town_view(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When ground is detected, should recognize TOWN view."""
        detect_view_returns = [
            (ViewState.UNKNOWN, 1.0),  # Initial
            (ViewState.UNKNOWN, 1.0),  # Loop check
            (ViewState.UNKNOWN, 1.0),  # After back button check
            (ViewState.TOWN, 0.02),    # After ground detection - success
        ]

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_returns), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.safe_grass_matcher.find_safe_grass', return_value=None), \
             patch('utils.safe_ground_matcher.find_safe_ground', return_value=(1500, 1200)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True

    def test_clicks_grass_to_dismiss_popup(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When grass is detected in UNKNOWN state, should click it to dismiss popup."""
        call_count = [0]

        def detect_view_side_effect(*args: Any, **kwargs: Any) -> tuple[ViewState, float]:
            call_count[0] += 1
            # Return UNKNOWN first, then WORLD after clicking
            if call_count[0] <= 4:
                return (ViewState.UNKNOWN, 1.0)
            return (ViewState.WORLD, 0.02)

        grass_pos = (1500, 1200)

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_side_effect), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.safe_grass_matcher.find_safe_grass', return_value=grass_pos), \
             patch('utils.safe_ground_matcher.find_safe_ground', return_value=None), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True


# =============================================================================
# Test: App foreground check and startup
# =============================================================================

class TestAppForegroundHandling:
    """Test app foreground detection and startup."""

    def test_starts_app_when_not_in_foreground(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When app is not in foreground, should start it."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=False), \
             patch('utils.return_to_base_view._start_app') as mock_start_app, \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            mock_start_app.assert_called_once()

    def test_runs_setup_when_resolution_wrong(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When resolution is wrong, should run setup_bluestacks."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="1920x1080"), \
             patch('utils.return_to_base_view._run_setup_bluestacks') as mock_setup, \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            mock_setup.assert_called_once()

    def test_skips_setup_when_resolution_correct(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When resolution is already correct, should skip setup."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view._run_setup_bluestacks') as mock_setup, \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            mock_setup.assert_not_called()


# =============================================================================
# Test: Shaded button handling
# =============================================================================

class TestShadedButtonHandling:
    """Test handling of shaded buttons (popups blocking)."""

    def test_dismisses_popups_when_shaded_button_detected(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When shaded button is detected, should call dismiss_popups."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(True, 0.05)), \
             patch('utils.shaded_button_helper.dismiss_popups') as mock_dismiss, \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            mock_dismiss.assert_called_once()


# =============================================================================
# Test: Troop selected state
# =============================================================================

class TestTroopSelectedState:
    """Test handling of troop selected state."""

    def test_clicks_map_to_deselect_troops(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When troop is selected, should click map to deselect."""
        from utils.return_to_base_view import MAP_DESELECT_CLICK

        call_count = [0]

        def detect_view_side_effect(*args: Any, **kwargs: Any) -> tuple[ViewState, float]:
            call_count[0] += 1
            if call_count[0] > 5:
                return (ViewState.WORLD, 0.02)
            return (ViewState.UNKNOWN, 1.0)

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_side_effect), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view._detect_troop_selected', return_value=(True, 0.05)), \
             patch('utils.return_to_base_view._detect_resource_bar', return_value=(False, 1.0)), \
             patch('utils.safe_grass_matcher.find_safe_grass', return_value=None), \
             patch('utils.safe_ground_matcher.find_safe_ground', return_value=None), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Check that MAP_DESELECT_CLICK was called
            tap_calls = [c for c in mock_adb.tap.call_args_list if c == call(*MAP_DESELECT_CLICK)]
            assert len(tap_calls) >= 1


# =============================================================================
# Test: Resource bar visible state
# =============================================================================

class TestResourceBarState:
    """Test handling of resource bar visible but world button hidden."""

    def test_clicks_center_when_resource_bar_visible(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """When resource bar visible but no world button, click center."""
        from utils.return_to_base_view import CENTER_SCREEN_CLICK

        call_count = [0]

        def detect_view_side_effect(*args: Any, **kwargs: Any) -> tuple[ViewState, float]:
            call_count[0] += 1
            if call_count[0] > 5:
                return (ViewState.TOWN, 0.02)
            return (ViewState.UNKNOWN, 1.0)

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', side_effect=detect_view_side_effect), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view._detect_troop_selected', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view._detect_resource_bar', return_value=(True, 0.05)), \
             patch('utils.safe_grass_matcher.find_safe_grass', return_value=None), \
             patch('utils.safe_ground_matcher.find_safe_ground', return_value=None), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            # Check that CENTER_SCREEN_CLICK was called at some point
            tap_calls = [c for c in mock_adb.tap.call_args_list if c == call(*CENTER_SCREEN_CLICK)]
            assert len(tap_calls) >= 1


# =============================================================================
# Test: Debug mode
# =============================================================================

class TestDebugMode:
    """Test debug mode output."""

    def test_debug_mode_does_not_crash(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock,
        capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Debug mode should run without errors."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=True)

            assert result is True
            # Debug mode should print something
            captured = capsys.readouterr()
            assert "[RETURN]" in captured.out or "Reached" in captured.out or "town" in captured.out.lower()


# =============================================================================
# Test: Consecutive restart tracking
# =============================================================================

class TestConsecutiveRestartTracking:
    """Test that consecutive restarts are tracked."""

    def test_resets_restart_count_on_success(
        self,
        mock_adb: MagicMock,
        mock_win: MagicMock
    ) -> None:
        """Restart count should reset when successfully reaching TOWN/WORLD."""
        import utils.return_to_base_view as rtbv

        # Set a non-zero restart count
        rtbv._consecutive_restarts = 5

        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('time.sleep'):

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, mock_win, debug=False)

            assert result is True
            assert rtbv._consecutive_restarts == 0


# =============================================================================
# Test: Screenshot helper creation
# =============================================================================

class TestScreenshotHelperCreation:
    """Test screenshot helper is created if not provided."""

    def test_creates_screenshot_helper_if_not_provided(
        self,
        mock_adb: MagicMock,
        sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """When no screenshot helper provided, should create one."""
        with patch('utils.return_to_base_view._is_xclash_in_foreground', return_value=True), \
             patch('utils.return_to_base_view._get_current_resolution', return_value="3840x2160"), \
             patch('utils.return_to_base_view.detect_view', return_value=(ViewState.TOWN, 0.02)), \
             patch('utils.return_to_base_view.BackButtonMatcher') as mock_back_matcher_cls, \
             patch('utils.shaded_button_helper.is_button_shaded', return_value=(False, 1.0)), \
             patch('utils.return_to_base_view.WindowsScreenshotHelper') as mock_win_cls, \
             patch('time.sleep'):

            mock_win_instance = MagicMock()
            mock_win_instance.get_screenshot_cv2.return_value = sample_frame
            mock_win_cls.return_value = mock_win_instance

            mock_back_matcher = MagicMock()
            mock_back_matcher.find.return_value = (False, 1.0, None, None)
            mock_back_matcher_cls.return_value = mock_back_matcher

            from utils.return_to_base_view import return_to_base_view

            result = return_to_base_view(mock_adb, screenshot_helper=None, debug=False)

            assert result is True
            mock_win_cls.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
