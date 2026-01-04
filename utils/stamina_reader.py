"""
Multi-read stamina confirmation with consistency validation.

The problem: OCR occasionally misreads stamina values (e.g., reads 23 when it's 5).
Using LAST value in history causes false rally triggers.

Solution: Require 3 consistent readings and use MODE (most common value).
If readings vary too much (e.g., [5, 5, 23]), reset and start fresh.
"""
from __future__ import annotations

from collections import Counter


class StaminaReader:
    """
    Multi-read stamina confirmation with consistency validation.

    Usage:
        reader = StaminaReader()

        # In daemon loop:
        confirmed, stamina = reader.add_reading(ocr_value)
        if confirmed:
            # Use stamina value
            reader.reset()  # Reset after triggering action
    """

    REQUIRED_READINGS = 3
    MAX_VARIANCE = 10  # Max allowed difference between min/max

    def __init__(self) -> None:
        self.history: list[int] = []

    def add_reading(self, stamina: int | None) -> tuple[bool, int | None]:
        """
        Add a stamina reading and return (confirmed, value).

        Args:
            stamina: OCR-extracted stamina value, or None if extraction failed

        Returns:
            (True, stamina) if 3 consistent readings confirm the value
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

        # Check consistency of ALL values
        min_val, max_val = min(self.history), max(self.history)
        if max_val - min_val > self.MAX_VARIANCE:
            # Values too spread - reset and start fresh with current reading
            self.history = [stamina]
            return False, None

        # Use MODE (most common value)
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
