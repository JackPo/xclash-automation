"""
Unit tests for utils/adb_helper.py.

Tests ADBHelper initialization, ADB command execution, tap/swipe methods,
screen size parsing, screenshot capture, and connection management.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest

from utils.adb_helper import ADBHelper

if TYPE_CHECKING:
    from unittest.mock import Mock


# =============================================================================
# Initialization Tests
# =============================================================================


class TestADBHelperInit:
    """Test ADBHelper initialization."""

    def test_init_with_auto_connect_false(self):
        """Test initialization without auto-connect."""
        with patch.object(ADBHelper, 'ensure_connected') as mock_ensure:
            adb = ADBHelper(auto_connect=False)

            assert adb.device is None
            assert adb._on_action is None
            mock_ensure.assert_not_called()

    def test_init_with_auto_connect_true(self):
        """Test initialization with auto-connect (default)."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True) as mock_ensure:
            adb = ADBHelper(auto_connect=True)

            mock_ensure.assert_called_once()

    def test_init_with_on_action_callback(self):
        """Test initialization with on_action callback."""
        callback = MagicMock()
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            adb = ADBHelper(on_action=callback)

            assert adb._on_action == callback

    def test_adb_path_constant(self):
        """Test ADB_PATH is set correctly."""
        assert ADBHelper.ADB_PATH == r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"


# =============================================================================
# _run_adb Tests
# =============================================================================


class TestRunAdb:
    """Test _run_adb method for executing ADB commands."""

    @pytest.fixture
    def adb(self) -> ADBHelper:
        """Create ADBHelper without auto-connect."""
        with patch.object(ADBHelper, 'ensure_connected'):
            helper = ADBHelper(auto_connect=False)
            helper.device = "emulator-5554"
            return helper

    def test_run_adb_with_device(self, adb: ADBHelper):
        """Test _run_adb includes device flag when device is set."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="output",
                stderr="",
                returncode=0
            )

            success, stdout, stderr = adb._run_adb(["shell", "echo", "test"])

            assert success is True
            assert stdout == "output"
            mock_run.assert_called_once()

            # Verify command includes -s device
            call_args = mock_run.call_args[0][0]
            assert call_args == [
                ADBHelper.ADB_PATH,
                "-s", "emulator-5554",
                "shell", "echo", "test"
            ]

    def test_run_adb_without_device(self):
        """Test _run_adb works without device set."""
        with patch.object(ADBHelper, 'ensure_connected'):
            adb = ADBHelper(auto_connect=False)
            adb.device = None  # No device set

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="output",
                stderr="",
                returncode=0
            )

            success, stdout, stderr = adb._run_adb(["devices"])

            # Command should NOT include -s flag
            call_args = mock_run.call_args[0][0]
            assert call_args == [ADBHelper.ADB_PATH, "devices"]

    def test_run_adb_capture_output_false(self, adb: ADBHelper):
        """Test _run_adb with capture_output=False."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            success, stdout, stderr = adb._run_adb(
                ["kill-server"],
                capture_output=False
            )

            assert success is True
            assert stdout == ""
            assert stderr == ""

    def test_run_adb_handles_called_process_error(self, adb: ADBHelper):
        """Test _run_adb handles CalledProcessError gracefully."""
        with patch('subprocess.run') as mock_run:
            error = subprocess.CalledProcessError(1, "adb")
            error.stdout = "stdout content"
            error.stderr = "stderr content"
            mock_run.side_effect = error

            success, stdout, stderr = adb._run_adb(["shell", "bad_command"])

            assert success is False
            assert stdout == "stdout content"
            assert stderr == "stderr content"

    def test_run_adb_handles_error_without_stdout(self, adb: ADBHelper):
        """Test _run_adb handles CalledProcessError without stdout/stderr."""
        with patch('subprocess.run') as mock_run:
            error = subprocess.CalledProcessError(1, "adb")
            error.stdout = None
            error.stderr = None
            mock_run.side_effect = error

            success, stdout, stderr = adb._run_adb(["shell", "bad_command"])

            assert success is False
            assert stdout == ""


# =============================================================================
# tap Tests
# =============================================================================


