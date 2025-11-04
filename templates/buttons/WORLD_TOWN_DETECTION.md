# World/Town Button Detection System

## Purpose
Detect whether the game is currently in **WORLD view** or **TOWN view** by using template matching on the toggle button in the lower-right corner of the screen.

## Quick Start - Using the API

```python
# Simple detection
from view_detection import detect_current_view, ViewState

state = detect_current_view(adb_controller)
if state == ViewState.WORLD:
    print("In World view")

# Simple switching
from view_detection import switch_to_view

success = switch_to_view(adb_controller, ViewState.TOWN)
if success:
    print("Successfully switched to Town view")

# Detailed result with confidence
from view_detection import get_detection_result

result = get_detection_result(adb_controller)
print(f"State: {result.state}, Confidence: {result.confidence:.2f}")
```

See `view_detection.py` for full API documentation.

## Button Location
- **Fixed position**: (2160, 1190) to (2560, 1440)
- **Size**: 400x250 pixels
- **Screen resolution**: 2560x1440 (constant)
- **Location**: Lower-right corner of game UI

## Templates

### 1. world_button_template.png
- **Icon**: Colorful map/atlas with red flag marker, green terrain, blue water
- **Text**: "World"
- **Match accuracy**: **99.96%** on WORLD state images
- **File size**: 66,747 bytes
- **Status**: ✅ VERIFIED CORRECT

### 2. town_button_template.png
- **Icon**: White castle/fortress with blue dome roof, red flag
- **Text**: "Town"
- **Match accuracy**: **100.00%** on TOWN state images
- **File size**: 52,326 bytes (new correct version)
- **Status**: ✅ VERIFIED CORRECT

### Archived/Wrong Templates
- `world_button_template_OLD_WRONG.png` - Previous incorrect WORLD template
- `town_button_template_OLD_WRONG.png` - Previous incorrect TOWN template (69.78% match)

## Detection Threshold: 97%+

### Why 97%?
- **Correct matches**: 99.96% (WORLD) and 100% (TOWN) - well above threshold
- **Cross-matching**: ~77-79% - well below threshold
- **77% cross-match is OK**: Templates share similar button frame/background structure (~77% similar), but differ in icons/text
- **97% threshold**: Safely distinguishes correct matches from incorrect ones

### Test Results

#### WORLD Template Performance
| Test Image | Score | Result |
|------------|-------|--------|
| screenshot_check.png | 99.97% | ✅ EXCELLENT |
| corner_check.png | 99.98% | ✅ EXCELLENT |
| button_match_world.png | 99.95% | ✅ EXCELLENT |
| **Average** | **99.96%** | ✅ PASS |

#### TOWN Template Performance
| Test Image | Score | Result |
|------------|-------|--------|
| screenshot_town.png | 100.00% | ✅ EXCELLENT |
| corner_town.png | 100.00% | ✅ EXCELLENT |
| **Average** | **100.00%** | ✅ PASS |

#### Cross-Matching (Should Be Low)
| Template | Wrong State | Score | Result |
|----------|-------------|-------|--------|
| WORLD | TOWN images | 77-79% | ✅ Correctly rejected |
| TOWN | WORLD images | 77-79% | ✅ Correctly rejected |

## Classification Logic

### State Detection Algorithm
```python
world_score = match_template(screenshot, world_button_template)
town_score = match_template(screenshot, town_button_template)

if world_score >= 0.97 and town_score < 0.97:
    current_state = "WORLD"
elif town_score >= 0.97 and world_score < 0.97:
    current_state = "TOWN"
else:
    current_state = "NONE"  # Button not detected or ambiguous
```

### Expected Scores
- **WORLD state**: world_score = 99.96%, town_score = 77%
- **TOWN state**: town_score = 100%, world_score = 77%
- **NOTHING**: both scores < 97%

## Test Images

### WORLD State Test Images
- `screenshot_check.png` - Full screenshot in WORLD view
- `corner_check.png` - Cropped lower-right corner, WORLD view
- `templates/debug/button_match_world.png` - Debug crop of WORLD button

