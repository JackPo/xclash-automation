#!/usr/bin/env python3
"""
Handshake Icon Auto-Clicker

Automatically detects and clicks the handshake icon on the Union button.
Designed to run as a cronjob every 3 seconds.

Usage:
    python run_handshake_clicker.py [--config CONFIG_PATH] [--dry-run]

Examples:
    # Normal run
    python run_handshake_clicker.py

    # Custom config
    python run_handshake_clicker.py --config my_config.json

    # Dry run (detect but don't click)
    python run_handshake_clicker.py --dry-run

Cronjob setup (Windows Task Scheduler):
    - Trigger: Every 3 seconds (00:00:03 interval)
    - Action: C:\\Users\\mail\\AppData\\Local\\Programs\\Python\\Python312\\python.exe
    - Arguments: C:\\Users\\mail\\xclash\\run_handshake_clicker.py
    - Start in: C:\\Users\\mail\\xclash
"""

import sys
import json
import argparse
from pathlib import Path

from adb_helper import ADBHelper
from handshake_icon_matcher import HandshakeIconMatcher
from action_chain_runner import ActionChainRunner, ActionStep


def load_config(config_path: Path) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Handshake icon auto-clicker for Union button"
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path(__file__).parent / 'handshake_config.json',
        help="Path to configuration file (default: handshake_config.json)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Detect but don't click (for testing)"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    try:
        # Initialize ADB
        adb = ADBHelper()

        # Initialize action chain runner
        settings = config.get('settings', {})
        runner = ActionChainRunner(
            adb,
            screenshot_path=Path(settings.get('screenshot_path', 'temp_handshake_check.png')),
            log_file=Path(settings.get('log_file', 'handshake_clicker.log'))
        )

        # Register matchers
        matchers_config = config.get('matchers', {})
        for name, matcher_config in matchers_config.items():
            template_path = matcher_config.get('template_path')
            threshold = matcher_config.get('threshold', 0.99)

            matcher = HandshakeIconMatcher(
                template_path=Path(template_path) if template_path else None,
                threshold=threshold,
                debug_dir=Path('templates/debug') if settings.get('debug_mode', True) else None
            )
            runner.register_matcher(name, matcher)

        # Build action chain
        chain_config = config.get('action_chain', [])
        chain = []
        for step_config in chain_config:
            # Override click_on_match if dry-run
            click = step_config.get('click_on_match', False)
            if args.dry_run and click:
                print("DRY RUN: Would click, but skipping")
                click = False

            step = ActionStep(
                action=step_config['action'],
                matcher=step_config.get('matcher'),
                click_on_match=click,
                duration=step_config.get('duration', 0.0),
                required=step_config.get('required', False)
            )
            chain.append(step)

        # Execute chain
        success, results = runner.execute_chain(chain)

        # Print summary
        print(f"\n{'='*60}")
        print(f"Execution Summary: {'SUCCESS' if success else 'FAILED'}")
        print(f"{'='*60}")

        for i, result in enumerate(results):
            status = "[OK]" if result.success else "[FAIL]"
            print(f"{status} Step {i+1}: {result.message}")
            if result.match_score is not None:
                print(f"  Score: {result.match_score:.3f}, Location: {result.match_location}")

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