class TestTap:
    """Test tap method."""

    @pytest.fixture
    def connected_adb(self) -> ADBHelper:
        """Create connected ADBHelper."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            helper = ADBHelper(auto_connect=False)
            helper.device = "emulator-5554"
            return helper

    def test_tap_calls_correct_adb_command(self, connected_adb: ADBHelper):
        """Test tap executes correct ADB shell input tap command."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                connected_adb.tap(1920, 1080)

                mock_run.assert_called_once_with([
                    "shell", "input", "tap", "1920", "1080"
                ])

    def test_tap_with_4k_coordinates(self, connected_adb: ADBHelper):
        """Test tap with 4K resolution coordinates."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                connected_adb.tap(3840, 2160)

                mock_run.assert_called_once_with([
                    "shell", "input", "tap", "3840", "2160"
                ])

    def test_tap_raises_when_not_connected(self):
        """Test tap raises RuntimeError when not connected."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=False):
            adb = ADBHelper(auto_connect=False)

            with pytest.raises(RuntimeError, match="No ADB device connected"):
                adb.tap(100, 100)

    def test_tap_calls_on_action_callback(self, connected_adb: ADBHelper):
        """Test tap invokes on_action callback before action."""
        callback = MagicMock()
        connected_adb._on_action = callback

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb'):
                connected_adb.tap(100, 100)

                callback.assert_called_once()

    def test_tap_without_on_action_callback(self, connected_adb: ADBHelper):
        """Test tap works without on_action callback."""
        connected_adb._on_action = None

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                # Should not raise
                connected_adb.tap(100, 100)

                mock_run.assert_called_once()


# =============================================================================
# swipe Tests
# =============================================================================


class TestSwipe:
    """Test swipe method."""

    @pytest.fixture
    def connected_adb(self) -> ADBHelper:
        """Create connected ADBHelper."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            helper = ADBHelper(auto_connect=False)
            helper.device = "emulator-5554"
            return helper

    def test_swipe_calls_correct_adb_command(self, connected_adb: ADBHelper):
        """Test swipe executes correct ADB shell input swipe command."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                connected_adb.swipe(100, 200, 300, 400)

                mock_run.assert_called_once_with([
                    "shell", "input", "swipe",
                    "100", "200", "300", "400", "300"  # Default duration
                ])

    def test_swipe_with_custom_duration(self, connected_adb: ADBHelper):
        """Test swipe with custom duration."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                connected_adb.swipe(0, 0, 500, 500, duration=500)

                mock_run.assert_called_once_with([
                    "shell", "input", "swipe",
                    "0", "0", "500", "500", "500"
                ])

    def test_swipe_raises_when_not_connected(self):
        """Test swipe raises RuntimeError when not connected."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=False):
            adb = ADBHelper(auto_connect=False)

            with pytest.raises(RuntimeError, match="No ADB device connected"):
                adb.swipe(0, 0, 100, 100)

    def test_swipe_calls_on_action_callback(self, connected_adb: ADBHelper):
        """Test swipe invokes on_action callback before action."""
        callback = MagicMock()
        connected_adb._on_action = callback

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb'):
                connected_adb.swipe(0, 0, 100, 100)

                callback.assert_called_once()

    def test_swipe_4k_screen_edge_to_edge(self, connected_adb: ADBHelper):
        """Test swipe across entire 4K screen."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                connected_adb.swipe(0, 1080, 3840, 1080, duration=1000)

                mock_run.assert_called_once_with([
                    "shell", "input", "swipe",
                    "0", "1080", "3840", "1080", "1000"
                ])


# =============================================================================
# get_screen_size Tests
# =============================================================================


class TestGetScreenSize:
    """Test get_screen_size method."""

    @pytest.fixture
    def connected_adb(self) -> ADBHelper:
        """Create connected ADBHelper."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            helper = ADBHelper(auto_connect=False)
            helper.device = "emulator-5554"
            return helper

    def test_get_screen_size_parses_physical_size(self, connected_adb: ADBHelper):
        """Test parsing 'Physical size: WxH' format."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                mock_run.return_value = (True, "Physical size: 3840x2160\n", "")

                result = connected_adb.get_screen_size()

                assert result == (3840, 2160)

    def test_get_screen_size_parses_override_size(self, connected_adb: ADBHelper):
        """Test parsing 'Override size: WxH' format returns first match."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                # When both physical and override are present, the function
                # returns the first 'size:' match (physical size)
                mock_run.return_value = (
                    True,
                    "Physical size: 1920x1080\nOverride size: 3840x2160\n",
                    ""
                )

                result = connected_adb.get_screen_size()

                # Returns first 'size:' match (Physical size)
                assert result == (1920, 1080)

    def test_get_screen_size_parses_1080p(self, connected_adb: ADBHelper):
        """Test parsing 1080p resolution."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                mock_run.return_value = (True, "Physical size: 1920x1080\n", "")

                result = connected_adb.get_screen_size()

                assert result == (1920, 1080)

    def test_get_screen_size_returns_none_on_failure(self, connected_adb: ADBHelper):
        """Test returns None when ADB command fails."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                mock_run.return_value = (False, "", "error")

                result = connected_adb.get_screen_size()

                assert result is None

    def test_get_screen_size_returns_none_on_parse_failure(self, connected_adb: ADBHelper):
        """Test returns None when output cannot be parsed."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                mock_run.return_value = (True, "unexpected output\n", "")

                result = connected_adb.get_screen_size()

                assert result is None

    def test_get_screen_size_returns_none_when_not_connected(self):
        """Test returns None when not connected."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=False):
            adb = ADBHelper(auto_connect=False)

            result = adb.get_screen_size()

            assert result is None

    def test_get_screen_size_handles_malformed_resolution(self, connected_adb: ADBHelper):
        """Test handles malformed resolution gracefully."""
        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch.object(connected_adb, '_run_adb') as mock_run:
                mock_run.return_value = (True, "Physical size: invalid\n", "")

                result = connected_adb.get_screen_size()

                assert result is None


