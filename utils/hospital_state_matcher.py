"""
Hospital State Matcher - Detects state of hospital building.

The hospital has a floating bubble icon above it indicating its state:
- Handshake icon = HELP_READY (ready for allies to help speed up - ALWAYS CLICK)
- Stopwatch icon = TRAINING (healing in progress, countdown active)
- Briefcase icon = HEALING (soldiers ready to claim after healing)
- Yellow soldier face = SOLDIERS_WOUNDED (soldiers wounded, need healing)
- Neither = IDLE (nothing to do)

Detection logic:
1. Extract ROI at fixed position (3312, 344) size 61x67
2. Match all templates using TM_SQDIFF_NORMED
3. If lowest score <= threshold:
   - Handshake wins → HELP_READY (always click!)
   - Stopwatch wins → TRAINING
   - Briefcase wins → HEALING
   - Yellow soldier wins → SOLDIERS_WOUNDED
4. None pass → IDLE

NOTE: Yellow soldier faces vary based on which soldier type was trained!
Multiple yellow soldier templates are loaded to match all variants.
"""

import numpy as np
from enum import Enum

from config import (
    HOSPITAL_ICON_POSITION,
    HOSPITAL_ICON_SIZE,
    HOSPITAL_CLICK_POSITION,
    HOSPITAL_MATCH_THRESHOLD,
)
from utils.template_matcher import match_template_fixed


class HospitalState(Enum):
    HELP_READY = "help_ready"     # Handshake icon - ready for allies to help (ALWAYS CLICK)
    TRAINING = "training"         # Stopwatch icon - healing in progress (countdown)
    HEALING = "healing"           # Briefcase icon - soldiers ready to claim
    SOLDIERS_WOUNDED = "wounded"  # Yellow soldier - soldiers wounded, need healing
    IDLE = "idle"                 # No template matches
    UNKNOWN = "unknown"           # Error/transitional state


