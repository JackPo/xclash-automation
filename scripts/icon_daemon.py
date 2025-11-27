#!/usr/bin/env python3
"""
Icon Auto-Clicker Daemon

Runs continuously, checking for clickable icons every 3 seconds.
When an icon is detected, kicks off a flow handler in a separate thread.

Currently detects:
- Handshake icon (Union button)
- Treasure map icon (bouncing scroll on barracks)
- Corn harvest bubble
- Gold coin bubble
- Harvest box icon
- Iron bar bubble
- Gem bubble

Press Ctrl+C to stop.

Usage:
    python icon_daemon.py [--interval SECONDS] [--debug]
"""

import sys
import time
import argparse
import threading
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.handshake_icon_matcher import HandshakeIconMatcher
from utils.treasure_map_matcher import TreasureMapMatcher
from utils.corn_harvest_matcher import CornHarvestMatcher
from utils.gold_coin_matcher import GoldCoinMatcher
from utils.harvest_box_matcher import HarvestBoxMatcher
from utils.iron_bar_matcher import IronBarMatcher
from utils.gem_matcher import GemMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper

from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow


class IconDaemon:
    """
    Daemon that detects icons and triggers non-blocking flows.
    """

    def __init__(self, interval: float = 3.0, debug: bool = False):
        self.interval = interval
        self.debug = debug
        self.adb = None
        self.windows_helper = None

        # Matchers
        self.handshake_matcher = None
        self.treasure_matcher = None
        self.corn_matcher = None
        self.gold_matcher = None
        self.harvest_box_matcher = None
        self.iron_matcher = None
        self.gem_matcher = None

        # Track active flows to prevent re-triggering
        self.active_flows = set()
        self.flow_lock = threading.Lock()

        # Setup logging
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('IconDaemon')

    def initialize(self):
        """Initialize all components."""
        self.logger.info("Initializing icon daemon...")
        self.logger.info(f"Log file: {self.log_file}")

        # ADB
        self.adb = ADBHelper()
        print(f"  Connected to device: {self.adb.device}")

        # Windows screenshot helper
        self.windows_helper = WindowsScreenshotHelper()
        print("  Windows screenshot helper initialized")

        # Matchers
        debug_dir = Path('templates/debug')

        # Matchers use their own default thresholds - edit thresholds in the matcher files
        self.handshake_matcher = HandshakeIconMatcher(debug_dir=debug_dir)
        print(f"  Handshake matcher: {self.handshake_matcher.template_path.name} (threshold={self.handshake_matcher.threshold})")

        self.treasure_matcher = TreasureMapMatcher(debug_dir=debug_dir)
        print(f"  Treasure map matcher: {self.treasure_matcher.template_path.name} (threshold={self.treasure_matcher.threshold})")

        self.corn_matcher = CornHarvestMatcher(debug_dir=debug_dir)
        print(f"  Corn harvest matcher: {self.corn_matcher.template_path.name} (threshold={self.corn_matcher.threshold})")

        self.gold_matcher = GoldCoinMatcher(debug_dir=debug_dir)
        print(f"  Gold coin matcher: {self.gold_matcher.template_path.name} (threshold={self.gold_matcher.threshold})")

        self.harvest_box_matcher = HarvestBoxMatcher(debug_dir=debug_dir)
        print(f"  Harvest box matcher: {self.harvest_box_matcher.template_path.name} (threshold={self.harvest_box_matcher.threshold})")

        self.iron_matcher = IronBarMatcher(debug_dir=debug_dir)
        print(f"  Iron bar matcher: {self.iron_matcher.template_path.name} (threshold={self.iron_matcher.threshold})")

        self.gem_matcher = GemMatcher(debug_dir=debug_dir)
        print(f"  Gem matcher: {self.gem_matcher.template_path.name} (threshold={self.gem_matcher.threshold})")

    def _run_flow(self, flow_name: str, flow_func):
        """
        Run a flow in a thread-safe way.

        Args:
            flow_name: Identifier for the flow
            flow_func: Function to execute (takes adb as argument)
        """
        def wrapper():
            try:
                self.logger.info(f"FLOW START: {flow_name}")
                flow_func(self.adb)
                self.logger.info(f"FLOW END: {flow_name}")
            except Exception as e:
                self.logger.error(f"FLOW ERROR: {flow_name} - {e}")
            finally:
                with self.flow_lock:
                    self.active_flows.discard(flow_name)

        with self.flow_lock:
            if flow_name in self.active_flows:
                self.logger.debug(f"SKIP: {flow_name} already running")
                return False

            self.active_flows.add(flow_name)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return True

    def run(self):
        """Main detection loop."""
        self.logger.info(f"Starting detection loop (interval: {self.interval}s)")
        self.logger.info("Detecting: Handshake, Treasure map, Corn, Gold, Harvest box, Iron, Gem")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        iteration = 0
        while True:
            iteration += 1

            try:
                # Take single screenshot for all checks
                frame = self.windows_helper.get_screenshot_cv2()

                # Check all icons
                handshake_present, handshake_score = self.handshake_matcher.is_present(frame)
                treasure_present, treasure_score = self.treasure_matcher.is_present(frame)
                corn_present, corn_score = self.corn_matcher.is_present(frame)
                gold_present, gold_score = self.gold_matcher.is_present(frame)
                harvest_present, harvest_score = self.harvest_box_matcher.is_present(frame)
                iron_present, iron_score = self.iron_matcher.is_present(frame)
                gem_present, gem_score = self.gem_matcher.is_present(frame)

                # Always print scores to stdout
                print(f"[{iteration}] H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f}")

                # Log and trigger flows
                if handshake_present:
                    self.logger.info(f"[{iteration}] HANDSHAKE detected (diff={handshake_score:.4f})")
                    self._run_flow("handshake", handshake_flow)

                if treasure_present:
                    self.logger.info(f"[{iteration}] TREASURE detected (diff={treasure_score:.4f})")
                    self._run_flow("treasure_map", treasure_map_flow)

                if corn_present:
                    self.logger.info(f"[{iteration}] CORN detected (diff={corn_score:.4f})")
                    self._run_flow("corn_harvest", corn_harvest_flow)

                if gold_present:
                    self.logger.info(f"[{iteration}] GOLD detected (diff={gold_score:.4f})")
                    self._run_flow("gold_coin", gold_coin_flow)

                if harvest_present:
                    self.logger.info(f"[{iteration}] HARVEST detected (diff={harvest_score:.4f})")
                    self._run_flow("harvest_box", harvest_box_flow)

                if iron_present:
                    self.logger.info(f"[{iteration}] IRON detected (diff={iron_score:.4f})")
                    self._run_flow("iron_bar", iron_bar_flow)

                if gem_present:
                    self.logger.info(f"[{iteration}] GEM detected (diff={gem_score:.4f})")
                    self._run_flow("gem", gem_flow)

            except Exception as e:
                self.logger.error(f"[{iteration}] ERROR: {e}")

            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser(
        description="Icon auto-clicker daemon"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=3.0,
        help="Check interval in seconds (default: 3.0)"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug logging (logs all scores, not just detections)"
    )

    args = parser.parse_args()

    daemon = IconDaemon(interval=args.interval, debug=args.debug)

    try:
        daemon.initialize()
        daemon.run()
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
