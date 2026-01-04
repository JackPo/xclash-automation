"""
Unit tests for utils/stamina_reader.py

Tests the multi-read stamina confirmation with consistency validation.
"""
import pytest

from utils.stamina_reader import StaminaReader, get_stamina_reader


class TestStaminaReaderBasics:
    """Test basic StaminaReader functionality."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_requires_3_readings_before_confirmation(self, reader: StaminaReader) -> None:
        """Test that exactly 3 readings are required before confirmation."""
        # First reading - should not confirm
        confirmed, value = reader.add_reading(100)
        assert confirmed is False
        assert value is None
        assert len(reader.get_history()) == 1

        # Second reading - should not confirm
        confirmed, value = reader.add_reading(100)
        assert confirmed is False
        assert value is None
        assert len(reader.get_history()) == 2

        # Third reading - should confirm
        confirmed, value = reader.add_reading(100)
        assert confirmed is True
        assert value == 100
        assert len(reader.get_history()) == 3

    def test_mode_calculation_returns_most_common_value(self, reader: StaminaReader) -> None:
        """Test that MODE (most common value) is returned, not last or average."""
        # Add 3 readings where 50 appears twice
        reader.add_reading(50)
        reader.add_reading(55)
        confirmed, value = reader.add_reading(50)

        assert confirmed is True
        assert value == 50  # MODE is 50, not 55 (last) or 51.67 (average)

    def test_mode_with_all_different_values(self, reader: StaminaReader) -> None:
        """Test MODE when all values are different (within variance limit)."""
        reader.add_reading(100)
        reader.add_reading(105)
        confirmed, value = reader.add_reading(102)

        assert confirmed is True
        # When all values are unique, Counter.most_common returns first encountered
        # This is implementation-dependent but should return a valid value
        assert value in [100, 105, 102]


class TestHighVarianceReset:
    """Test that high variance (max-min > 10) resets readings."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_high_variance_resets_history(self, reader: StaminaReader) -> None:
        """Test that variance > 10 resets history to only current reading."""
        # Add two consistent readings
        reader.add_reading(5)
        reader.add_reading(5)
        assert len(reader.get_history()) == 2

        # Add a reading with high variance (23 - 5 = 18 > 10)
        confirmed, value = reader.add_reading(23)

        assert confirmed is False
        assert value is None
        # History should be reset to only the current reading
        assert reader.get_history() == [23]

    def test_variance_exactly_at_threshold(self, reader: StaminaReader) -> None:
        """Test that variance == 10 is acceptable (not reset)."""
        reader.add_reading(90)
        reader.add_reading(95)
        confirmed, value = reader.add_reading(100)  # max-min = 100-90 = 10

        # Should confirm because variance is exactly 10, not > 10
        assert confirmed is True
        assert value in [90, 95, 100]

    def test_variance_just_over_threshold(self, reader: StaminaReader) -> None:
        """Test that variance == 11 triggers reset."""
        reader.add_reading(90)
        reader.add_reading(95)
        confirmed, value = reader.add_reading(101)  # max-min = 101-90 = 11 > 10

        assert confirmed is False
        assert value is None
        assert reader.get_history() == [101]

    def test_recovery_after_variance_reset(self, reader: StaminaReader) -> None:
        """Test that reader can recover after variance reset."""
        # Trigger a variance reset
        reader.add_reading(5)
        reader.add_reading(5)
        reader.add_reading(50)  # High variance - resets to [50]

        # Now add consistent readings
        reader.add_reading(52)
        confirmed, value = reader.add_reading(50)

        assert confirmed is True
        assert value == 50


class TestResetMethod:
    """Test the reset() method."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_reset_clears_all_readings(self, reader: StaminaReader) -> None:
        """Test that reset() clears all history."""
        # Add some readings
        reader.add_reading(100)
        reader.add_reading(100)
        reader.add_reading(100)
        assert len(reader.get_history()) == 3

        # Reset
        reader.reset()

        assert len(reader.get_history()) == 0
        assert reader.get_history() == []

    def test_reset_requires_fresh_readings_for_confirmation(self, reader: StaminaReader) -> None:
        """Test that after reset, 3 new readings are required."""
        # Get confirmation
        reader.add_reading(100)
        reader.add_reading(100)
        confirmed, _ = reader.add_reading(100)
        assert confirmed is True

        # Reset and verify new readings required
        reader.reset()

        confirmed, value = reader.add_reading(200)
        assert confirmed is False
        assert value is None

        confirmed, value = reader.add_reading(200)
        assert confirmed is False
        assert value is None

        confirmed, value = reader.add_reading(200)
        assert confirmed is True
        assert value == 200


class TestConsistentReadings:
    """Test consistent readings confirmation scenarios."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_three_identical_readings_confirm(self, reader: StaminaReader) -> None:
        """Test that 3 identical readings confirm correctly."""
        reader.add_reading(118)
        reader.add_reading(118)
        confirmed, value = reader.add_reading(118)

        assert confirmed is True
        assert value == 118

    def test_consistent_readings_with_slight_variance(self, reader: StaminaReader) -> None:
        """Test that readings with small variance (<=10) confirm."""
        reader.add_reading(115)
        reader.add_reading(118)
        confirmed, value = reader.add_reading(120)  # max-min = 5

        assert confirmed is True
        # MODE should be one of these values
        assert value in [115, 118, 120]

    def test_sliding_window_keeps_last_3_readings(self, reader: StaminaReader) -> None:
        """Test that only the last 3 readings are kept."""
        # Use values within variance threshold (max-min <= 10)
        reader.add_reading(100)  # Will be dropped after 4th reading
        reader.add_reading(102)
        reader.add_reading(105)
        reader.add_reading(108)  # 4th reading, 100 should be dropped

        # Only last 3 should be in history
        assert len(reader.get_history()) == 3
        assert 100 not in reader.get_history()
        assert reader.get_history() == [102, 105, 108]

    def test_continuous_readings_after_confirmation(self, reader: StaminaReader) -> None:
        """Test that readings continue to confirm after initial confirmation."""
        reader.add_reading(100)
        reader.add_reading(100)
        confirmed1, value1 = reader.add_reading(100)
        assert confirmed1 is True

        # Add another reading - should still confirm (sliding window)
        confirmed2, value2 = reader.add_reading(100)
        assert confirmed2 is True
        assert value2 == 100