### TOWN State Test Images
- `screenshot_town.png` - Full screenshot in TOWN view
- `corner_town.png` - Cropped lower-right corner, TOWN view
- `templates/debug/button_match_town.png` - Debug crop of TOWN button (old, may not match)

## Button Structure & Visual Differences

### Button Composition
Both buttons share the same structural elements:
- Blue UI bar background
- Light cyan circular icon background
- Black text label at bottom
- 400x250 pixel dimensions

### What Changes Between States
The **icon and text** change completely:

| Element | WORLD | TOWN |
|---------|-------|------|
| **Icon** | Map/atlas (folded book) | Castle/fortress building |
| **Colors** | Green terrain, blue water, red flag | White walls, blue dome, brown door |
| **Text** | "World" | "Town" |
| **Semantic** | Geographic/exploration | Settlement/construction |
| **Pixel Difference** | 43.51% of pixels differ between states |

This 43.51% pixel difference creates the ~22-23 percentage point gap (99.96% vs 77%) that allows reliable classification.

## Clicking Logic

The button is a **simple toggle** - clicking at the same position toggles between states.

### VERIFIED WORKING METHOD

**Click position: x_frac=0.75, y_frac=0.5** (75% from left, middle height)

This single position works from BOTH states:
- **WORLD → TOWN**: Click at x_frac=0.75 → switches to TOWN
- **TOWN → WORLD**: Click at x_frac=0.75 → switches to WORLD

### Click Calculation
```python
# Assuming detected button at (x, y) with template size (template_w, template_h)
click_x = x + template_w * 0.75
click_y = y + template_h * 0.5

# For standard 400x250 button at (2160, 1190):
# click_x = 2160 + 400 * 0.75 = 2460
# click_y = 1190 + 250 * 0.5 = 1315
```

### Button Layout
```
[  TOWN/UNION Icon  ] [  WORLD Icon (CLICK HERE)  ]
      (castle)              (map) <- x_frac=0.75
```

The button shows both states side-by-side, with the currently active state highlighted.
Clicking at x_frac=0.75 (right side) toggles between them regardless of current state.

## Implementation

### ButtonMatcher Class
Location: `button_matcher.py`

**Key parameters:**
- Match method: `cv2.TM_CCOEFF_NORMED` (normalized cross-correlation)
- Threshold: 0.85 (code default, but 0.97 recommended for final classification)
- Returns: `TemplateMatch` dataclass with label, score, coordinates

### GameHelper Integration
Location: `game_utils.py`

**Key methods:**
- `check_world_view()` - Returns (detected, state_or_reason)
- `switch_to_view(desired_state)` - Switches between WORLD/TOWN
- Uses fractional offsets for clicking

## Verification Steps

To verify the system is working:

1. **Capture test screenshots** in both WORLD and TOWN states
2. **Run comprehensive test**: `python test_all_states_classifier.py`
3. **Check scores**:
   - WORLD on WORLD: ≥95%
   - TOWN on TOWN: ≥95%
   - Cross-matching: <85%
4. **Test clicking**: Ensure clicking switches states correctly

## Common Issues

### Templates Not Matching
- **Symptom**: Scores below 90%
- **Cause**: Template extracted from wrong resolution or zoom level
- **Fix**: Re-extract template from known good screenshot at 2560x1440

### Cross-Matching Too High
- **Symptom**: Both templates score >90%
- **Cause**: Templates are too similar or identical
- **Fix**: Verify templates show different icons (map vs castle)

### Button Not Detected
- **Symptom**: Both scores <70%
- **Cause**: Button position changed, UI overlay, or different game state
- **Fix**: Check button location, verify no dialogs blocking button

## History

### 2025-01-04: Template Verification
- Confirmed WORLD template: 99.96% accuracy (✅)
- Fixed TOWN template: 100% accuracy (was 28.58%, now ✅)
- Established 97% threshold based on test results
- Documented button structure and clicking logic
- Created comprehensive test suite

### Previous Issues
- **Old WORLD template** (world_button_template_OLD_WRONG.png): Wrong image, only 76.80% match
- **Old TOWN template** (town_button_template_OLD_WRONG.png): Wrong image, only 69.78% match
- Both replaced with correctly extracted templates from actual game screenshots
