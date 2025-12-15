"""
Hospital State Matcher - Detects state of hospital building.

The hospital has a floating bubble icon above it indicating its state:
- Handshake icon = HELP_READY (ready for allies to help speed up - ALWAYS CLICK)
- Stopwatch icon = TRAINING (healing in progress, countdown active)
- Briefcase icon = HEALING (soldiers ready to claim after healing)
- Yellow soldier face = SOLDIERS_WOUNDED (soldiers wounded, need healing)
- Neither = IDLE (nothing to do)

Detection logic (follows barracks pattern):
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
Templates are shared with barracks_state_matcher.

Templates:
- handshake_hospital_4k.png - Handshake icon for HELP_READY state (always click)
- stopwatch_barrack_4k.png - Stopwatch icon for TRAINING state (shared with barracks)
- healing_bubble_tight_4k.png - Briefcase icon for HEALING state
- yellow_soldier_barrack_4k.png - Yellow soldier variant 1 (shared with barracks)
- yellow_soldier_barrack_v2_4k.png - Yellow soldier variant 2 (shared with barracks)
"""

from pathlib import Path
import cv2
import numpy as np
from enum import Enum

from config import (
    HOSPITAL_ICON_POSITION,
    HOSPITAL_ICON_SIZE,
    HOSPITAL_CLICK_POSITION,
    HOSPITAL_MATCH_THRESHOLD,
)

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
HANDSHAKE_TEMPLATE = TEMPLATE_DIR / "handshake_hospital_4k.png"  # Help ready - always click
STOPWATCH_TEMPLATE = TEMPLATE_DIR / "stopwatch_barrack_4k.png"  # Shared with barracks
HEALING_TEMPLATE = TEMPLATE_DIR / "healing_bubble_tight_4k.png"
# Multiple yellow soldier variants (different soldier types have different faces)
# Shared with barracks_state_matcher
YELLOW_SOLDIER_TEMPLATES = [
    TEMPLATE_DIR / "yellow_soldier_barrack_4k.png",      # Purple hat soldier
    TEMPLATE_DIR / "yellow_soldier_barrack_v2_4k.png",   # Purple hat soldier (different frame)
    TEMPLATE_DIR / "yellow_soldier_barrack_v3_4k.png",   # Red hat soldier
    TEMPLATE_DIR / "yellow_soldier_barrack_v4_4k.png",   # Orange hat soldier
    TEMPLATE_DIR / "yellow_soldier_barrack_v5_4k.png",   # Yellow/orange hat soldier
    TEMPLATE_DIR / "yellow_soldier_barrack_v6_4k.png",   # Purple hat soldier (golden background)
]


class HospitalState(Enum):
    HELP_READY = "help_ready"     # Handshake icon - ready for allies to help (ALWAYS CLICK)
    TRAINING = "training"         # Stopwatch icon - healing in progress (countdown)
    HEALING = "healing"           # Briefcase icon - soldiers ready to claim
    SOLDIERS_WOUNDED = "wounded"  # Yellow soldier - soldiers wounded, need healing
    IDLE = "idle"                 # No template matches
    UNKNOWN = "unknown"           # Error/transitional state