class HospitalStateMatcher:
    """Detects the state of the hospital building."""

    HANDSHAKE_TEMPLATE = "handshake_hospital_4k.png"
    STOPWATCH_TEMPLATE = "stopwatch_barrack_4k.png"
    HEALING_TEMPLATE = "healing_bubble_tight_4k.png"
    YELLOW_SOLDIER_TEMPLATES = [
        "yellow_soldier_barrack_4k.png",
        "yellow_soldier_barrack_v2_4k.png",
        "yellow_soldier_barrack_v3_4k.png",
        "yellow_soldier_barrack_v4_4k.png",
        "yellow_soldier_barrack_v5_4k.png",
        "yellow_soldier_barrack_v6_4k.png",
    ]

    def __init__(self):
        self.icon_x, self.icon_y = HOSPITAL_ICON_POSITION
        self.icon_w, self.icon_h = HOSPITAL_ICON_SIZE
        self.click_x, self.click_y = HOSPITAL_CLICK_POSITION
        self.threshold = HOSPITAL_MATCH_THRESHOLD

    def get_scores(self, frame: np.ndarray) -> dict[str, float]:
        """
        Get all template scores for the hospital position.

        Returns:
            dict with 'handshake', 'stopwatch', 'healing', 'yellow_soldier' scores
        """
        scores = {'handshake': 1.0, 'stopwatch': 1.0, 'healing': 1.0, 'yellow_soldier': 1.0}

        # Match each template at the hospital position
        _, handshake_score, _ = match_template_fixed(
            frame,
            self.HANDSHAKE_TEMPLATE,
            position=(self.icon_x, self.icon_y),
            size=(self.icon_w, self.icon_h),
            threshold=self.threshold
        )
        scores['handshake'] = handshake_score

        _, stopwatch_score, _ = match_template_fixed(
            frame,
            self.STOPWATCH_TEMPLATE,
            position=(self.icon_x, self.icon_y),
            size=(self.icon_w, self.icon_h),
            threshold=self.threshold
        )
        scores['stopwatch'] = stopwatch_score

        _, healing_score, _ = match_template_fixed(
            frame,
            self.HEALING_TEMPLATE,
            position=(self.icon_x, self.icon_y),
            size=(self.icon_w, self.icon_h),
            threshold=self.threshold
        )
        scores['healing'] = healing_score

        # Match against all yellow soldier variants, use best (lowest) score
        yellow_scores = []
        for template_name in self.YELLOW_SOLDIER_TEMPLATES:
            _, score, _ = match_template_fixed(
                frame,
                template_name,
                position=(self.icon_x, self.icon_y),
                size=(self.icon_w, self.icon_h),
                threshold=self.threshold
            )
            yellow_scores.append(score)

        if yellow_scores:
            scores['yellow_soldier'] = min(yellow_scores)

        return scores

    def get_state(self, frame: np.ndarray, debug: bool = False) -> tuple[HospitalState, float]:
        """
        Get the current state of the hospital.

        Returns:
            (HospitalState, best_score) tuple
        """
        scores = self.get_scores(frame)

        handshake_score = scores['handshake']
        stopwatch_score = scores['stopwatch']
        healing_score = scores['healing']
        yellow_score = scores['yellow_soldier']

        best_score = min(handshake_score, stopwatch_score, healing_score, yellow_score)

        if debug:
            print(f"  Hospital: handshake={handshake_score:.4f}, stopwatch={stopwatch_score:.4f}, healing={healing_score:.4f}, yellow={yellow_score:.4f}, threshold={self.threshold}")

        # Check if best match passes threshold
        if best_score <= self.threshold:
            # Handshake takes priority - always click when detected
            if handshake_score <= stopwatch_score and handshake_score <= healing_score and handshake_score <= yellow_score:
                if debug:
                    print(f"  Hospital: HELP_READY (score={handshake_score:.4f})")
                return HospitalState.HELP_READY, handshake_score
            elif stopwatch_score <= healing_score and stopwatch_score <= yellow_score:
                if debug:
                    print(f"  Hospital: TRAINING (score={stopwatch_score:.4f})")
                return HospitalState.TRAINING, stopwatch_score
            elif healing_score <= yellow_score:
                if debug:
                    print(f"  Hospital: HEALING (score={healing_score:.4f})")
                return HospitalState.HEALING, healing_score
            else:
                if debug:
                    print(f"  Hospital: SOLDIERS_WOUNDED (score={yellow_score:.4f})")
                return HospitalState.SOLDIERS_WOUNDED, yellow_score

        # None passes threshold
        if debug:
            print(f"  Hospital: IDLE (best={best_score:.4f} > threshold={self.threshold})")
        return HospitalState.IDLE, best_score

    def get_click_position(self) -> tuple[int, int]:
        """Return the click position for the hospital."""
        return (self.click_x, self.click_y)

    def format_state(self, frame: np.ndarray) -> str:
        """Format hospital state as a short string for logging."""
        state, score = self.get_state(frame)
        state_char = {
            HospitalState.HELP_READY: "HELP",
            HospitalState.TRAINING: "TRAIN",
            HospitalState.HEALING: "HEAL",
            HospitalState.SOLDIERS_WOUNDED: "WOUND",
            HospitalState.IDLE: "IDLE",
            HospitalState.UNKNOWN: "?"
        }.get(state, "?")
        return f"H:{state_char}"

    def format_state_detailed(self, frame: np.ndarray) -> str:
        """Format hospital state with all scores for debugging."""
        scores = self.get_scores(frame)
        state, _ = self.get_state(frame)
        state_char = {
            HospitalState.HELP_READY: "HELP",
            HospitalState.TRAINING: "TRAIN",
            HospitalState.HEALING: "HEAL",
            HospitalState.SOLDIERS_WOUNDED: "WOUND",
            HospitalState.IDLE: "IDLE",
            HospitalState.UNKNOWN: "?"
        }.get(state, "?")
        return f"H:{state_char}(hs={scores['handshake']:.3f},s={scores['stopwatch']:.3f},h={scores['healing']:.3f},y={scores['yellow_soldier']:.3f})"


# Singleton instance
_matcher = None


def get_matcher() -> HospitalStateMatcher:
    """Get singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = HospitalStateMatcher()
    return _matcher


def check_hospital_state(frame: np.ndarray, debug: bool = False) -> tuple[HospitalState, float]:
    """Convenience function to check hospital state."""
    return get_matcher().get_state(frame, debug=debug)


def format_hospital_state(frame: np.ndarray) -> str:
    """Convenience function to get formatted hospital state string."""
    return get_matcher().format_state(frame)


def format_hospital_state_detailed(frame: np.ndarray) -> str:
    """Convenience function to get detailed hospital state with scores."""
    return get_matcher().format_state_detailed(frame)
