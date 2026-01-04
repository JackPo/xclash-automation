# Template Matching Patterns

Three proven patterns for UI element detection.

## Pattern 1: Fixed-Position Matcher

For elements that always appear at the same location (icons, buttons in fixed UI).

```python
# utils/my_icon_matcher.py
from pathlib import Path
import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"

class MyIconMatcher:
    """Detect icon at fixed screen position."""

    # Fixed position (4K resolution)
    ICON_X, ICON_Y = 2096, 1540
    ICON_WIDTH, ICON_HEIGHT = 158, 162

    # Click position (may differ from detection center)
    CLICK_X, CLICK_Y = 2175, 1621

    # Match threshold (lower = stricter)
    THRESHOLD = 0.05

    def __init__(self):
        template_path = BASE_DIR / "my_icon_4k.png"
        self.template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {template_path}")

    def is_present(self, frame: np.ndarray) -> tuple[bool, float]:
        """
        Check if icon is present at fixed location.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (is_present, score) - score lower is better
        """
        # Extract ROI at fixed position
        roi = frame[self.ICON_Y:self.ICON_Y + self.ICON_HEIGHT,
                    self.ICON_X:self.ICON_X + self.ICON_WIDTH]

        # Convert to grayscale
        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Template match
        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        score = cv2.minMaxLoc(result)[0]

        return score <= self.THRESHOLD, score

    def click(self, adb):
        """Click the icon position."""
        adb.tap(self.CLICK_X, self.CLICK_Y)
```

**When to use**: Icons, bubbles, fixed UI elements that don't move.

**Examples in codebase**:
- `utils/treasure_map_matcher.py`
- `utils/handshake_icon_matcher.py`
- `utils/corn_harvest_matcher.py`

---

## Pattern 2: Search-Based Matcher

For elements that move within a region (dialogs, scrollable lists).

```python
# utils/search_matcher.py
from pathlib import Path
import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"

class SearchMatcher:
    """Find element anywhere within a search region."""

    # Search region (x, y, width, height)
    SEARCH_REGION = (1500, 0, 820, 2160)  # Vertical strip

    THRESHOLD = 0.05

    def __init__(self):
        template_path = BASE_DIR / "button_4k.png"
        self.template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {template_path}")
        self.template_h, self.template_w = self.template.shape[:2]

    def find(self, frame: np.ndarray) -> tuple[bool, float, tuple | None]:
        """
        Search for element in region.

        Returns:
            (found, score, (x, y)) - coordinates in full frame, or None if not found
        """
        x, y, w, h = self.SEARCH_REGION
        roi = frame[y:y+h, x:x+w]

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)

        if min_val <= self.THRESHOLD:
            # Convert back to full frame coordinates
            found_x = x + min_loc[0]
            found_y = y + min_loc[1]
            return True, min_val, (found_x, found_y)

        return False, min_val, None

    def find_and_click(self, frame: np.ndarray, adb) -> bool:
        """Find and click center of element."""
        found, score, pos = self.find(frame)
        if found and pos:
            click_x = pos[0] + self.template_w // 2
            click_y = pos[1] + self.template_h // 2
            adb.tap(click_x, click_y)
            return True
        return False
```

**When to use**: Buttons in scrollable panels, dialogs that appear at varying positions.

**Examples in codebase**:
- `utils/claim_button_matcher.py` (column-restricted search)
- `utils/hospital_panel_helper.py` (plus button search)

---

## Pattern 3: Multi-Template State Matcher

For detecting different states of the same element (ready/training/pending).

```python
# utils/state_matcher.py
from pathlib import Path
import cv2
import numpy as np
from enum import Enum

BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"

class BarrackState(Enum):
    READY = "ready"
    TRAINING = "training"
    PENDING = "pending"
    UNKNOWN = "unknown"

class BarrackStateMatcher:
    """Detect barrack state from bubble icon."""

    # Template size (all templates must be same size)
    TEMPLATE_SIZE = (81, 87)
    THRESHOLD = 0.08

    def __init__(self):
        self.templates = {}

        # READY state - multiple yellow soldier variants
        ready_files = [
            "yellow_soldier_barrack_4k.png",
            "yellow_soldier_barrack_v2_4k.png",
            "yellow_soldier_barrack_v3_4k.png",
            "yellow_soldier_barrack_v4_4k.png",
            "yellow_soldier_barrack_v5_4k.png",
        ]
        self.templates[BarrackState.READY] = [
            cv2.imread(str(BASE_DIR / f), cv2.IMREAD_GRAYSCALE)
            for f in ready_files
        ]

        # TRAINING state - stopwatch
        self.templates[BarrackState.TRAINING] = [
            cv2.imread(str(BASE_DIR / "stopwatch_barrack_4k.png"), cv2.IMREAD_GRAYSCALE)
        ]

        # PENDING state - white soldier
        self.templates[BarrackState.PENDING] = [
            cv2.imread(str(BASE_DIR / "white_soldier_barrack_4k.png"), cv2.IMREAD_GRAYSCALE)
        ]

    def get_state(self, frame: np.ndarray, position: tuple[int, int]) -> tuple[BarrackState, float]:
        """
        Detect state at given position.

        Args:
            frame: BGR screenshot
            position: (x, y) center of detection area

        Returns:
            (state, best_score)
        """
        x, y = position
        w, h = self.TEMPLATE_SIZE

        # Extract ROI centered on position
        roi_x = x - w // 2
        roi_y = y - h // 2
        roi = frame[roi_y:roi_y+h, roi_x:roi_x+w]

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Check each state's templates
        best_state = BarrackState.UNKNOWN
        best_score = 1.0

        for state, templates in self.templates.items():
            for template in templates:
                if template is None:
                    continue
                result = cv2.matchTemplate(roi_gray, template, cv2.TM_SQDIFF_NORMED)
                score = cv2.minMaxLoc(result)[0]

                if score < best_score:
                    best_score = score
                    if score <= self.THRESHOLD:
                        best_state = state

        return best_state, best_score

    def get_all_states(self, frame: np.ndarray, positions: list[tuple[int, int]]) -> dict:
        """Get states for multiple positions."""
        return {
            pos: self.get_state(frame, pos)
            for pos in positions
        }
```

**When to use**: Elements with multiple visual states (barracks, hospital bubbles).

**Examples in codebase**:
- `utils/barracks_state_matcher.py`
- `utils/hospital_state_matcher.py`

---

## Integration with Icon Daemon

Matchers integrate with `scripts/icon_daemon.py`:

```python
# In icon_daemon.py
from utils.my_icon_matcher import MyIconMatcher

matcher = MyIconMatcher()

# In detection loop
frame = win.get_screenshot_cv2()
is_present, score = matcher.is_present(frame)

if is_present:
    logger.info(f"Icon detected (score={score:.4f})")
    # Trigger flow
    run_my_flow(adb, win)
```

---

## Debugging Tips

### Print all scores

```python
def is_present(self, frame, debug=False):
    # ... matching code ...
    if debug:
        print(f"Template match score: {score:.4f} (threshold: {self.THRESHOLD})")
    return score <= self.THRESHOLD, score
```

### Save debug visualization

```python
# Show where template matched
debug_frame = frame.copy()
cv2.rectangle(debug_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
cv2.imwrite("screenshots/debug/match_debug.png", debug_frame)
```

### Verify template extraction

```python
# After extracting template, verify dimensions
template = cv2.imread("templates/ground_truth/new_template_4k.png")
print(f"Template size: {template.shape[:2]}")  # (height, width)
```