# =============================================================================
# take_screenshot Tests
# =============================================================================


class TestTakeScreenshot:
    """Test take_screenshot method."""

    @pytest.fixture
    def connected_adb(self) -> ADBHelper:
        """Create connected ADBHelper."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            helper = ADBHelper(auto_connect=False)
            helper.device = "emulator-5554"
            return helper

    def test_take_screenshot_captures_png_data(self, connected_adb: ADBHelper, tmp_path: Path):
        """Test screenshot captures and saves PNG data."""
        output_path = tmp_path / "screenshot.png"
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Fake PNG header

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=png_data,
                    stderr=b"",
                    returncode=0
                )

                result = connected_adb.take_screenshot(output_path)

                assert result == str(output_path)
                assert output_path.exists()
                assert output_path.read_bytes() == png_data

    def test_take_screenshot_uses_exec_out_screencap(self, connected_adb: ADBHelper, tmp_path: Path):
        """Test screenshot uses exec-out screencap command."""
        output_path = tmp_path / "screenshot.png"

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=b'\x89PNG\r\n\x1a\n',
                    stderr=b"",
                    returncode=0
                )

                connected_adb.take_screenshot(output_path)

                # Verify command
                call_args = mock_run.call_args[0][0]
                assert call_args == [
                    ADBHelper.ADB_PATH,
                    "-s", "emulator-5554",
                    "exec-out", "screencap", "-p"
                ]

    def test_take_screenshot_raises_when_not_connected(self, tmp_path: Path):
        """Test raises RuntimeError when not connected."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=False):
            adb = ADBHelper(auto_connect=False)

            with pytest.raises(RuntimeError, match="No ADB device connected"):
                adb.take_screenshot(tmp_path / "screenshot.png")

    def test_take_screenshot_raises_on_empty_data(self, connected_adb: ADBHelper, tmp_path: Path):
        """Test raises RuntimeError when screenshot returns empty data."""
        output_path = tmp_path / "screenshot.png"

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=b"",  # Empty data
                    stderr=b"",
                    returncode=0
                )

                with pytest.raises(RuntimeError, match="Screenshot capture returned empty data"):
                    connected_adb.take_screenshot(output_path)

    def test_take_screenshot_raises_on_subprocess_error(
        self, connected_adb: ADBHelper, tmp_path: Path
    ):
        """Test raises RuntimeError when subprocess fails."""
        output_path = tmp_path / "screenshot.png"

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                error = subprocess.CalledProcessError(1, "adb")
                error.stderr = b"device not found"
                mock_run.side_effect = error

                with pytest.raises(RuntimeError, match="Screenshot capture failed"):
                    connected_adb.take_screenshot(output_path)

    def test_take_screenshot_accepts_path_object(self, connected_adb: ADBHelper, tmp_path: Path):
        """Test screenshot accepts Path object."""
        output_path = tmp_path / "screenshot.png"

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=b'\x89PNG\r\n\x1a\n',
                    stderr=b"",
                    returncode=0
                )

                result = connected_adb.take_screenshot(output_path)

                assert result == str(output_path)

    def test_take_screenshot_accepts_string_path(self, connected_adb: ADBHelper, tmp_path: Path):
        """Test screenshot accepts string path."""
        output_path = str(tmp_path / "screenshot.png")

        with patch.object(connected_adb, 'ensure_connected', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=b'\x89PNG\r\n\x1a\n',
                    stderr=b"",
                    returncode=0
                )

                result = connected_adb.take_screenshot(output_path)

                assert result == output_path


