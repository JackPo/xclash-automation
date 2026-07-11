"""
Multi-read stamina confirmation.

The problem: OCR occasionally misreads stamina values - both transient glitches
(reads 23 when it's 5) and GLUED-DIGIT errors (reads 511 when it's 11, 910 when
it's 9) that pass the 0..MAX_VALID range check.

Solution:
1. Require 3 readings and use MODE (most common value). Callers MUST feed one
   reading per REAL OCR (never echo a cached value into add_reading - echoing
   turns one misread into an instant self-confirmation; that burned a
   500-stamina stockpile on 2026-07-11).
2. Plausibility guard: a big sudden INCREASE (>=3x last confirmed AND
   >= last+JUMP_MIN) is quarantined until the NEXT fresh reading agrees within
   +/-JUMP_AGREE. Real jumps (recovery items +50/+100/+500) repeat on the next
   read; glued-digit garbage doesn't. Decreases are always accepted - spending
   is instant and any drop is plausible.
"""
from __future__ import annotations

from collections import Counter

try:
    from config import STAMINA_OCR_MAX_VALID as MAX_VALID
except ImportError:
    MAX_VALID = 2500


class StaminaReader:
    """
    Multi-read stamina confirmation with implausible-jump quarantine.

    Usage:
        reader = StaminaReader()
        confirmed, stamina = reader.add_reading(fresh_ocr_value)
        if reader.last_event:      # instrumentation for the daemon log
            logger.info(f"[STAMINA] {reader.last_event}")
    """

    REQUIRED_READINGS = 3
    JUMP_FACTOR = 3      # increase >= 3x last confirmed ...
    JUMP_MIN = 150       # ... AND >= last+150 => quarantine
    JUMP_AGREE = 5       # next read within +/-5 confirms a real jump

    def __init__(self) -> None:
        self.history: list[int] = []
        self.last_confirmed: int | None = None
        self._pending_jump: int | None = None
        self.last_event: str | None = None  # set per add_reading for logging

    def _is_implausible_jump(self, stamina: int) -> bool:
        if self.last_confirmed is None:
            return False
        return (
            stamina >= self.last_confirmed * self.JUMP_FACTOR
            and stamina >= self.last_confirmed + self.JUMP_MIN
        )

    def add_reading(self, stamina: int | None) -> tuple[bool, int | None]:
        """
        Add ONE FRESH OCR reading and return (confirmed, value).

        Returns:
            (True, mode_value) once REQUIRED_READINGS accepted readings exist
            (False, None) otherwise
        """
        self.last_event = None

        # Invalid reading resets history. Real stamina can reach ~2000 with
        # recovery items; reject only clear OCR garbage above MAX_VALID.
        if stamina is None or not (0 <= stamina <= MAX_VALID):
            self.history = []
            if stamina is not None:
                self.last_event = f"out-of-bounds read {stamina} discarded"
            return False, None

        # Implausible-jump quarantine (glued-digit misreads like 11 -> 511).
        if self._is_implausible_jump(stamina):
            if self._pending_jump is not None and abs(stamina - self._pending_jump) <= self.JUMP_AGREE:
                # Second independent read agrees - it's a REAL jump (items).
                self.last_event = (
                    f"jump {self.last_confirmed} -> {stamina} confirmed by repeat read"
                )
                self._pending_jump = None
                self.history = [stamina]  # restart history at the new level
                # Trust the new level as the plausibility baseline, else every
                # subsequent read at the new level re-quarantines.
                self.last_confirmed = stamina
                return False, None
            self._pending_jump = stamina
            self.last_event = (
                f"quarantined implausible jump {self.last_confirmed} -> {stamina}, awaiting agreement"
            )
            return False, None

        # Normal reading clears any pending quarantine (the jump didn't repeat).
        if self._pending_jump is not None:
            self.last_event = f"quarantined {self._pending_jump} dropped (next read was {stamina})"
            self._pending_jump = None

        self.history.append(stamina)

        # Keep only last N readings
        if len(self.history) > self.REQUIRED_READINGS:
            self.history = self.history[-self.REQUIRED_READINGS:]

        # Need 3 readings
        if len(self.history) < self.REQUIRED_READINGS:
            return False, None

        # Use MODE (most common value) - handles occasional OCR glitches
        confirmed = Counter(self.history).most_common(1)[0][0]
        if confirmed != self.last_confirmed:
            self.last_event = f"confirmed {confirmed} (reads={self.history})"
        self.last_confirmed = confirmed
        return True, confirmed

    def reset(self) -> None:
        """Clear history after triggering action (keeps last_confirmed for the guard)."""
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