class HospitalStateMatcher:
    """Detects the state of the hospital building."""

    def __init__(self):
        # Load templates
        self.handshake_template = cv2.imread(str(HANDSHAKE_TEMPLATE))
        self.stopwatch_template = cv2.imread(str(STOPWATCH_TEMPLATE))
        self.healing_template = cv2.imread(str(HEALING_TEMPLATE))

        # Load multiple yellow soldier templates (different soldier faces)
        self.yellow_soldier_templates = []
        for path in YELLOW_SOLDIER_TEMPLATES:
            template = cv2.imread(str(path))
            if template is not None:
                self.yellow_soldier_templates.append(template)
            else:
                print(f"Warning: Could not load {path}")

        if self.handshake_template is None:
            print(f"Warning: Could not load {HANDSHAKE_TEMPLATE}")
        if self.stopwatch_template is None:
            print(f"Warning: Could not load {STOPWATCH_TEMPLATE}")
        if self.healing_template is None:
            print(f"Warning: Could not load {HEALING_TEMPLATE}")
        if not self.yellow_soldier_templates:
            print("Warning: No yellow soldier templates loaded!")

        # Position and size from config
        self.icon_x, self.icon_y = HOSPITAL_ICON_POSITION
        self.icon_w, self.icon_h = HOSPITAL_ICON_SIZE
        self.click_x, self.click_y = HOSPITAL_CLICK_POSITION
        self.threshold = HOSPITAL_MATCH_THRESHOLD

    def get_scores(self, frame: np.ndarray) -> dict[str, float]:
        """
        Get all template scores for the hospital position.

        Args:
            frame: BGR numpy array screenshot (4K resolution)

        Returns:
            dict with 'handshake', 'stopwatch', 'healing', 'yellow_soldier' scores (1.0 if template not loaded)
        """
        scores = {'handshake': 1.0, 'stopwatch': 1.0, 'healing': 1.0, 'yellow_soldier': 1.0}

        # Extract ROI at fixed position
        roi = frame[self.icon_y:self.icon_y + self.icon_h,
                    self.icon_x:self.icon_x + self.icon_w]

        if roi.shape[:2] != (self.icon_h, self.icon_w):
            return scores

        # Match templates
        if self.handshake_template is not None:
            result = cv2.matchTemplate(roi, self.handshake_template, cv2.TM_SQDIFF_NORMED)
            scores['handshake'] = result[0, 0]

        if self.stopwatch_template is not None:
            result = cv2.matchTemplate(roi, self.stopwatch_template, cv2.TM_SQDIFF_NORMED)
            scores['stopwatch'] = result[0, 0]

        if self.healing_template is not None:
            result = cv2.matchTemplate(roi, self.healing_template, cv2.TM_SQDIFF_NORMED)
            scores['healing'] = result[0, 0]

        # Match against all yellow soldier variants, use best (lowest) score
        if self.yellow_soldier_templates:
            yellow_scores = [
                cv2.matchTemplate(roi, t, cv2.TM_SQDIFF_NORMED)[0, 0]
                for t in self.yellow_soldier_templates
            ]
            scores['yellow_soldier'] = min(yellow_scores)

        return scores

    def get_state(self, frame: np.ndarray, debug: bool = False) -> tuple[HospitalState, float]:
        """
        Get the current state of the hospital.

        Args:
            frame: BGR numpy array screenshot (4K resolution)
            debug: Enable debug output

        Returns:
            (HospitalState, best_score) tuple
        """
        scores = self.get_scores(frame)

        handshake_score = scores['handshake']
        stopwatch_score = scores['stopwatch']
        healing_score = scores['healing']
        yellow_score = scores['yellow_soldier']

        # Find best match
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
        """
        Format hospital state as a short string for logging.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            String like "H:TRAIN" or "H:HEAL" or "H:WOUND" or "H:IDLE" or "H:?"
        """
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
        """
        Format hospital state with all scores for debugging.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            String like "H:HELP(hs=0.010,s=0.150,h=0.200,y=0.300)"
        """
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
    """
    Convenience function to check hospital state.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        (HospitalState, score) tuple
    """
    return get_matcher().get_state(frame, debug=debug)


def format_hospital_state(frame: np.ndarray) -> str:
    """
    Convenience function to get formatted hospital state string.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        String like "H:HEAL" or "H:WOUND" or "H:IDLE"
    """
    return get_matcher().format_state(frame)


def format_hospital_state_detailed(frame: np.ndarray) -> str:
    """
    Convenience function to get detailed hospital state with scores.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        String like "H:HEAL(h=0.010,y=0.150)"
    """
    return get_matcher().format_state_detailed(frame)
