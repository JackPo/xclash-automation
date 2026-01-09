"""
Multi-read stamina confirmation.

The problem: OCR occasionally misreads stamina values (e.g., reads 23 when it's 5).
Using LAST value in history causes false rally triggers.

Solution: Require 3 readings and use MODE (most common value).
This handles occasional OCR glitches while allowing fast adaptation to stamina changes.
"""
from __future__ import annotations

from collections import Counter


class StaminaReader:
    """
    Multi-read stamina confirmation.

    Usage:
        reader = StaminaReader()

        # In daemon loop:
        confirmed, stamina = reader.add_reading(ocr_value)
        if confirmed:
            # Use stamina value
            reader.reset()  # Reset after triggering action
    """

    REQUIRED_READINGS = 3

    def __init__(self) -> None:
        self.history: list[int] = []

    def add_reading(self, stamina: int | None) -> tuple[bool, int | None]:
        """
        Add a stamina reading and return (confirmed, value).

        Args:
            stamina: OCR-extracted stamina value, or None if extraction failed

        Returns:
            (True, stamina) if 3 readings available (uses mode)
            (False, None) otherwise
        """
        # Invalid reading resets history
        # Cap raised to 500 - stamina can exceed 200 with recovery items
        if stamina is None or not (0 <= stamina <= 500):
            self.history = []
            return False, None

        self.history.append(stamina)

        # Keep only last N readings
        if len(self.history) > self.REQUIRED_READINGS:
            self.history = self.history[-self.REQUIRED_READINGS:]

        # Need 3 readings
        if len(self.history) < self.REQUIRED_READINGS:
            return False, None

        # Use MODE (most common value) - handles occasional OCR glitches
        confirmed = Counter(self.history).most_common(1)[0][0]
        return True, confirmed

    def reset(self) -> None:
        """Clear history after triggering action."""
        self.history = []

    def get_history(self) -> list[int]:
        """Get current history for debugging."""
        return self.history.copy()


# Singleton instance
_reader: StaminaReader | None = None


def get_stamina_reader() -> StaminaReader:
    """Get the singleton StaminaReader instance."""
    global _reader
    if _reader is None:
        _reader = StaminaReader()
    return _reader
