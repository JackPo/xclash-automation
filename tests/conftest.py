"""
Pytest configuration and shared fixtures for xclash tests.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Add project root to path so imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

if TYPE_CHECKING:
    import numpy.typing as npt


# =============================================================================
# Frame Fixtures
# =============================================================================

@pytest.fixture
def sample_frame() -> npt.NDArray[np.uint8]:
    """4K black frame for testing (3840x2160 BGR)."""
    return np.zeros((2160, 3840, 3), dtype=np.uint8)


@pytest.fixture
def white_frame() -> npt.NDArray[np.uint8]:
    """4K white frame for testing."""
    return np.ones((2160, 3840, 3), dtype=np.uint8) * 255


@pytest.fixture
def random_frame() -> npt.NDArray[np.uint8]:
    """4K random noise frame for testing."""
    return np.random.randint(0, 256, (2160, 3840, 3), dtype=np.uint8)


# =============================================================================
# ADB Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_adb() -> MagicMock:
    """Mock ADBHelper that tracks all calls."""
    adb = MagicMock()
    adb.tap = MagicMock(return_value=None)
    adb.swipe = MagicMock(return_value=None)
    adb.device = "emulator-5554"
    adb.adb_path = "C:\\Program Files\\BlueStacks_nxt\\hd-adb.exe"
    return adb


# =============================================================================
# Screenshot Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_win(sample_frame: npt.NDArray[np.uint8]) -> MagicMock:
    """Mock WindowsScreenshotHelper that returns sample_frame."""
    win = MagicMock()
    win.get_screenshot_cv2 = MagicMock(return_value=sample_frame)
    return win


@pytest.fixture
def mock_win_factory() -> Any:
    """Factory for creating mock WindowsScreenshotHelper with custom frames."""
    def _create_mock(*frames: npt.NDArray[np.uint8]) -> MagicMock:
        win = MagicMock()
        if len(frames) == 1:
            win.get_screenshot_cv2 = MagicMock(return_value=frames[0])
        else:
            win.get_screenshot_cv2 = MagicMock(side_effect=list(frames))
        return win
    return _create_mock


# =============================================================================
# Template Matcher Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_template_match() -> Generator[MagicMock, None, None]:
    """Patch template_matcher.match_template - returns (False, 1.0, None) by default."""
    with patch('utils.template_matcher.match_template') as mock:
        mock.return_value = (False, 1.0, None)
        yield mock


@pytest.fixture
def mock_template_match_fixed() -> Generator[MagicMock, None, None]:
    """Patch template_matcher.match_template_fixed - returns (False, 1.0, None) by default."""
    with patch('utils.template_matcher.match_template_fixed') as mock:
        mock.return_value = (False, 1.0, None)
        yield mock


@pytest.fixture
def mock_template_found() -> Generator[MagicMock, None, None]:
    """Patch template_matcher.match_template - returns found with good score."""
    with patch('utils.template_matcher.match_template') as mock:
        mock.return_value = (True, 0.02, (100, 100))
        yield mock


# =============================================================================
# View State Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_detect_view_town() -> Generator[MagicMock, None, None]:
    """Patch detect_view to return TOWN."""
    with patch('utils.view_state_detector.detect_view') as mock:
        from utils.view_state_detector import ViewState
        mock.return_value = (ViewState.TOWN, 0.02)
        yield mock


@pytest.fixture
def mock_detect_view_world() -> Generator[MagicMock, None, None]:
    """Patch detect_view to return WORLD."""
    with patch('utils.view_state_detector.detect_view') as mock:
        from utils.view_state_detector import ViewState
        mock.return_value = (ViewState.WORLD, 0.02)
        yield mock


# =============================================================================
# OCR Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_ocr() -> MagicMock:
    """Mock OCR client."""
    ocr = MagicMock()
    ocr.extract_number = MagicMock(return_value=100)
    ocr.extract_text = MagicMock(return_value="test")
    return ocr


# =============================================================================
# Config Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_config() -> Generator[None, None, None]:
    """Patch config values for testing."""
    with patch.dict('config.__dict__', {
        'IDLE_THRESHOLD': 300,
        'CHECK_INTERVAL': 3,
    }):
        yield


# =============================================================================
# Device Availability Check
# =============================================================================

def device_available() -> bool:
    """Check if a real device is available for e2e tests."""
    try:
        import subprocess
        result = subprocess.run(
            ['C:\\Program Files\\BlueStacks_nxt\\hd-adb.exe', 'devices'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return 'emulator' in result.stdout
    except Exception:
        return False


@pytest.fixture
def require_device() -> None:
    """Skip test if no device is available."""
    if not device_available():
        pytest.skip("No device connected")


# =============================================================================
# Template Path Fixture
# =============================================================================

@pytest.fixture
def templates_dir() -> Path:
    """Path to templates/ground_truth directory."""
    return project_root / "templates" / "ground_truth"


# =============================================================================
# Time Mock Fixtures
# =============================================================================

@pytest.fixture
def freeze_time_2026() -> Generator[None, None, None]:
    """Freeze time to 2026-01-04 10:00:00 UTC."""
    from freezegun import freeze_time
    with freeze_time("2026-01-04 10:00:00"):
        yield
