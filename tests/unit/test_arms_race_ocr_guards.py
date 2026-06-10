"""Tests for Arms Race score OCR consensus + monotonic plausibility guards."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import arms_race_ocr
from utils.arms_race_ocr import get_current_points_verified, get_last_confirmed_points


def _win() -> MagicMock:
    win = MagicMock()
    win.get_screenshot_cv2.return_value = MagicMock(size=100)
    return win


def _verified(readings: list[int | None], last_known: int | None = None) -> int | None:
    """Run get_current_points_verified with scripted OCR readings."""
    with patch.object(arms_race_ocr, "ocr_number_from_region", side_effect=readings), \
         patch("time.sleep"):
        return get_current_points_verified(_win(), retries=len(readings), last_known=last_known)


class TestConsensus:
    def test_majority_agreement_returns_value(self) -> None:
        assert _verified([5200, 5200, 9999]) == 5200

    def test_no_consensus_returns_none(self) -> None:
        assert _verified([5200, 5300, 5400]) is None

    def test_all_none_returns_none(self) -> None:
        assert _verified([None, None, None]) is None


class TestMonotonicGuard:
    """Scores within a block only go up - decreases need unanimity."""

    def test_increase_accepted(self) -> None:
        assert _verified([6000, 6000, 6000], last_known=5000) == 6000

    def test_majority_decrease_rejected(self) -> None:
        # 2/3 agree on a value below last known - probable misread, reject
        assert _verified([4000, 4000, 6000], last_known=5000) is None

    def test_unanimous_decrease_accepted(self) -> None:
        # All reads agree: our stored state was stale, OCR is right
        assert _verified([4000, 4000, 4000], last_known=5000) == 4000

    def test_equal_to_last_known_accepted(self) -> None:
        assert _verified([5000, 5000, 5000], last_known=5000) == 5000


class TestJumpsAccepted:
    """Scores legitimately leap while the panel is closed - no upper guard."""

    def test_large_jump_accepted_with_consensus(self) -> None:
        assert _verified([152000, 152000, 15300], last_known=15200) == 152000

    def test_moderate_jump_accepted(self) -> None:
        assert _verified([10000, 10000, 9000], last_known=5000) == 10000

    def test_jump_from_small_score_accepted(self) -> None:
        assert _verified([900, 900, 100], last_known=100) == 900


class TestLastConfirmedPoints:
    def _score(self, points: int, event: str, age_seconds: int) -> dict:
        ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        return {"current_points": points, "event": event, "timestamp": ts.isoformat()}

    def test_same_event_recent_returned(self) -> None:
        with patch("utils.current_state.get_arms_race_score",
                   return_value=self._score(5000, "Mystic Beast Training", 600)):
            assert get_last_confirmed_points("Mystic Beast Training") == 5000

    def test_different_event_ignored(self) -> None:
        with patch("utils.current_state.get_arms_race_score",
                   return_value=self._score(5000, "City Construction", 600)):
            assert get_last_confirmed_points("Mystic Beast Training") is None

    def test_stale_score_ignored(self) -> None:
        # Older than one 4h block - previous block, scores reset
        with patch("utils.current_state.get_arms_race_score",
                   return_value=self._score(5000, "Mystic Beast Training", 5 * 3600)):
            assert get_last_confirmed_points("Mystic Beast Training") is None

    def test_score_before_block_start_ignored(self) -> None:
        block_start = datetime.now(timezone.utc) - timedelta(minutes=10)
        with patch("utils.current_state.get_arms_race_score",
                   return_value=self._score(5000, "Mystic Beast Training", 1200)):
            assert get_last_confirmed_points("Mystic Beast Training", block_start) is None

    def test_score_within_block_returned(self) -> None:
        block_start = datetime.now(timezone.utc) - timedelta(hours=2)
        with patch("utils.current_state.get_arms_race_score",
                   return_value=self._score(5000, "Mystic Beast Training", 600)):
            assert get_last_confirmed_points("Mystic Beast Training", block_start) == 5000

    def test_empty_state_returns_none(self) -> None:
        with patch("utils.current_state.get_arms_race_score", return_value={}):
            assert get_last_confirmed_points("Mystic Beast Training") is None
