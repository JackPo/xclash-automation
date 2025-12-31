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

import cv2
import numpy as np
from enum import Enum

from config import BARRACKS_POSITIONS, BARRACKS_TEMPLATE_SIZE, BARRACKS_MATCH_THRESHOLD, BARRACKS_YELLOW_PIXEL_THRESHOLD
from utils.template_matcher import match_template_fixed

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

    YELLOW_TEMPLATE = "yellow_soldier_barrack_4k.png"
    WHITE_TEMPLATE = "white_soldier_barrack_4k.png"
    STOPWATCH_TEMPLATE = "stopwatch_barrack_4k.png"

    def __init__(self):
        pass  # Templates are now loaded by template_matcher

    def _count_yellow_pixels(self, roi_bgr):
        """
        Count yellow pixels in ROI using HSV color space.

        Used to distinguish READY (yellow soldier ~2600 pixels) from
        PENDING (white soldier ~0 pixels) when template scores are ambiguous.
        """
        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        lower_yellow = np.array([15, 100, 100])
        upper_yellow = np.array([45, 255, 255])
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        return np.count_nonzero(mask)

    def get_barrack_scores(self, frame, barrack_index):
        """
        Get all template scores for a single barrack.

        Returns:
            dict with 'stopwatch', 'yellow', 'white' scores (1.0 if no match)
        """
        scores = {'stopwatch': 1.0, 'yellow': 1.0, 'white': 1.0}

        if barrack_index < 0 or barrack_index >= len(BARRACKS_POSITIONS):
            return scores

        x, y = BARRACKS_POSITIONS[barrack_index]
        tw, th = TEMPLATE_SIZE

        # Match each template at this position
        _, stopwatch_score, _ = match_template_fixed(
            frame,
            self.STOPWATCH_TEMPLATE,
            position=(x, y),
            size=(tw, th),
            threshold=MATCH_THRESHOLD
        )
        scores['stopwatch'] = stopwatch_score

        _, yellow_score, _ = match_template_fixed(
            frame,
            self.YELLOW_TEMPLATE,
            position=(x, y),
            size=(tw, th),
            threshold=MATCH_THRESHOLD
        )
        scores['yellow'] = yellow_score

        _, white_score, _ = match_template_fixed(
            frame,
            self.WHITE_TEMPLATE,
            position=(x, y),
            size=(tw, th),
            threshold=MATCH_THRESHOLD
        )
        scores['white'] = white_score

        return scores

    def get_barrack_state(self, frame, barrack_index, frame_gray=None):
        """
        Get the state of a single barrack.

        Detection logic:
        1. If stopwatch passes threshold AND is best match → TRAINING
        2. If yellow OR white passes threshold:
           - Count yellow pixels in ROI
           - If yellow_pixels >= threshold → READY
           - Else → PENDING
        3. No template passes → UNKNOWN
        """
        if barrack_index < 0 or barrack_index >= len(BARRACKS_POSITIONS):
            return BarrackState.UNKNOWN, 1.0

        scores = self.get_barrack_scores(frame, barrack_index)

        # Check which templates pass threshold
        stopwatch_pass = scores['stopwatch'] <= MATCH_THRESHOLD
        yellow_pass = scores['yellow'] <= MATCH_THRESHOLD
        white_pass = scores['white'] <= MATCH_THRESHOLD

        # If stopwatch passes and is the best match, it's TRAINING
        if stopwatch_pass:
            if scores['stopwatch'] <= scores['yellow'] and scores['stopwatch'] <= scores['white']:
                return BarrackState.TRAINING, scores['stopwatch']

        # If yellow or white passes, use yellow pixel counting to distinguish
        if yellow_pass or white_pass:
            x, y = BARRACKS_POSITIONS[barrack_index]
            tw, th = TEMPLATE_SIZE
            roi_bgr = frame[y:y+th, x:x+tw]
            yellow_pixels = self._count_yellow_pixels(roi_bgr)

            if yellow_pixels >= BARRACKS_YELLOW_PIXEL_THRESHOLD:
                return BarrackState.READY, scores['yellow']
            else:
                return BarrackState.PENDING, scores['white']

        # Stopwatch passed but wasn't best - still TRAINING
        if stopwatch_pass:
            return BarrackState.TRAINING, scores['stopwatch']

        # No match - return UNKNOWN with best score for debugging
        best_score = min(scores['stopwatch'], scores['yellow'], scores['white'])
        return BarrackState.UNKNOWN, best_score

    def get_all_states(self, frame):
        """Get the state of all 4 barracks."""
        return [self.get_barrack_state(frame, i) for i in range(4)]

    def get_states_summary(self, frame):
        """Get a summary of all barrack states."""
        states = self.get_all_states(frame)
        summary = {'ready': 0, 'pending': 0, 'training': 0, 'unknown': 0}

        for state, score in states:
            summary[state.value] += 1

        return summary

    def format_states(self, frame):
        """Format barrack states as a human-readable string."""
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
        """Format barrack states with all template scores for debugging."""
        parts = []
        for i in range(4):
            state, _ = self.get_barrack_state(frame, i)
            scores = self.get_barrack_scores(frame, i)
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
    """Convenience function to check all barrack states."""
    return get_matcher().get_all_states(frame)


def format_barracks_states(frame):
    """Convenience function to get formatted barrack states string."""
    return get_matcher().format_states(frame)


def format_barracks_states_detailed(frame):
    """Convenience function to get detailed barrack states with all scores."""
    return get_matcher().format_states_detailed(frame)