class TestInvalidReadings:
    """Test handling of invalid readings (None and out-of-range)."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_none_reading_resets_history(self, reader: StaminaReader) -> None:
        """Test that None reading resets history."""
        reader.add_reading(100)
        reader.add_reading(100)
        assert len(reader.get_history()) == 2

        confirmed, value = reader.add_reading(None)

        assert confirmed is False
        assert value is None
        assert len(reader.get_history()) == 0

    def test_negative_reading_resets_history(self, reader: StaminaReader) -> None:
        """Test that negative stamina resets history."""
        reader.add_reading(100)
        reader.add_reading(100)

        confirmed, value = reader.add_reading(-1)

        assert confirmed is False
        assert value is None
        assert len(reader.get_history()) == 0

    def test_over_500_reading_resets_history(self, reader: StaminaReader) -> None:
        """Test that stamina > 500 resets history."""
        reader.add_reading(100)
        reader.add_reading(100)

        confirmed, value = reader.add_reading(501)

        assert confirmed is False
        assert value is None
        assert len(reader.get_history()) == 0

    def test_boundary_value_zero_is_valid(self, reader: StaminaReader) -> None:
        """Test that stamina = 0 is valid."""
        reader.add_reading(0)
        reader.add_reading(0)
        confirmed, value = reader.add_reading(0)

        assert confirmed is True
        assert value == 0

    def test_boundary_value_500_is_valid(self, reader: StaminaReader) -> None:
        """Test that stamina = 500 is valid (max with recovery items)."""
        reader.add_reading(500)
        reader.add_reading(500)
        confirmed, value = reader.add_reading(500)

        assert confirmed is True
        assert value == 500


class TestGetHistory:
    """Test the get_history() method."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_get_history_returns_copy(self, reader: StaminaReader) -> None:
        """Test that get_history returns a copy, not the internal list."""
        reader.add_reading(100)
        history = reader.get_history()
        history.append(999)  # Modify the returned copy

        # Internal history should be unchanged
        assert 999 not in reader.get_history()
        assert reader.get_history() == [100]

    def test_get_history_empty_initially(self, reader: StaminaReader) -> None:
        """Test that history is empty on fresh reader."""
        assert reader.get_history() == []


class TestSingleton:
    """Test the singleton get_stamina_reader() function."""

    def test_singleton_returns_same_instance(self) -> None:
        """Test that get_stamina_reader returns the same instance."""
        reader1 = get_stamina_reader()
        reader2 = get_stamina_reader()

        assert reader1 is reader2

    def test_singleton_persists_state(self) -> None:
        """Test that singleton maintains state between calls."""
        reader = get_stamina_reader()
        reader.reset()  # Clean state

        reader.add_reading(50)

        # Get again and check state persists
        same_reader = get_stamina_reader()
        assert same_reader.get_history() == [50]

        # Clean up for other tests
        reader.reset()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def reader(self) -> StaminaReader:
        """Create a fresh StaminaReader instance for each test."""
        return StaminaReader()

    def test_mode_with_tie_returns_valid_value(self, reader: StaminaReader) -> None:
        """Test MODE when there's a tie (each value appears once)."""
        reader.add_reading(100)
        reader.add_reading(105)
        confirmed, value = reader.add_reading(108)

        assert confirmed is True
        # Any of the three values is acceptable
        assert value in [100, 105, 108]

    def test_rapid_variance_fluctuations(self, reader: StaminaReader) -> None:
        """Test behavior with rapid variance fluctuations."""
        # High variance triggers reset
        reader.add_reading(10)
        reader.add_reading(10)
        reader.add_reading(100)  # Resets to [100]

        # Add more readings
        reader.add_reading(100)
        confirmed, value = reader.add_reading(100)

        assert confirmed is True
        assert value == 100

    def test_constants_are_correct(self, reader: StaminaReader) -> None:
        """Verify class constants match documented values."""
        assert StaminaReader.REQUIRED_READINGS == 3
        assert StaminaReader.MAX_VARIANCE == 10
