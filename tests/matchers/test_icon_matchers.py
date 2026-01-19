"""
Unit tests for icon matcher classes in utils/.

Tests cover:
- BubbleMatcher class and create_bubble_matcher factory
- HandshakeIconMatcher
- TreasureMapMatcher
- HarvestBoxMatcher
- BackButtonMatcher

All tests use mocks to avoid requiring actual template images.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import numpy.typing as npt
import pytest


# =============================================================================
# BubbleMatcher Tests
# =============================================================================

class TestBubbleMatcher:
    """Tests for the BubbleMatcher class."""

    def test_is_present_returns_tuple_bool_float(self, sample_frame: npt.NDArray[np.uint8]) -> None:
        """Test that is_present returns (bool, float) tuple."""
        from utils.bubble_matcher import BubbleMatcher

        with patch('utils.bubble_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.03, (100, 100))

            matcher = BubbleMatcher(
                region=(100, 100, 50, 50),
                click_pos=(125, 125),
                template_name="test_template.png",
                threshold=0.06,
                name="test"
            )
            result = matcher.is_present(sample_frame)

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], float)

    def test_is_present_returns_true_when_template_matches(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns True when template is found."""
        from utils.bubble_matcher import BubbleMatcher

        with patch('utils.bubble_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.02, (125, 125))

            matcher = BubbleMatcher(
                region=(100, 100, 50, 50),
                click_pos=(125, 125),
                template_name="test_template.png",
                threshold=0.06
            )
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is True
            assert score == 0.02

    def test_is_present_returns_false_when_template_not_matches(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns False when template is not found."""
        from utils.bubble_matcher import BubbleMatcher

        with patch('utils.bubble_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.15, None)

            matcher = BubbleMatcher(
                region=(100, 100, 50, 50),
                click_pos=(125, 125),
                template_name="test_template.png",
                threshold=0.06
            )
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is False
            assert score == 0.15

    def test_is_present_handles_none_frame(self) -> None:
        """Test is_present handles None frame gracefully."""
        from utils.bubble_matcher import BubbleMatcher

        matcher = BubbleMatcher(
            region=(100, 100, 50, 50),
            click_pos=(125, 125),
            template_name="test_template.png",
            threshold=0.06
        )
        is_present, score = matcher.is_present(None)  # type: ignore

        assert is_present is False
        assert score == 1.0

    def test_is_present_handles_empty_frame(self) -> None:
        """Test is_present handles empty frame gracefully."""
        from utils.bubble_matcher import BubbleMatcher

        empty_frame = np.array([], dtype=np.uint8)
        matcher = BubbleMatcher(
            region=(100, 100, 50, 50),
            click_pos=(125, 125),
            template_name="test_template.png",
            threshold=0.06
        )
        is_present, score = matcher.is_present(empty_frame)

        assert is_present is False
        assert score == 1.0

    def test_is_present_passes_correct_search_region(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present passes correct region to match_template."""
        from utils.bubble_matcher import BubbleMatcher

        with patch('utils.bubble_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.5, None)

            matcher = BubbleMatcher(
                region=(200, 300, 80, 90),
                click_pos=(240, 345),
                template_name="test_template.png",
                threshold=0.08
            )
            matcher.is_present(sample_frame)

            mock_match.assert_called_once()
            call_args = mock_match.call_args
            assert call_args[0][1] == "test_template.png"
            assert call_args[1]['search_region'] == (200, 300, 80, 90)
            assert call_args[1]['threshold'] == 0.08

    def test_click_calls_adb_tap_with_correct_coords(self, mock_adb: MagicMock) -> None:
        """Test click() calls adb.tap with the configured click position."""
        from utils.bubble_matcher import BubbleMatcher

        matcher = BubbleMatcher(
            region=(100, 100, 50, 50),
            click_pos=(150, 175),
            template_name="test_template.png"
        )
        matcher.click(mock_adb)

        mock_adb.tap.assert_called_once_with(150, 175)

    def test_matcher_stores_all_properties(self) -> None:
        """Test that BubbleMatcher stores all initialization properties."""
        from utils.bubble_matcher import BubbleMatcher

        matcher = BubbleMatcher(
            region=(100, 200, 50, 60),
            click_pos=(125, 230),
            template_name="my_template.png",
            threshold=0.05,
            name="my_bubble"
        )

        assert matcher.icon_x == 100
        assert matcher.icon_y == 200
        assert matcher.icon_width == 50
        assert matcher.icon_height == 60
        assert matcher.click_x == 125
        assert matcher.click_y == 230
        assert matcher.template_name == "my_template.png"
        assert matcher.threshold == 0.05
        assert matcher.name == "my_bubble"


class TestCreateBubbleMatcher:
    """Tests for the create_bubble_matcher factory function."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock config module with bubble configs."""
        mock = MagicMock()
        mock.CORN_BUBBLE = {'region': (1015, 869, 67, 57), 'click': (1048, 897)}
        mock.GOLD_BUBBLE = {'region': (1369, 800, 53, 43), 'click': (1395, 835)}
        mock.IRON_BUBBLE = {'region': (1617, 351, 46, 32), 'click': (1639, 377)}
        mock.GEM_BUBBLE = {'region': (1378, 652, 54, 51), 'click': (1405, 696)}
        mock.CABBAGE_BUBBLE = {'region': (1267, 277, 67, 57), 'click': (1300, 305)}
        mock.EQUIPMENT_BUBBLE = {'region': (1246, 859, 67, 57), 'click': (1279, 887)}
        mock.THRESHOLDS = {
            'corn': 0.06,
            'gold': 0.06,
            'iron': 0.08,
            'gem': 0.13,
            'cabbage': 0.05,
            'equipment': 0.06
        }
        return mock

    @pytest.mark.parametrize("config_key,expected_template,expected_threshold", [
        ("corn", "corn_harvest_bubble_4k.png", 0.06),
        ("gold", "gold_coin_tight_4k.png", 0.06),
        ("iron", "iron_bar_tight_4k.png", 0.08),
        ("gem", "gem_tight_4k.png", 0.13),
        ("cabbage", "cabbage_tight_4k.png", 0.05),
        ("equipment", "sword_tight_4k.png", 0.06),
    ])
    def test_create_bubble_matcher_all_types(
        self,
        mock_config: MagicMock,
        config_key: str,
        expected_template: str,
        expected_threshold: float
    ) -> None:
        """Test create_bubble_matcher creates correct matcher for each bubble type."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            # Re-import to use the mocked config
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher(config_key)

            assert matcher.template_name == expected_template
            assert matcher.name == config_key

    def test_create_bubble_matcher_corn(self, mock_config: MagicMock) -> None:
        """Test creating corn bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('corn')

            assert matcher.icon_x == 1015
            assert matcher.icon_y == 869
            assert matcher.icon_width == 67
            assert matcher.icon_height == 57
            assert matcher.click_x == 1048
            assert matcher.click_y == 897

    def test_create_bubble_matcher_gold(self, mock_config: MagicMock) -> None:
        """Test creating gold bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('gold')

            assert matcher.icon_x == 1369
            assert matcher.icon_y == 800
            assert matcher.icon_width == 53
            assert matcher.icon_height == 43
            assert matcher.click_x == 1395
            assert matcher.click_y == 835

    def test_create_bubble_matcher_iron(self, mock_config: MagicMock) -> None:
        """Test creating iron bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('iron')

            assert matcher.icon_x == 1617
            assert matcher.icon_y == 351
            assert matcher.icon_width == 46
            assert matcher.icon_height == 32

    def test_create_bubble_matcher_gem(self, mock_config: MagicMock) -> None:
        """Test creating gem bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('gem')

            assert matcher.icon_x == 1378
            assert matcher.icon_y == 652
            assert matcher.icon_width == 54
            assert matcher.icon_height == 51

    def test_create_bubble_matcher_cabbage(self, mock_config: MagicMock) -> None:
        """Test creating cabbage bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('cabbage')

            assert matcher.icon_x == 1267
            assert matcher.icon_y == 277
            assert matcher.icon_width == 67
            assert matcher.icon_height == 57

    def test_create_bubble_matcher_equipment(self, mock_config: MagicMock) -> None:
        """Test creating equipment bubble matcher with correct region and click."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            matcher = bubble_module.create_bubble_matcher('equipment')

            assert matcher.icon_x == 1246
            assert matcher.icon_y == 859
            assert matcher.icon_width == 67
            assert matcher.icon_height == 57

    def test_create_bubble_matcher_with_custom_threshold(
        self, mock_config: MagicMock
    ) -> None:
        """Test create_bubble_matcher respects custom threshold override."""
        from utils.bubble_matcher import create_bubble_matcher

        with patch.dict('sys.modules', {'config': mock_config}):
            import importlib
            import utils.bubble_matcher as bubble_module
            importlib.reload(bubble_module)

            custom_threshold = 0.15
            matcher = bubble_module.create_bubble_matcher('corn', threshold=custom_threshold)

            assert matcher.threshold == custom_threshold

    def test_create_bubble_matcher_invalid_key_raises_error(self) -> None:
        """Test create_bubble_matcher raises ValueError for unknown config key."""
        from utils.bubble_matcher import create_bubble_matcher

        with pytest.raises(ValueError, match="Unknown bubble config key"):
            create_bubble_matcher('invalid_bubble_type')

    def test_create_bubble_matcher_error_message_contains_valid_keys(self) -> None:
        """Test error message lists valid config keys."""
        from utils.bubble_matcher import create_bubble_matcher

        with pytest.raises(ValueError) as exc_info:
            create_bubble_matcher('nonexistent')

        error_msg = str(exc_info.value)
        assert 'corn' in error_msg
        assert 'gold' in error_msg
        assert 'iron' in error_msg


# =============================================================================
# HandshakeIconMatcher Tests
# =============================================================================

class TestHandshakeIconMatcher:
    """Tests for the HandshakeIconMatcher class."""

    def test_is_present_returns_tuple_bool_float(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test that is_present returns (bool, float) tuple."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        with patch('utils.handshake_icon_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.02, (3165, 1843))

            matcher = HandshakeIconMatcher()
            result = matcher.is_present(sample_frame)

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], float)

    def test_is_present_returns_true_when_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns True when handshake icon is detected."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        with patch('utils.handshake_icon_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.01, (3165, 1843))

            matcher = HandshakeIconMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is True
            assert score == 0.01

    def test_is_present_returns_false_when_not_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns False when handshake icon is not detected."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        with patch('utils.handshake_icon_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.2, None)

            matcher = HandshakeIconMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is False
            assert score == 0.2

    def test_is_present_handles_none_frame(self) -> None:
        """Test is_present handles None frame gracefully."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        matcher = HandshakeIconMatcher()
        is_present, score = matcher.is_present(None)  # type: ignore

        assert is_present is False
        assert score == 1.0

    def test_is_present_handles_empty_frame(self) -> None:
        """Test is_present handles empty frame gracefully."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        empty_frame = np.array([], dtype=np.uint8)
        matcher = HandshakeIconMatcher()
        is_present, score = matcher.is_present(empty_frame)

        assert is_present is False
        assert score == 1.0

    def test_is_present_uses_correct_search_region(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present uses correct fixed search region."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        with patch('utils.handshake_icon_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.5, None)

            matcher = HandshakeIconMatcher()
            matcher.is_present(sample_frame)

            mock_match.assert_called_once()
            call_args = mock_match.call_args
            assert call_args[0][1] == "handshake_icon_4k.png"
            # Check search region matches class constants
            expected_region = (
                HandshakeIconMatcher.ICON_X,
                HandshakeIconMatcher.ICON_Y,
                HandshakeIconMatcher.ICON_WIDTH,
                HandshakeIconMatcher.ICON_HEIGHT
            )
            assert call_args[1]['search_region'] == expected_region

    def test_click_calls_adb_tap_with_correct_coords(self, mock_adb: MagicMock) -> None:
        """Test click() calls adb.tap with the correct fixed position."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        matcher = HandshakeIconMatcher()
        matcher.click(mock_adb)

        mock_adb.tap.assert_called_once_with(
            HandshakeIconMatcher.CLICK_X,
            HandshakeIconMatcher.CLICK_Y
        )

    def test_default_threshold(self) -> None:
        """Test default threshold is 0.04."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        matcher = HandshakeIconMatcher()
        assert matcher.threshold == 0.04

    def test_custom_threshold(self) -> None:
        """Test custom threshold is used."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        matcher = HandshakeIconMatcher(threshold=0.08)
        assert matcher.threshold == 0.08

    def test_class_constants(self) -> None:
        """Test that class constants have expected values."""
        from utils.handshake_icon_matcher import HandshakeIconMatcher

        assert HandshakeIconMatcher.ICON_X == 3088
        assert HandshakeIconMatcher.ICON_Y == 1780
        assert HandshakeIconMatcher.ICON_WIDTH == 155
        assert HandshakeIconMatcher.ICON_HEIGHT == 127
        assert HandshakeIconMatcher.CLICK_X == 3165
        assert HandshakeIconMatcher.CLICK_Y == 1843
        assert HandshakeIconMatcher.TEMPLATE_NAME == "handshake_icon_4k.png"


# =============================================================================
# TreasureMapMatcher Tests
# =============================================================================

class TestTreasureMapMatcher:
    """Tests for the TreasureMapMatcher class."""

    def test_is_present_returns_tuple_bool_float(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test that is_present returns (bool, float) tuple."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        with patch('utils.treasure_map_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.02, (2175, 1621))

            matcher = TreasureMapMatcher()
            result = matcher.is_present(sample_frame)

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], float)

    def test_is_present_returns_true_when_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns True when treasure map is detected."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        with patch('utils.treasure_map_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.03, (2175, 1621))

            matcher = TreasureMapMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is True
            assert score == 0.03

    def test_is_present_returns_false_when_not_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns False when treasure map is not detected."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        with patch('utils.treasure_map_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.3, None)

            matcher = TreasureMapMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is False
            assert score == 0.3

    def test_is_present_handles_none_frame(self) -> None:
        """Test is_present handles None frame gracefully."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        matcher = TreasureMapMatcher()
        is_present, score = matcher.is_present(None)  # type: ignore

        assert is_present is False
        assert score == 1.0

    def test_is_present_handles_empty_frame(self) -> None:
        """Test is_present handles empty frame gracefully."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        empty_frame = np.array([], dtype=np.uint8)
        matcher = TreasureMapMatcher()
        is_present, score = matcher.is_present(empty_frame)

        assert is_present is False
        assert score == 1.0

    def test_is_present_uses_correct_search_region(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present uses correct fixed search region."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        with patch('utils.treasure_map_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.5, None)

            matcher = TreasureMapMatcher()
            matcher.is_present(sample_frame)

            mock_match.assert_called_once()
            call_args = mock_match.call_args
            assert call_args[0][1] == "treasure_map/treasure_map_4k.png"
            expected_region = (
                TreasureMapMatcher.ICON_X,
                TreasureMapMatcher.ICON_Y,
                TreasureMapMatcher.ICON_WIDTH,
                TreasureMapMatcher.ICON_HEIGHT
            )
            assert call_args[1]['search_region'] == expected_region

    def test_click_calls_adb_tap_with_correct_coords(self, mock_adb: MagicMock) -> None:
        """Test click() calls adb.tap with the correct fixed position."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        matcher = TreasureMapMatcher()
        matcher.click(mock_adb)

        mock_adb.tap.assert_called_once_with(
            TreasureMapMatcher.CLICK_X,
            TreasureMapMatcher.CLICK_Y,
            source="matcher:treasure_map:click"
        )

    def test_default_threshold(self) -> None:
        """Test default threshold is 0.01 (tight threshold for masked matching)."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        matcher = TreasureMapMatcher()
        assert matcher.threshold == 0.01

    def test_custom_threshold(self) -> None:
        """Test custom threshold is used."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        matcher = TreasureMapMatcher(threshold=0.1)
        assert matcher.threshold == 0.1

    def test_class_constants(self) -> None:
        """Test that class constants have expected values."""
        from utils.treasure_map_matcher import TreasureMapMatcher

        assert TreasureMapMatcher.ICON_X == 2096
        assert TreasureMapMatcher.ICON_Y == 1540
        assert TreasureMapMatcher.ICON_WIDTH == 158
        assert TreasureMapMatcher.ICON_HEIGHT == 162
        assert TreasureMapMatcher.CLICK_X == 2175
        assert TreasureMapMatcher.CLICK_Y == 1621
        assert TreasureMapMatcher.TEMPLATE == "treasure_map/treasure_map_4k.png"


# =============================================================================
# HarvestBoxMatcher Tests
# =============================================================================

class TestHarvestBoxMatcher:
    """Tests for the HarvestBoxMatcher class."""

    def test_is_present_returns_tuple_bool_float(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test that is_present returns (bool, float) tuple."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        with patch('utils.harvest_box_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.05, (2177, 1618))

            matcher = HarvestBoxMatcher()
            result = matcher.is_present(sample_frame)

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], float)

    def test_is_present_returns_true_when_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns True when harvest box is detected."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        with patch('utils.harvest_box_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.04, (2177, 1618))

            matcher = HarvestBoxMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is True
            assert score == 0.04

    def test_is_present_returns_false_when_not_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns False when harvest box is not detected."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        with patch('utils.harvest_box_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.25, None)

            matcher = HarvestBoxMatcher()
            is_present, score = matcher.is_present(sample_frame)

            assert is_present is False
            assert score == 0.25

    def test_is_present_handles_none_frame(self) -> None:
        """Test is_present handles None frame gracefully."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        matcher = HarvestBoxMatcher()
        is_present, score = matcher.is_present(None)  # type: ignore

        assert is_present is False
        assert score == 1.0

    def test_is_present_handles_empty_frame(self) -> None:
        """Test is_present handles empty frame gracefully."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        empty_frame = np.array([], dtype=np.uint8)
        matcher = HarvestBoxMatcher()
        is_present, score = matcher.is_present(empty_frame)

        assert is_present is False
        assert score == 1.0

    def test_click_calls_adb_tap_with_correct_coords(self, mock_adb: MagicMock) -> None:
        """Test click() calls adb.tap with the correct fixed position."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        matcher = HarvestBoxMatcher()
        matcher.click(mock_adb)

        mock_adb.tap.assert_called_once_with(
            HarvestBoxMatcher.CLICK_X,
            HarvestBoxMatcher.CLICK_Y
        )

    def test_default_threshold(self) -> None:
        """Test default threshold is 0.1."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        matcher = HarvestBoxMatcher()
        assert matcher.threshold == 0.1

    def test_custom_threshold(self) -> None:
        """Test custom threshold is used."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        matcher = HarvestBoxMatcher(threshold=0.05)
        assert matcher.threshold == 0.05

    def test_class_constants(self) -> None:
        """Test that class constants have expected values."""
        from utils.harvest_box_matcher import HarvestBoxMatcher

        assert HarvestBoxMatcher.ICON_X == 2100
        assert HarvestBoxMatcher.ICON_Y == 1540
        assert HarvestBoxMatcher.ICON_WIDTH == 154
        assert HarvestBoxMatcher.ICON_HEIGHT == 157
        assert HarvestBoxMatcher.CLICK_X == 2177
        assert HarvestBoxMatcher.CLICK_Y == 1618
        assert HarvestBoxMatcher.TEMPLATE_NAME == "harvest_box_4k.png"


# =============================================================================
# BackButtonMatcher Tests
# =============================================================================

class TestBackButtonMatcher:
    """Tests for the BackButtonMatcher class."""

    def test_find_returns_tuple_with_four_elements(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test that find returns (bool, float, tuple|None, str|None)."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 1.0, None)

            matcher = BackButtonMatcher()
            result = matcher.find(sample_frame)

            assert isinstance(result, tuple)
            assert len(result) == 4

    def test_find_returns_true_when_button_found(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test find returns found=True when back button is detected."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            with patch('utils.back_button_matcher.has_mask') as mock_has_mask:
                mock_has_mask.return_value = False
                mock_match.return_value = (True, 0.03, (1407, 2055))

                matcher = BackButtonMatcher()
                found, score, pos, template = matcher.find(sample_frame)

                assert found is True
                assert score == 0.03
                assert pos == (1407, 2055)

    def test_find_returns_false_when_no_button(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test find returns found=False when no back button detected."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.5, None)

            matcher = BackButtonMatcher()
            found, score, pos, template = matcher.find(sample_frame)

            assert found is False
            assert pos is None
            assert template is None

    def test_find_handles_none_frame(self) -> None:
        """Test find handles None frame gracefully."""
        from utils.back_button_matcher import BackButtonMatcher

        matcher = BackButtonMatcher()
        found, score, pos, template = matcher.find(None)  # type: ignore

        assert found is False
        assert score == 1.0
        assert pos is None
        assert template is None

    def test_find_handles_empty_frame(self) -> None:
        """Test find handles empty frame gracefully."""
        from utils.back_button_matcher import BackButtonMatcher

        empty_frame = np.array([], dtype=np.uint8)
        matcher = BackButtonMatcher()
        found, score, pos, template = matcher.find(empty_frame)

        assert found is False
        assert score == 1.0
        assert pos is None
        assert template is None

    def test_find_tries_multiple_templates(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test find attempts all templates in order."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            # All templates fail to match
            mock_match.return_value = (False, 0.5, None)

            matcher = BackButtonMatcher()
            matcher.find(sample_frame)

            # Should have called match_template for each template
            assert mock_match.call_count == len(BackButtonMatcher.TEMPLATES)

    def test_find_returns_best_match(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test find returns the best matching template."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            with patch('utils.back_button_matcher.has_mask') as mock_has_mask:
                # First template (union - has mask): medium match
                # Second template (standard): best match
                # Third template (light): poor match
                mock_has_mask.side_effect = [True, False, False]
                mock_match.side_effect = [
                    (True, 0.92, (1400, 2000)),   # CCORR: 0.92 (normalized: 0.92)
                    (True, 0.02, (1405, 2050)),   # SQDIFF: 0.02 (normalized: 0.98)
                    (True, 0.1, (1410, 2055)),    # SQDIFF: 0.1 (normalized: 0.90)
                ]

                matcher = BackButtonMatcher()
                found, score, pos, template = matcher.find(sample_frame)

                assert found is True
                # Best match should be the second one (highest normalized score 0.98)
                assert score == 0.02
                assert pos == (1405, 2050)

    def test_is_present_legacy_api(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_present returns (bool, float) for backward compatibility."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            with patch('utils.back_button_matcher.has_mask') as mock_has_mask:
                mock_has_mask.return_value = False
                mock_match.return_value = (True, 0.04, (1407, 2055))

                matcher = BackButtonMatcher()
                result = matcher.is_present(sample_frame)

                assert isinstance(result, tuple)
                assert len(result) == 2
                assert result[0] is True
                assert result[1] == 0.04

    def test_click_with_detected_position(self, mock_adb: MagicMock) -> None:
        """Test click uses detected position when provided."""
        from utils.back_button_matcher import BackButtonMatcher

        matcher = BackButtonMatcher()
        detected_pos = (1500, 2000)
        matcher.click(mock_adb, detected_pos=detected_pos)

        mock_adb.tap.assert_called_once_with(1500, 2000)

    def test_click_without_detected_position_uses_fallback(
        self, mock_adb: MagicMock
    ) -> None:
        """Test click uses fallback position when no position provided."""
        from utils.back_button_matcher import BackButtonMatcher

        matcher = BackButtonMatcher()
        matcher.click(mock_adb)

        # Default fallback position
        mock_adb.tap.assert_called_once_with(1407, 2055)

    def test_is_template_present_returns_true(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_template_present returns True when template found."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.03, (1407, 2055))

            matcher = BackButtonMatcher()
            result = matcher.is_template_present(sample_frame, "back_button_4k.png")

            assert result is True

    def test_is_template_present_returns_false(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_template_present returns False when template not found."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            mock_match.return_value = (False, 0.3, None)

            matcher = BackButtonMatcher()
            result = matcher.is_template_present(sample_frame, "back_button_4k.png")

            assert result is False

    def test_is_template_present_with_near_pos(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_template_present checks proximity when near_pos provided."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            # Found but at different position
            mock_match.return_value = (True, 0.03, (1500, 2100))

            matcher = BackButtonMatcher()
            # Position is too far (> 30 pixels)
            result = matcher.is_template_present(
                sample_frame,
                "back_button_4k.png",
                near_pos=(1400, 2000),
                tolerance=30
            )

            assert result is False

    def test_is_template_present_near_pos_within_tolerance(
        self, sample_frame: npt.NDArray[np.uint8]
    ) -> None:
        """Test is_template_present returns True when within tolerance."""
        from utils.back_button_matcher import BackButtonMatcher

        with patch('utils.back_button_matcher.match_template') as mock_match:
            mock_match.return_value = (True, 0.03, (1415, 2010))

            matcher = BackButtonMatcher()
            result = matcher.is_template_present(
                sample_frame,
                "back_button_4k.png",
                near_pos=(1400, 2000),
                tolerance=30
            )

            assert result is True

    def test_search_region_constant(self) -> None:
        """Test that search region is bottom half of screen."""
        from utils.back_button_matcher import BackButtonMatcher

        # Bottom half of 4K screen
        assert BackButtonMatcher.SEARCH_REGION == (0, 1080, 3840, 1080)

    def test_templates_list(self) -> None:
        """Test that templates list contains expected templates."""
        from utils.back_button_matcher import BackButtonMatcher

        assert "back_button_union_4k.png" in BackButtonMatcher.TEMPLATES
        assert "back_button_4k.png" in BackButtonMatcher.TEMPLATES
        assert "back_button_light_4k.png" in BackButtonMatcher.TEMPLATES


# =============================================================================
# Integration Tests (All Matchers Together)
# =============================================================================

class TestMatcherConsistency:
    """Tests that verify consistent behavior across all matcher types."""

    @pytest.mark.parametrize("matcher_class,module_path", [
        ("HandshakeIconMatcher", "utils.handshake_icon_matcher"),
        ("TreasureMapMatcher", "utils.treasure_map_matcher"),
        ("HarvestBoxMatcher", "utils.harvest_box_matcher"),
    ])
    def test_all_matchers_have_is_present_method(
        self, matcher_class: str, module_path: str
    ) -> None:
        """Test all icon matchers have is_present method."""
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, matcher_class)
        matcher = cls()
        assert hasattr(matcher, 'is_present')
        assert callable(matcher.is_present)

    @pytest.mark.parametrize("matcher_class,module_path", [
        ("HandshakeIconMatcher", "utils.handshake_icon_matcher"),
        ("TreasureMapMatcher", "utils.treasure_map_matcher"),
        ("HarvestBoxMatcher", "utils.harvest_box_matcher"),
    ])
    def test_all_matchers_have_click_method(
        self, matcher_class: str, module_path: str
    ) -> None:
        """Test all icon matchers have click method."""
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, matcher_class)
        matcher = cls()
        assert hasattr(matcher, 'click')
        assert callable(matcher.click)

    @pytest.mark.parametrize("matcher_class,module_path", [
        ("HandshakeIconMatcher", "utils.handshake_icon_matcher"),
        ("TreasureMapMatcher", "utils.treasure_map_matcher"),
        ("HarvestBoxMatcher", "utils.harvest_box_matcher"),
    ])
    def test_all_matchers_have_threshold_attribute(
        self, matcher_class: str, module_path: str
    ) -> None:
        """Test all icon matchers have threshold attribute."""
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, matcher_class)
        matcher = cls()
        assert hasattr(matcher, 'threshold')
        assert isinstance(matcher.threshold, float)

    @pytest.mark.parametrize("matcher_class,module_path", [
        ("HandshakeIconMatcher", "utils.handshake_icon_matcher"),
        ("TreasureMapMatcher", "utils.treasure_map_matcher"),
        ("HarvestBoxMatcher", "utils.harvest_box_matcher"),
    ])
    def test_all_matchers_accept_custom_threshold(
        self, matcher_class: str, module_path: str
    ) -> None:
        """Test all icon matchers accept custom threshold in constructor."""
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, matcher_class)
        custom_threshold = 0.123
        matcher = cls(threshold=custom_threshold)
        assert matcher.threshold == custom_threshold
