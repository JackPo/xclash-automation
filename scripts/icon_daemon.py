#!/usr/bin/env python3
"""
Icon Auto-Clicker Daemon

Runs continuously, checking for clickable icons every 3 seconds.
When an icon is detected, kicks off a flow handler in a separate thread.

Currently detects:
- Handshake icon (Union button)
- Treasure map icon (bouncing scroll on barracks)

Press Ctrl+C to stop.

Usage:
    python icon_daemon.py [--interval SECONDS]
"""

import sys
import time
import argparse
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.handshake_icon_matcher import HandshakeIconMatcher
from utils.treasure_map_matcher import TreasureMapMatcher
from utils.corn_harvest_matcher import CornHarvestMatcher
from utils.gold_coin_matcher import GoldCoinMatcher
from utils.harvest_box_matcher import HarvestBoxMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper

from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow


class IconDaemon:
    """
    Daemon that detects icons and triggers non-blocking flows.
    """

    def __init__(self, interval: float = 3.0):
        self.interval = interval
        self.adb = None
        self.windows_helper = None

        # Matchers
        self.handshake_matcher = None
        self.treasure_matcher = None
        self.corn_matcher = None
        self.gold_matcher = None
        self.harvest_box_matcher = None

        # Track active flows to prevent re-triggering
        self.active_flows = set()
        self.flow_lock = threading.Lock()

    def initialize(self):
        """Initialize all components."""
        print("Initializing icon daemon...")

        # ADB
        self.adb = ADBHelper()
        print(f"  Connected to device: {self.adb.device}")

        # Windows screenshot helper
        self.windows_helper = WindowsScreenshotHelper()
        print("  Windows screenshot helper initialized")

        # Matchers
        debug_dir = Path('templates/debug')

        self.handshake_matcher = HandshakeIconMatcher(
            threshold=0.04,
            debug_dir=debug_dir
        )
        print(f"  Handshake matcher: {self.handshake_matcher.template_path.name}")

        self.treasure_matcher = TreasureMapMatcher(
            threshold=0.05,
            debug_dir=debug_dir
        )
        print(f"  Treasure map matcher: {self.treasure_matcher.template_path.name}")

        self.corn_matcher = CornHarvestMatcher(
            threshold=0.05,
            debug_dir=debug_dir
        )
        print(f"  Corn harvest matcher: {self.corn_matcher.template_path.name}")

        self.gold_matcher = GoldCoinMatcher(
            threshold=0.1,
            debug_dir=debug_dir
        )
        print(f"  Gold coin matcher: {self.gold_matcher.template_path.name}")

        self.harvest_box_matcher = HarvestBoxMatcher(
            threshold=0.1,
            debug_dir=debug_dir
        )
        print(f"  Harvest box matcher: {self.harvest_box_matcher.template_path.name}")

    def _run_flow(self, flow_name: str, flow_func):
        """
        Run a flow in a thread-safe way.

        Args:
            flow_name: Identifier for the flow
            flow_func: Function to execute (takes adb as argument)
        """
        def wrapper():
            try:
                flow_func(self.adb)
            finally:
                with self.flow_lock:
                    self.active_flows.discard(flow_name)

        with self.flow_lock:
            if flow_name in self.active_flows:
                print(f"    [SKIP] {flow_name} already running")
                return False

            self.active_flows.add(flow_name)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return True

    def run(self):
        """Main detection loop."""
        print(f"\nStarting detection loop (interval: {self.interval}s)")
        print("Detecting: Handshake, Treasure map, Corn, Gold, Harvest box")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        iteration = 0
        while True:
            iteration += 1
            print(f"\n[{iteration}] {time.strftime('%H:%M:%S')}")

            try:
                # Take single screenshot for all checks
                frame = self.windows_helper.get_screenshot_cv2()

                # Check handshake
                handshake_present, handshake_score = self.handshake_matcher.is_present(frame)
                if handshake_present:
                    print(f"  [HANDSHAKE] Detected (diff={handshake_score:.4f})")
                    self._run_flow("handshake", handshake_flow)
                else:
                    print(f"  [HANDSHAKE] Not present (diff={handshake_score:.4f})")

                # Check treasure map
                treasure_present, treasure_score = self.treasure_matcher.is_present(frame)
                if treasure_present:
                    print(f"  [TREASURE]  Detected (diff={treasure_score:.4f})")
                    self._run_flow("treasure_map", treasure_map_flow)
                else:
                    print(f"  [TREASURE]  Not present (diff={treasure_score:.4f})")

                # Check corn harvest
                corn_present, corn_score = self.corn_matcher.is_present(frame)
                if corn_present:
                    print(f"  [CORN]      Detected (diff={corn_score:.4f})")
                    self._run_flow("corn_harvest", corn_harvest_flow)
                else:
                    print(f"  [CORN]      Not present (diff={corn_score:.4f})")

                # Check gold coin
                gold_present, gold_score = self.gold_matcher.is_present(frame)
                if gold_present:
                    print(f"  [GOLD]      Detected (diff={gold_score:.4f})")
                    self._run_flow("gold_coin", gold_coin_flow)
                else:
                    print(f"  [GOLD]      Not present (diff={gold_score:.4f})")

                # Check harvest box
                harvest_present, harvest_score = self.harvest_box_matcher.is_present(frame)
                if harvest_present:
                    print(f"  [HARVEST]   Detected (diff={harvest_score:.4f})")
                    self._run_flow("harvest_box", harvest_box_flow)
                else:
                    print(f"  [HARVEST]   Not present (diff={harvest_score:.4f})")

            except Exception as e:
                print(f"  [ERROR] {e}")

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

    args = parser.parse_args()

    daemon = IconDaemon(interval=args.interval)

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
