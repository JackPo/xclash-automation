"""
Barracks State Matcher - Detects state of each barracks building.

Each barracks has a floating bubble icon above it indicating its state:
- Timer/stopwatch icon = TRAINING (soldiers currently training, countdown active)
- Yellow soldier face = READY (soldiers ready to collect)
- White/gray soldier face = PENDING (idle, can start training)

Detection logic (explicit template matching for all states):
1. Check stopwatch template → TRAINING
2. Check yellow soldier template → READY
3. Check white soldier template → PENDING
4. No match → UNKNOWN

Barracks positions are configured in config.py (BARRACKS_POSITIONS).

Templates:
- stopwatch_barrack_4k.png - Timer icon for TRAINING state
- yellow_soldier_barrack_4k.png - Yellow soldier for READY state
- white_soldier_barrack_4k.png - White soldier for PENDING state
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
    PENDING = "pending"   # No timer, no yellow - idle, can start training
    TRAINING = "training" # Stopwatch/timer visible - currently training
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

    def get_barrack_scores(self, frame, barrack_index, frame_gray=None):
        """
        Get all template scores for a single barrack.

        Args:
            frame: BGR numpy array screenshot
            barrack_index: 0-3 for the 4 barracks
            frame_gray: Optional pre-computed grayscale frame

        Returns:
            dict with 'stopwatch', 'yellow', 'white' scores (1.0 if template not loaded)
        """
        scores = {'stopwatch': 1.0, 'yellow': 1.0, 'white': 1.0}

        if barrack_index < 0 or barrack_index >= len(BARRACKS_POSITIONS):
            return scores

        x, y = BARRACKS_POSITIONS[barrack_index]

        if frame_gray is None:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.stopwatch_template is not None:
            scores['stopwatch'] = self._match_template_at_position(
                frame_gray, self.stopwatch_gray, x, y
            )
        if self.yellow_template is not None:
            scores['yellow'] = self._match_template_at_position(
                frame_gray, self.yellow_gray, x, y
            )
        if self.white_template is not None:
            scores['white'] = self._match_template_at_position(
                frame_gray, self.white_gray, x, y
            )

        return scores

    def get_barrack_state(self, frame, barrack_index, frame_gray=None):
        """
        Get the state of a single barrack.

        Uses explicit template matching - picks the template with the LOWEST score
        (best match) among those that pass the threshold.

        Args:
            frame: BGR numpy array screenshot
            barrack_index: 0-3 for the 4 barracks
            frame_gray: Optional pre-computed grayscale frame

        Returns:
            (BarrackState, best_score) tuple
        """
        if barrack_index < 0 or barrack_index >= len(BARRACKS_POSITIONS):
            return BarrackState.UNKNOWN, 1.0

        if frame_gray is None:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        scores = self.get_barrack_scores(frame, barrack_index, frame_gray)

        # Find all templates that pass threshold, pick the one with lowest score
        candidates = []
        if scores['stopwatch'] <= MATCH_THRESHOLD:
            candidates.append((BarrackState.TRAINING, scores['stopwatch']))
        if scores['yellow'] <= MATCH_THRESHOLD:
            candidates.append((BarrackState.READY, scores['yellow']))
        if scores['white'] <= MATCH_THRESHOLD:
            candidates.append((BarrackState.PENDING, scores['white']))

        if candidates:
            # Return the state with the lowest (best) score
            return min(candidates, key=lambda x: x[1])

        # No match - return UNKNOWN with best score for debugging
        best_score = min(scores['stopwatch'], scores['yellow'], scores['white'])
        return BarrackState.UNKNOWN, best_score

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

    def format_states_detailed(self, frame):
        """
        Format barrack states with all template scores for debugging.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            String with state and all scores for each barrack
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        parts = []
        for i in range(4):
            state, _ = self.get_barrack_state(frame, i, frame_gray)
            scores = self.get_barrack_scores(frame, i, frame_gray)
            state_char = {
                BarrackState.READY: "R",
                BarrackState.PENDING: "P",
                BarrackState.TRAINING: "T",
                BarrackState.UNKNOWN: "?"
            }.get(state, "?")
            parts.append(
                f"B{i+1}:{state_char}(s={scores['stopwatch']:.3f},y={scores['yellow']:.3f},w={scores['white']:.3f})"
            )

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


def format_barracks_states_detailed(frame):
    """
    Convenience function to get detailed barrack states with all scores.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        String like "B1:R(s=0.100,y=0.030,w=0.080) B2:T(s=0.020,y=0.150,w=0.140) ..."
    """
    return get_matcher().format_states_detailed(frame)
