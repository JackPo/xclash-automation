"""
Unit tests for utils/template_matcher.py.

Tests the template matching functionality with mocked cv2 to avoid
needing actual image files. Covers:
- match_template with valid template
- Return value structure (found, score, location)
- Auto mask detection
- Template caching behavior
- Threshold behavior for both SQDIFF and CCORR methods
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest


class TestMatchTemplate:
    """Test match_template function."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        # Import and clear cache before test
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        # Clear cache after test
        template_matcher.clear_cache()

    @pytest.fixture
    def sample_frame(self):
        """4K BGR frame for testing."""
        return np.zeros((2160, 3840, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_template(self):
        """Small template image for testing."""
        return np.zeros((100, 100, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_mask(self):
        """Grayscale mask for testing."""
        return np.ones((100, 100), dtype=np.uint8) * 255

    def test_match_template_returns_tuple(self, sample_frame, sample_template):
        """Test that match_template returns (found, score, location) tuple."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            # Setup mocks
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            # Mock matchTemplate result
            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.01, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            result = match_template(sample_frame, "test_template_4k.png")

            assert isinstance(result, tuple)
            assert len(result) == 3
            found, score, location = result
            assert isinstance(found, bool)
            assert isinstance(score, float)
            assert location is None or isinstance(location, tuple)

    def test_match_template_found_with_good_score(self, sample_frame, sample_template):
        """Test match_template returns True when score meets threshold."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            # Template exists, mask does not
            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Low score (0.01) for SQDIFF means good match
            mock_cv2.minMaxLoc.return_value = (0.01, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, location = match_template(
                sample_frame, "test_template_4k.png", threshold=0.1
            )

            assert found is True
            assert score == 0.01
            # Location should be center of match: (100 + 50, 200 + 50)
            assert location == (150, 250)

    def test_match_template_not_found_with_bad_score(self, sample_frame, sample_template):
        """Test match_template returns False when score exceeds threshold."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            # Template exists, mask does not
            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # High score (0.5) for SQDIFF means bad match
            mock_cv2.minMaxLoc.return_value = (0.5, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, location = match_template(
                sample_frame, "test_template_4k.png", threshold=0.1
            )

            assert found is False
            assert score == 0.5

    def test_match_template_missing_template(self, sample_frame):
        """Test match_template handles missing template file."""
        with patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_dir.__truediv__ = MagicMock(return_value=mock_path)

            from utils.template_matcher import match_template

            found, score, location = match_template(
                sample_frame, "nonexistent_4k.png"
            )

            assert found is False
            assert score == 1.0
            assert location is None

    def test_match_template_with_search_region(self, sample_frame, sample_template):
        """Test match_template with search region offset."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            # Template exists, mask does not
            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((100, 100), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Match at (50, 50) within search region
            mock_cv2.minMaxLoc.return_value = (0.01, 0.99, (50, 50), (80, 80))

            from utils.template_matcher import match_template

            # Search region: x=500, y=300, w=300, h=300
            found, score, location = match_template(
                sample_frame, "test_template_4k.png",
                search_region=(500, 300, 300, 300),
                threshold=0.1
            )

            assert found is True
            # Location should be offset by search region + match position + half template
            # The actual calculation depends on template_matcher implementation
            assert location is not None
            assert isinstance(location, tuple)
            assert len(location) == 2


class TestAutoMaskDetection:
    """Test automatic mask detection and CCORR matching."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        template_matcher.clear_cache()

    @pytest.fixture
    def sample_frame(self):
        """4K BGR frame for testing."""
        return np.zeros((2160, 3840, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_template(self):
        """Small template image for testing."""
        return np.zeros((100, 100, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_template_gray(self):
        """Small grayscale template image for testing."""
        return np.zeros((100, 100), dtype=np.uint8)

    @pytest.fixture
    def sample_mask(self):
        """Grayscale mask for testing."""
        return np.ones((100, 100), dtype=np.uint8) * 255

    def test_auto_mask_detection_when_mask_exists(
        self, sample_frame, sample_template, sample_template_gray, sample_mask
    ):
        """Test that mask is automatically loaded and used when mask file exists."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            # Both template and mask files exist
            def path_exists_side_effect(name):
                mock_path = MagicMock()
                mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_CCORR_NORMED = 3
            mock_cv2.COLOR_BGR2GRAY = 6

            # Return different images based on flag
            def imread_side_effect(path, flag):
                if flag == 0:  # IMREAD_GRAYSCALE
                    if 'mask' in str(path):
                        return sample_mask
                    return sample_template_gray
                return sample_template

            mock_cv2.imread.side_effect = imread_side_effect
            mock_cv2.cvtColor.return_value = sample_template_gray

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # High score (0.98) for CCORR means good match
            mock_cv2.minMaxLoc.return_value = (0.01, 0.98, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, location = match_template(
                sample_frame, "search_button_4k.png", threshold=0.95
            )

            # Should use TM_CCORR_NORMED when mask exists
            mock_cv2.matchTemplate.assert_called_once()
            call_args = mock_cv2.matchTemplate.call_args
            assert call_args[1].get('mask') is not None or len(call_args[0]) > 3

            assert found is True
            assert score == 0.98

    def test_no_mask_uses_sqdiff(self, sample_frame, sample_template):
        """Test that SQDIFF is used when no mask file exists."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            call_count = [0]

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                # Template exists, mask does not
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.02, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, location = match_template(
                sample_frame, "test_template_4k.png", threshold=0.1
            )

            # Should use TM_SQDIFF_NORMED when no mask
            mock_cv2.matchTemplate.assert_called_once()
            call_args = mock_cv2.matchTemplate.call_args
            # Check that mask is not in call (either not in kwargs or is None)
            mask_arg = call_args[1].get('mask') if call_args[1] else None
            assert mask_arg is None

            assert found is True
            assert score == 0.02


class TestCachingBehavior:
    """Test template and mask caching."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        template_matcher.clear_cache()

    @pytest.fixture
    def sample_frame(self):
        """4K BGR frame for testing."""
        return np.zeros((2160, 3840, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_template(self):
        """Small template image for testing."""
        return np.zeros((100, 100, 3), dtype=np.uint8)

    def test_template_loaded_once_and_cached(self, sample_frame, sample_template):
        """Test that template is loaded once and reused from cache."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.02, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            # Call match_template multiple times with same template
            match_template(sample_frame, "cached_template_4k.png")
            match_template(sample_frame, "cached_template_4k.png")
            match_template(sample_frame, "cached_template_4k.png")

            # cv2.imread should only be called once for this template
            # (may be called for mask check too, but template itself only once)
            imread_calls = [
                c for c in mock_cv2.imread.call_args_list
                if 'cached_template_4k' in str(c) and 'mask' not in str(c)
            ]
            assert len(imread_calls) == 1

    def test_clear_cache_resets_templates(self, sample_frame, sample_template):
        """Test that clear_cache allows templates to be reloaded."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.02, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template, clear_cache

            # First call - loads template
            match_template(sample_frame, "reload_template_4k.png")
            initial_call_count = mock_cv2.imread.call_count

            # Clear cache
            clear_cache()

            # Second call - should reload template
            match_template(sample_frame, "reload_template_4k.png")

            # Should have additional imread calls after cache clear
            assert mock_cv2.imread.call_count > initial_call_count

    def test_different_templates_cached_separately(self, sample_frame, sample_template):
        """Test that different templates are cached independently."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.02, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            # Load two different templates
            match_template(sample_frame, "template_a_4k.png")
            match_template(sample_frame, "template_b_4k.png")

            # Each should be loaded once
            imread_calls_a = [
                c for c in mock_cv2.imread.call_args_list
                if 'template_a_4k' in str(c) and 'mask' not in str(c)
            ]
            imread_calls_b = [
                c for c in mock_cv2.imread.call_args_list
                if 'template_b_4k' in str(c) and 'mask' not in str(c)
            ]
            assert len(imread_calls_a) == 1
            assert len(imread_calls_b) == 1


class TestThresholdBehavior:
    """Test threshold behavior for both matching methods."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        template_matcher.clear_cache()

    @pytest.fixture
    def sample_frame(self):
        """4K BGR frame for testing."""
        return np.zeros((2160, 3840, 3), dtype=np.uint8)

    @pytest.fixture
    def sample_template(self):
        """Small template image for testing."""
        return np.zeros((100, 100, 3), dtype=np.uint8)

    def test_sqdiff_threshold_boundary_pass(self, sample_frame, sample_template):
        """Test SQDIFF threshold: score exactly at threshold passes."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Score exactly at threshold
            mock_cv2.minMaxLoc.return_value = (0.05, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, _ = match_template(
                sample_frame, "test_4k.png", threshold=0.05
            )

            assert found is True  # Score <= threshold passes for SQDIFF
            assert score == 0.05

    def test_sqdiff_threshold_boundary_fail(self, sample_frame, sample_template):
        """Test SQDIFF threshold: score just above threshold fails."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Score just above threshold
            mock_cv2.minMaxLoc.return_value = (0.051, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, _ = match_template(
                sample_frame, "test_4k.png", threshold=0.05
            )

            assert found is False  # Score > threshold fails for SQDIFF
            assert score == 0.051

    def test_ccorr_threshold_boundary_pass(
        self, sample_frame, sample_template
    ):
        """Test CCORR threshold: score exactly at threshold passes."""
        sample_template_gray = np.zeros((100, 100), dtype=np.uint8)
        sample_mask = np.ones((100, 100), dtype=np.uint8) * 255

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                mock_path.exists.return_value = True  # Both template and mask exist
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_CCORR_NORMED = 3
            mock_cv2.COLOR_BGR2GRAY = 6

            def imread_side_effect(path, flag):
                if flag == 0:  # IMREAD_GRAYSCALE
                    if 'mask' in str(path):
                        return sample_mask
                    return sample_template_gray
                return sample_template

            mock_cv2.imread.side_effect = imread_side_effect
            mock_cv2.cvtColor.return_value = sample_template_gray

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Score exactly at threshold
            mock_cv2.minMaxLoc.return_value = (0.01, 0.95, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, _ = match_template(
                sample_frame, "masked_4k.png", threshold=0.95
            )

            assert found is True  # Score >= threshold passes for CCORR
            assert score == 0.95

    def test_ccorr_threshold_boundary_fail(
        self, sample_frame, sample_template
    ):
        """Test CCORR threshold: score just below threshold fails."""
        sample_template_gray = np.zeros((100, 100), dtype=np.uint8)
        sample_mask = np.ones((100, 100), dtype=np.uint8) * 255

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                mock_path.exists.return_value = True  # Both template and mask exist
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_CCORR_NORMED = 3
            mock_cv2.COLOR_BGR2GRAY = 6

            def imread_side_effect(path, flag):
                if flag == 0:
                    if 'mask' in str(path):
                        return sample_mask
                    return sample_template_gray
                return sample_template

            mock_cv2.imread.side_effect = imread_side_effect
            mock_cv2.cvtColor.return_value = sample_template_gray

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            # Score just below threshold
            mock_cv2.minMaxLoc.return_value = (0.01, 0.949, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, _ = match_template(
                sample_frame, "masked_4k.png", threshold=0.95
            )

            assert found is False  # Score < threshold fails for CCORR
            assert score == 0.949

    def test_default_sqdiff_threshold(self, sample_frame, sample_template):
        """Test default threshold for SQDIFF (0.1)."""
        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.imread.return_value = sample_template

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array

            from utils.template_matcher import match_template, DEFAULT_SQDIFF_THRESHOLD

            # Score at default threshold
            mock_cv2.minMaxLoc.return_value = (0.1, 0.99, (100, 200), (300, 400))

            found, _, _ = match_template(sample_frame, "test_4k.png")
            assert found is True  # Should pass with default threshold
            assert DEFAULT_SQDIFF_THRESHOLD == 0.1

    def test_default_ccorr_threshold(self, sample_frame, sample_template):
        """Test default threshold for CCORR (0.90)."""
        sample_template_gray = np.zeros((100, 100), dtype=np.uint8)
        sample_mask = np.ones((100, 100), dtype=np.uint8) * 255

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_CCORR_NORMED = 3
            mock_cv2.COLOR_BGR2GRAY = 6

            def imread_side_effect(path, flag):
                if flag == 0:
                    if 'mask' in str(path):
                        return sample_mask
                    return sample_template_gray
                return sample_template

            mock_cv2.imread.side_effect = imread_side_effect
            mock_cv2.cvtColor.return_value = sample_template_gray

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array

            from utils.template_matcher import match_template, DEFAULT_CCORR_THRESHOLD

            # Score at default threshold
            mock_cv2.minMaxLoc.return_value = (0.01, 0.90, (100, 200), (300, 400))

            found, _, _ = match_template(sample_frame, "masked_4k.png")
            assert found is True  # Should pass with default threshold
            assert DEFAULT_CCORR_THRESHOLD == 0.90


class TestHelperFunctions:
    """Test helper functions like has_mask and get_mask_path."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        template_matcher.clear_cache()

    def test_get_mask_name_4k_convention(self):
        """Test mask naming convention for 4K templates."""
        from utils.template_matcher import _get_mask_name

        assert _get_mask_name("search_button_4k.png") == "search_button_mask_4k.png"
        assert _get_mask_name("icon_4k.png") == "icon_mask_4k.png"

    def test_get_mask_name_1080p_convention(self):
        """Test mask naming convention for 1080p templates."""
        from utils.template_matcher import _get_mask_name

        assert _get_mask_name("icon_1080p.png") == "icon_mask_1080p.png"

    def test_get_mask_name_no_resolution_suffix(self):
        """Test mask naming for templates without resolution suffix."""
        from utils.template_matcher import _get_mask_name

        assert _get_mask_name("other.png") == "other_mask.png"

    def test_has_mask_returns_true_when_exists(self):
        """Test has_mask returns True when mask file exists."""
        with patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:
            def path_side_effect(name):
                mock_path = MagicMock()
                mock_path.exists.return_value = True
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_side_effect)

            from utils.template_matcher import has_mask

            assert has_mask("search_button_4k.png") is True

    def test_has_mask_returns_false_when_not_exists(self):
        """Test has_mask returns False when mask file does not exist."""
        with patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:
            def path_side_effect(name):
                mock_path = MagicMock()
                # Mask does not exist
                mock_path.exists.return_value = 'mask' not in str(name)
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_side_effect)

            from utils.template_matcher import has_mask

            assert has_mask("no_mask_template_4k.png") is False

    def test_get_mask_path_returns_path_object(self):
        """Test get_mask_path returns a Path object."""
        from utils.template_matcher import get_mask_path

        result = get_mask_path("search_button_4k.png")
        assert isinstance(result, Path)
        assert result.name == "search_button_mask_4k.png"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear template cache before and after each test."""
        from utils import template_matcher
        template_matcher.clear_cache()
        yield
        template_matcher.clear_cache()

    @pytest.fixture
    def sample_template(self):
        """Small template image for testing."""
        return np.zeros((100, 100, 3), dtype=np.uint8)

    def test_search_area_smaller_than_template(self, sample_template):
        """Test handling when search area is smaller than template."""
        # Frame smaller than template
        small_frame = np.zeros((50, 50, 3), dtype=np.uint8)

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.imread.return_value = sample_template

            from utils.template_matcher import match_template

            found, score, location = match_template(small_frame, "test_4k.png")

            assert found is False
            assert score == 1.0
            assert location is None

    def test_search_region_too_small(self, sample_template):
        """Test handling when search region is smaller than template."""
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.imread.return_value = sample_template

            from utils.template_matcher import match_template

            # Search region 50x50 is smaller than 100x100 template
            found, score, location = match_template(
                frame, "test_4k.png", search_region=(100, 100, 50, 50)
            )

            assert found is False
            assert score == 1.0
            assert location is None

    def test_grayscale_mode(self, sample_template):
        """Test grayscale matching mode."""
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        gray_template = np.zeros((100, 100), dtype=np.uint8)

        with patch('utils.template_matcher.cv2') as mock_cv2, \
             patch('utils.template_matcher.TEMPLATE_DIR') as mock_dir:

            def path_exists_side_effect(name):
                mock_path = MagicMock()
                if 'mask' in str(name):
                    mock_path.exists.return_value = False
                else:
                    mock_path.exists.return_value = True
                mock_path.__str__ = MagicMock(return_value=str(name))
                return mock_path

            mock_dir.__truediv__ = MagicMock(side_effect=path_exists_side_effect)

            mock_cv2.IMREAD_COLOR = 1
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.TM_SQDIFF_NORMED = 1
            mock_cv2.COLOR_BGR2GRAY = 6
            mock_cv2.imread.return_value = gray_template
            mock_cv2.cvtColor.return_value = np.zeros((2160, 3840), dtype=np.uint8)

            result_array = np.zeros((2060, 3740), dtype=np.float32)
            mock_cv2.matchTemplate.return_value = result_array
            mock_cv2.minMaxLoc.return_value = (0.02, 0.99, (100, 200), (300, 400))

            from utils.template_matcher import match_template

            found, score, location = match_template(
                frame, "test_4k.png", grayscale=True, threshold=0.1
            )

            # Should call cvtColor to convert frame to grayscale
            mock_cv2.cvtColor.assert_called()
            assert found is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
