"""
Barracks State Matcher - Detects state of each barracks building.

Each barracks has a floating bubble icon above it indicating its state:
- Yellow soldier face = READY (soldiers ready to collect)
- White soldier face = PENDING (idle, can start training)
- Stopwatch = TRAINING (soldiers currently training)

Barracks positions are configured in config.py (BARRACKS_POSITIONS).

Templates:
- yellow_soldier_barrack_4k.png - Ready state (collect soldiers)
- white_soldier_barrack_4k.png - Pending state (start training)
- stopwatch_barrack_4k.png - Training state (in progress)
"""

from pathlib import Path
import cv2
import numpy as np
from enum import Enum

from config import BARRACKS_POSITIONS, BARRACKS_TEMPLATE_SIZE, BARRACKS_MATCH_THRESHOLD

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
YELLOW_TEMPLATE = TEMPLATE_DIR / "yellow_soldier_barrack_4k.png"
WHITE_TEMPLATE = TEMPLATE_DIR / "white_soldier_barrack_4k.png"
STOPWATCH_TEMPLATE = TEMPLATE_DIR / "stopwatch_barrack_4k.png"

# Use config values
TEMPLATE_SIZE = BARRACKS_TEMPLATE_SIZE
MATCH_THRESHOLD = BARRACKS_MATCH_THRESHOLD


class BarrackState(Enum):
    READY = "ready"       # Yellow - soldiers ready to collect
    PENDING = "pending"   # White - idle, can start training
    TRAINING = "training" # Stopwatch - currently training
    UNKNOWN = "unknown"   # No match found


class BarracksStateMatcher:
    """Detects the state of all 4 barracks buildings."""

    def __init__(self):
        # Load templates
        self.yellow_template = cv2.imread(str(YELLOW_TEMPLATE))
        self.white_template = cv2.imread(str(WHITE_TEMPLATE))
        self.stopwatch_template = cv2.imread(str(STOPWATCH_TEMPLATE))

        if self.yellow_template is None:
            print(f"Warning: Could not load {YELLOW_TEMPLATE}")
        if self.white_template is None:
            print(f"Warning: Could not load {WHITE_TEMPLATE}")
        if self.stopwatch_template is None:
            print(f"Warning: Could not load {STOPWATCH_TEMPLATE}")

        # Convert to grayscale
        if self.yellow_template is not None:
            self.yellow_gray = cv2.cvtColor(self.yellow_template, cv2.COLOR_BGR2GRAY)
        if self.white_template is not None:
            self.white_gray = cv2.cvtColor(self.white_template, cv2.COLOR_BGR2GRAY)
        if self.stopwatch_template is not None:
            self.stopwatch_gray = cv2.cvtColor(self.stopwatch_template, cv2.COLOR_BGR2GRAY)

    def _match_template_at_position(self, frame_gray, template_gray, x, y):
        """Match template at a specific position, return score."""
        tw, th = TEMPLATE_SIZE

        # Extract ROI at position
        roi = frame_gray[y:y+th, x:x+tw]

        if roi.shape != template_gray.shape:
            return 1.0  # No match

        # Direct comparison using TM_SQDIFF_NORMED
        result = cv2.matchTemplate(roi, template_gray, cv2.TM_SQDIFF_NORMED)
        return result[0][0]

    def get_barrack_state(self, frame, barrack_index):
        """
        Get the state of a single barrack.

        Uses hybrid approach:
        1. Check stopwatch template for PENDING state
        2. If no stopwatch, use pixel counting to distinguish READY vs TRAINING

        Args:
            frame: BGR numpy array screenshot
            barrack_index: 0-3 for the 4 barracks

        Returns:
            (BarrackState, best_score) tuple
        """
        if barrack_index < 0 or barrack_index >= len(BARRACKS_POSITIONS):
            return BarrackState.UNKNOWN, 1.0

        x, y = BARRACKS_POSITIONS[barrack_index]
        tw, th = TEMPLATE_SIZE

        # Step 1: Check for stopwatch (PENDING)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.stopwatch_template is not None:
            stopwatch_score = self._match_template_at_position(
                frame_gray, self.stopwatch_gray, x, y
            )
            if stopwatch_score <= MATCH_THRESHOLD:
                return BarrackState.PENDING, stopwatch_score

        # Step 2: Not stopwatch, use pixel counting to distinguish READY vs TRAINING
        # Extract the ROI
        roi = frame[y:y+th, x:x+tw]
        if roi.shape[0] != th or roi.shape[1] != tw:
            return BarrackState.UNKNOWN, 1.0

        b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]

        # Count yellow pixels (READY = yellow border)
        # Yellow: high R (>150), high G (>150), low B (<100)
        yellow_mask = (r > 150) & (g > 150) & (b < 100)
        yellow_count = int(yellow_mask.sum())

        # Count white pixels (TRAINING = white/gray soldier)
        # White: all channels high (>200)
        white_mask = (r > 200) & (g > 200) & (b > 200)
        white_count = int(white_mask.sum())

        total_pixels = tw * th

        # Decision based on pixel counts
        # READY template has ~15% yellow pixels
        # TRAINING template has ~21% white pixels
        yellow_pct = yellow_count / total_pixels
        white_pct = white_count / total_pixels

        if yellow_pct > 0.10:  # More than 10% yellow = READY
            return BarrackState.READY, yellow_pct
        elif white_pct > 0.15:  # More than 15% white = TRAINING
            return BarrackState.TRAINING, white_pct
        else:
            return BarrackState.UNKNOWN, 1.0

    def get_all_states(self, frame):
        """
        Get the state of all 4 barracks.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            List of (BarrackState, score) tuples for each barrack
        """
        return [self.get_barrack_state(frame, i) for i in range(4)]

    def get_states_summary(self, frame):
        """
        Get a summary of all barrack states.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            dict with counts: {'ready': N, 'pending': N, 'training': N, 'unknown': N}
        """
        states = self.get_all_states(frame)
        summary = {
            'ready': 0,
            'pending': 0,
            'training': 0,
            'unknown': 0
        }

        for state, score in states:
            summary[state.value] += 1

        return summary

    def format_states(self, frame):
        """
        Format barrack states as a human-readable string.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            String like "B1:READY B2:TRAINING B3:PENDING B4:TRAINING"
        """
        states = self.get_all_states(frame)
        parts = []
        for i, (state, score) in enumerate(states):
            state_char = {
                BarrackState.READY: "R",
                BarrackState.PENDING: "P",
                BarrackState.TRAINING: "T",
                BarrackState.UNKNOWN: "?"
            }.get(state, "?")
            parts.append(f"B{i+1}:{state_char}")

        return " ".join(parts)


# Singleton instance
_matcher = None

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = BarracksStateMatcher()
    return _matcher


def check_barracks_states(frame):
    """
    Convenience function to check all barrack states.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        List of (BarrackState, score) tuples
    """
    return get_matcher().get_all_states(frame)


def format_barracks_states(frame):
    """
    Convenience function to get formatted barrack states string.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        String like "B1:R B2:T B3:P B4:T"
    """
    return get_matcher().format_states(frame)