# =============================================================================
# ensure_connected Tests
# =============================================================================


class TestEnsureConnected:
    """Test ensure_connected method."""

    def test_ensure_connected_returns_true_when_device_online(self):
        """Test returns True when device is already connected and online."""
        with patch.object(ADBHelper, 'ensure_connected'):
            adb = ADBHelper(auto_connect=False)
            adb.device = "emulator-5554"

        with patch.object(adb, '_run_adb') as mock_run:
            mock_run.return_value = (True, "device\n", "")

            result = adb.ensure_connected()

            assert result is True
            # Verify get-state was called
            mock_run.assert_called_with(["get-state"])

    def test_ensure_connected_finds_new_device(self):
        """Test finds new device when none is set."""
        with patch.object(ADBHelper, 'ensure_connected'):
            adb = ADBHelper(auto_connect=False)
            adb.device = None

        with patch.object(adb, 'find_device', return_value="emulator-5554") as mock_find:
            result = adb.ensure_connected()

            assert result is True
            assert adb.device == "emulator-5554"
            mock_find.assert_called_once()

    def test_ensure_connected_reconnects_when_device_offline(self):
        """Test reconnects when device goes offline."""
        with patch.object(ADBHelper, 'ensure_connected'):
            adb = ADBHelper(auto_connect=False)
            adb.device = "emulator-5554"

        with patch.object(adb, '_run_adb') as mock_run:
            # Device offline
            mock_run.return_value = (True, "offline\n", "")

            with patch.object(adb, 'find_device', return_value="emulator-5556") as mock_find:
                result = adb.ensure_connected()

                assert result is True
                assert adb.device == "emulator-5556"
                mock_find.assert_called_once()

    def test_ensure_connected_returns_false_when_no_device_found(self):
        """Test returns False when no device can be found."""
        with patch.object(ADBHelper, 'ensure_connected'):
            adb = ADBHelper(auto_connect=False)
            adb.device = None

        with patch.object(adb, 'find_device', return_value=None):
            result = adb.ensure_connected()

            assert result is False


# =============================================================================
# find_device Tests
# =============================================================================


