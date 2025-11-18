"""
Action chain runner for template-based automation workflows.

Provides a generalizable framework for:
- Capturing screenshots once and running multiple template matches
- Executing action sequences (find → click → wait → find next)
- Logging results for cronjob debugging

Usage:
    from action_chain_runner import ActionChainRunner, ActionStep
    from adb_helper import ADBHelper
    from handshake_icon_matcher import HandshakeIconMatcher

    adb = ADBHelper()
    runner = ActionChainRunner(adb)

    # Register matchers
    runner.register_matcher("handshake", HandshakeIconMatcher())

    # Define action chain
    chain = [
        ActionStep(action="find", matcher="handshake", click_on_match=True),
        ActionStep(action="wait", duration=0.5),
    ]

    # Execute
    success = runner.execute_chain(chain)
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any
from enum import Enum

import cv2
import numpy as np


class ActionType(Enum):
    """Supported action types in chain."""
    FIND = "find"
    CLICK = "click"
    WAIT = "wait"


@dataclass
class ActionStep:
    """
    Represents a single step in an action chain.

    Examples:
        # Find and click if found
        ActionStep(action="find", matcher="handshake", click_on_match=True)

        # Wait 0.5 seconds
        ActionStep(action="wait", duration=0.5)

        # Find without clicking
        ActionStep(action="find", matcher="handshake", click_on_match=False)
    """
    action: str  # "find", "click", "wait"
    matcher: Optional[str] = None  # Matcher name (for "find" actions)
    click_on_match: bool = False  # Whether to click if match found
    duration: float = 0.0  # Wait duration in seconds (for "wait" actions)
    required: bool = False  # If True, chain stops if this step fails


@dataclass
class ActionResult:
    """Result of executing a single action step."""
    step: ActionStep
    success: bool
    message: str
    match_score: Optional[float] = None
    match_location: Optional[tuple] = None


class ActionChainRunner:
    """
    Executes template matching action chains with a single screenshot.

    Features:
    - Single screenshot capture for all template matches
    - Sequential action execution with conditional logic
    - Logging for debugging cronjob runs
    - Extensible matcher registry
    """

    def __init__(
        self,
        adb_helper,
        screenshot_path: Optional[Path] = None,
        log_file: Optional[Path] = None,
    ):
        """
        Initialize action chain runner.

        Args:
            adb_helper: ADBHelper instance for screenshots and clicking
            screenshot_path: Path to save screenshots (default: temp_action_chain.png)
            log_file: Path to log file (default: action_chain.log)
        """
        self.adb = adb_helper
        self.screenshot_path = screenshot_path or Path("temp_action_chain.png")
        self.matchers: Dict[str, Any] = {}
        self.current_frame: Optional[np.ndarray] = None

        # Setup logging
        log_path = log_file or Path("action_chain.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def register_matcher(self, name: str, matcher) -> None:
        """
        Register a template matcher.

        Args:
            name: Identifier for this matcher (used in ActionStep)
            matcher: Matcher instance (must have find() method)
        """
        self.matchers[name] = matcher
        self.logger.info(f"Registered matcher: {name}")

    def capture_screenshot(self) -> bool:
        """
        Capture screenshot and load into memory.

        Returns:
            True if successful, False otherwise
        """
        try:
            full_path, _ = self.adb.take_screenshot(
                str(self.screenshot_path),
                scale_for_llm=False
            )
            self.current_frame = cv2.imread(full_path)

            if self.current_frame is None:
                self.logger.error(f"Failed to load screenshot: {full_path}")
                return False

            self.logger.info(f"Screenshot captured: {self.current_frame.shape}")
            return True

        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {e}")
            return False

    def execute_chain(
        self,
        steps: list[ActionStep],
        capture_screenshot: bool = True
    ) -> tuple[bool, list[ActionResult]]:
        """
        Execute action chain.

        Args:
            steps: List of ActionStep objects to execute
            capture_screenshot: If True, capture new screenshot before executing

        Returns:
            Tuple of (overall_success, list of ActionResult)
        """
        results = []

        if capture_screenshot:
            if not self.capture_screenshot():
                return False, results

        self.logger.info(f"Executing action chain with {len(steps)} steps")

        for i, step in enumerate(steps):
            self.logger.info(f"Step {i+1}/{len(steps)}: {step.action}")

            result = self._execute_step(step)
            results.append(result)

            if not result.success and step.required:
                self.logger.warning(f"Required step failed, stopping chain: {result.message}")
                return False, results

        overall_success = all(r.success for r in results if r.step.required)
        self.logger.info(f"Chain completed: {'SUCCESS' if overall_success else 'PARTIAL'}")

        return overall_success, results

    def _execute_step(self, step: ActionStep) -> ActionResult:
        """Execute a single action step."""

        if step.action == "find":
            return self._execute_find(step)
        elif step.action == "wait":
            return self._execute_wait(step)
        elif step.action == "click":
            return self._execute_click(step)
        else:
            return ActionResult(
                step=step,
                success=False,
                message=f"Unknown action type: {step.action}"
            )

    def _execute_find(self, step: ActionStep) -> ActionResult:
        """Execute template matching step."""

        if step.matcher not in self.matchers:
            return ActionResult(
                step=step,
                success=False,
                message=f"Matcher not registered: {step.matcher}"
            )

        if self.current_frame is None:
            return ActionResult(
                step=step,
                success=False,
                message="No screenshot loaded"
            )

        try:
            matcher = self.matchers[step.matcher]
            match = matcher.find(self.current_frame)

            if match is None:
                return ActionResult(
                    step=step,
                    success=False,
                    message=f"No match found for {step.matcher}"
                )

            self.logger.info(
                f"Found {step.matcher}: score={match.score:.3f}, "
                f"center={match.center}"
            )

            # Click if requested
            if step.click_on_match:
                matcher.click_center(self.adb, match)
                self.logger.info(f"Clicked at {match.center}")

            return ActionResult(
                step=step,
                success=True,
                message=f"Matched {step.matcher} with score {match.score:.3f}",
                match_score=match.score,
                match_location=match.center
            )

        except Exception as e:
            return ActionResult(
                step=step,
                success=False,
                message=f"Find error: {e}"
            )

    def _execute_wait(self, step: ActionStep) -> ActionResult:
        """Execute wait step."""
        try:
            time.sleep(step.duration)
            return ActionResult(
                step=step,
                success=True,
                message=f"Waited {step.duration}s"
            )
        except Exception as e:
            return ActionResult(
                step=step,
                success=False,
                message=f"Wait error: {e}"
            )

    def _execute_click(self, step: ActionStep) -> ActionResult:
        """Execute raw click step (not implemented yet)."""
        return ActionResult(
            step=step,
            success=False,
            message="Raw click action not yet implemented"
        )
