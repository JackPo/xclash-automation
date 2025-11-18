# Level Number Crop Analysis Report

## Executive Summary

Examined 5 level number crops extracted with formula: `frame[cy+35:cy+60, cx-25:cx+25]`

**Results:**
- **4 images**: PERFECT - Full 25px height captured (level_00, level_01, level_02, level_03)
- **1 image**: TRUNCATED - Only 11px captured (level_04) - Missing 14px at bottom

---

## Detailed Findings

### 1. level_00_center_531_369.png ✓ GOOD

**Dimensions:** 50px wide x 25px tall
**Center:** (531, 369)
**Crop extracted:** frame[404:429, 506:556]

**Analysis:**
- Height: ✓ FULL (25px)
- Width: ✓ FULL (50px)
- Content fill: 99.4% (1242/1250 pixels non-zero)
- Content at all edges: YES (fully visible)

**Verdict:** Entire level bar is visible and complete.

---

### 2. level_01_center_91_1310.png ✓ GOOD

**Dimensions:** 50px wide x 25px tall
**Center:** (91, 1310)
**Crop extracted:** frame[1345:1370, 66:116]

**Analysis:**
- Height: ✓ FULL (25px)
- Width: ✓ FULL (50px)
- Content fill: 100% (1250/1250 pixels non-zero)
- Content at all edges: YES (fully visible)

**Verdict:** Entire level bar is visible and complete.

---

### 3. level_02_center_1982_190.png ✓ GOOD

**Dimensions:** 50px wide x 25px tall
**Center:** (1982, 190)
**Crop extracted:** frame[225:250, 1957:2007]

**Analysis:**
- Height: ✓ FULL (25px)
- Width: ✓ FULL (50px)
- Content fill: 100% (1250/1250 pixels non-zero)
- Content at all edges: YES (fully visible)

**Verdict:** Entire level bar is visible and complete.

---

### 4. level_03_center_1422_265.png ✓ GOOD

**Dimensions:** 50px wide x 25px tall
**Center:** (1422, 265)
**Crop extracted:** frame[300:325, 1397:1447]

**Analysis:**
- Height: ✓ FULL (25px)
- Width: ✓ FULL (50px)
- Content fill: 100% (1250/1250 pixels non-zero)
- Content at all edges: YES (fully visible)

**Verdict:** Entire level bar is visible and complete.

---

### 5. level_04_center_87_1394.png ✗ TRUNCATED

**Dimensions:** 50px wide x 11px tall
**Center:** (87, 1394)
**Crop requested:** frame[1429:1454, 62:112]
**Expected:** 25px tall, Actual: 11px tall

**Analysis:**
- Height: ✗ TRUNCATED (11px captured out of 25px requested)
- Width: ✓ FULL (50px)
- Content fill: 100% (550/550 pixels non-zero)
- Content at top edge: YES
- Content at bottom edge: YES (THE PROBLEM!)
- **Missing:** 14px of height

**Root Cause:**
The crop bottom boundary extends beyond the available image data. At center Y=1394:
- Requested crop: frame[1429:1454] (rows 1429-1453, which is 25 rows)
- Available data: Only 11 rows (from 1429 to 1439 approximately)
- Image boundary likely reached at row ~1440
- **The level bar extends BELOW where we're currently capturing**

**How Much Space is Needed:**

| Direction | Current | Needed | Adjustment |
|-----------|---------|--------|------------|
| **Top** | cy+35 (14px above center) | cy+20 to cy+25 | +10 to +15px MORE space |
| **Bottom** | cy+60 (66px below center) | cy+75 to cy+80 | +15 to +20px MORE space |
| **Left** | cx-25 | cx-25 | ✓ Sufficient |
| **Right** | cx+25 | cx+25 | ✓ Sufficient |

**Total recommended height:** 40-45px (instead of current 25px)

---

## Recommended Solution

### Current Formula (INSUFFICIENT):
```python
frame[cy+35:cy+60, cx-25:cx+25]  # 25px tall, 50px wide
```

### Recommended Formula (SAFE):
```python
# Option 1: Symmetric expansion
frame[cy+20:cy+75, cx-25:cx+25]  # 55px tall, 50px wide

# Option 2: More bottom emphasis
frame[cy+25:cy+75, cx-25:cx+25]  # 50px tall, 50px wide

# Option 3: Conservative expansion
frame[cy+30:cy+70, cx-25:cx+25]  # 40px tall, 50px wide
```

### Why This Works:
- **Level 04 problem:** Extends 14px beyond current bottom edge
- **Adding 15px to bottom** (cy+60 → cy+75) ensures full capture
- **Adding 10px to top** (cy+35 → cy+25) provides symmetry and safety margin
- **Recommended formula:** `frame[cy+25:cy+75, cx-25:cx+25]`
  - Total height: 50px
  - Total width: 50px
  - Symmetrical: 25px above center, 25px below center

---

## Testing Recommendation

1. **Apply new formula** to all level crops
2. **Verify level_04** specifically - should now be full 50px tall
3. **Check levels 00-03** - should still be correct (may have extra space above/below)
4. **Apply to live detection code**

---

## Summary Table

| Level | Filename | Width | Height | Problem | Solution |
|-------|----------|-------|--------|---------|----------|
| 0 | level_00_center_531_369.png | 50px ✓ | 25px ✓ | None | Keep current formula |
| 1 | level_01_center_91_1310.png | 50px ✓ | 25px ✓ | None | Keep current formula |
| 2 | level_02_center_1982_190.png | 50px ✓ | 25px ✓ | None | Keep current formula |
| 3 | level_03_center_1422_265.png | 50px ✓ | 25px ✓ | None | Keep current formula |
| 4 | level_04_center_87_1394.png | 50px ✓ | 11px ✗ | Missing 14px below | Expand to cy+20:cy+75 |

**Overall Assessment:** Use expanded formula for all crops to ensure consistency and safety.

---

## Implementation

Replace in code:
```python
# OLD
crop = frame[cy+35:cy+60, cx-25:cx+25]

# NEW
crop = frame[cy+25:cy+75, cx-25:cx+25]
```

This adds:
- **10px extension to the top** (from +35 to +25)
- **15px extension to the bottom** (from +60 to +75)
- **Total increase:** +25px height (25px → 50px)