class TestFindDevice:
    """Test find_device method."""

    @pytest.fixture
    def adb(self) -> ADBHelper:
        """Create ADBHelper without auto-connect."""
        with patch.object(ADBHelper, 'ensure_connected'):
            return ADBHelper(auto_connect=False)

    def test_find_device_returns_emulator(self, adb: ADBHelper):
        """Test finds emulator-XXXX device."""
        with patch.object(adb, '_run_adb') as mock_run:
            # First calls: kill-server, start-server
            # Then devices call
            mock_run.side_effect = [
                (True, "", ""),  # kill-server
                (True, "", ""),  # start-server
                (True, "List of devices attached\nemulator-5554\tdevice\n", ""),  # devices
            ]

            with patch('time.sleep'):  # Skip sleeps
                result = adb.find_device()

            assert result == "emulator-5554"

    def test_find_device_prefers_emulator_over_ip(self, adb: ADBHelper):
        """Test prefers emulator-XXXX over IP connections."""
        with patch.object(adb, '_run_adb') as mock_run:
            mock_run.side_effect = [
                (True, "", ""),  # kill-server
                (True, "", ""),  # start-server
                (True, "List of devices attached\n127.0.0.1:5555\tdevice\nemulator-5554\tdevice\n", ""),
            ]

            with patch('time.sleep'):
                result = adb.find_device()

            assert result == "emulator-5554"

    def test_find_device_falls_back_to_ip(self, adb: ADBHelper):
        """Test falls back to IP connection when no emulator found."""
        with patch.object(adb, '_run_adb') as mock_run:
            mock_run.side_effect = [
                (True, "", ""),  # kill-server
                (True, "", ""),  # start-server
                (True, "List of devices attached\n", ""),  # No emulator
                (True, "", ""),  # connect 127.0.0.1:5556
                (True, "List of devices attached\n127.0.0.1:5556\tdevice\n", ""),  # devices
            ]

            with patch('time.sleep'):
                result = adb.find_device()

            assert result == "127.0.0.1:5556"

    def test_find_device_returns_none_when_no_device(self, adb: ADBHelper):
        """Test returns None when no device found."""
        with patch.object(adb, '_run_adb') as mock_run:
            # All attempts fail
            mock_run.return_value = (True, "List of devices attached\n", "")

            with patch('time.sleep'):
                result = adb.find_device()

            assert result is None

    def test_find_device_restarts_adb_server(self, adb: ADBHelper):
        """Test restarts ADB server before searching."""
        with patch.object(adb, '_run_adb') as mock_run:
            mock_run.side_effect = [
                (True, "", ""),  # kill-server
                (True, "", ""),  # start-server
                (True, "List of devices attached\nemulator-5554\tdevice\n", ""),
            ]

            with patch('time.sleep'):
                adb.find_device()

            # Verify kill-server and start-server were called
            calls = mock_run.call_args_list
            assert calls[0] == call(["kill-server"], capture_output=False)
            assert calls[1] == call(["start-server"], capture_output=False)


# =============================================================================
# Edge Cases and Integration-like Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_tap_with_zero_coordinates(self):
        """Test tap at origin (0, 0)."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            adb = ADBHelper(auto_connect=False)
            adb.device = "emulator-5554"

        with patch.object(adb, '_run_adb') as mock_run:
            with patch.object(adb, 'ensure_connected', return_value=True):
                adb.tap(0, 0)

                mock_run.assert_called_once_with([
                    "shell", "input", "tap", "0", "0"
                ])

    def test_swipe_with_zero_duration(self):
        """Test swipe with zero duration."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            adb = ADBHelper(auto_connect=False)
            adb.device = "emulator-5554"

        with patch.object(adb, '_run_adb') as mock_run:
            with patch.object(adb, 'ensure_connected', return_value=True):
                adb.swipe(100, 100, 200, 200, duration=0)

                mock_run.assert_called_once_with([
                    "shell", "input", "swipe",
                    "100", "100", "200", "200", "0"
                ])

    def test_multiple_taps_in_sequence(self):
        """Test multiple consecutive taps."""
        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            adb = ADBHelper(auto_connect=False)
            adb.device = "emulator-5554"

        with patch.object(adb, '_run_adb') as mock_run:
            with patch.object(adb, 'ensure_connected', return_value=True):
                adb.tap(100, 100)
                adb.tap(200, 200)
                adb.tap(300, 300)

                assert mock_run.call_count == 3

    def test_callback_called_before_adb_command(self):
        """Test on_action callback is called before the ADB command."""
        call_order = []

        def callback():
            call_order.append('callback')

        with patch.object(ADBHelper, 'ensure_connected', return_value=True):
            adb = ADBHelper(auto_connect=False, on_action=callback)
            adb.device = "emulator-5554"

        def record_adb_call(*args, **kwargs):
            call_order.append('adb')
            return (True, "", "")

        with patch.object(adb, '_run_adb', side_effect=record_adb_call):
            with patch.object(adb, 'ensure_connected', return_value=True):
                adb.tap(100, 100)

        assert call_order == ['callback', 'adb']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
