# Template Extraction Workflows

Complete workflows for extracting and creating templates.

## Basic Extraction Workflow

1. **Take screenshot** with `WindowsScreenshotHelper` (NOT adb_helper)
2. **Use Gemini** to find element: `python calibration/detect_object.py screenshot.png "description"`
3. **Extract template** using returned bounding box
4. **Save** to `templates/ground_truth/`

---

## Correlation-Based Extraction (Consistent Framing)

Use when extracting multiple similar templates (e.g., Attack, Rally, Scout buttons) that need consistent framing.

```python
import cv2

frame = cv2.imread('screenshot.png')
reference_template = cv2.imread('templates/ground_truth/rally_button_4k.png')

# Search region: expected position +/- 100px
expected_x, expected_y = 1639, 1658  # From Gemini
w, h = reference_template.shape[1], reference_template.shape[0]

region_x = expected_x - 100
region_y = expected_y - 100
region_w = w + 200
region_h = h + 200

region = frame[region_y:region_y+region_h, region_x:region_x+region_w]

# Find highest correlation
result = cv2.matchTemplate(region, reference_template, cv2.TM_CCORR_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

# Convert to full frame coordinates
best_x = region_x + max_loc[0]
best_y = region_y + max_loc[1]

print(f'Best correlation: {max_val:.4f} at ({best_x}, {best_y})')

# Extract with correct framing
new_template = frame[best_y:best_y+h, best_x:best_x+w]
cv2.imwrite('templates/ground_truth/new_button_4k.png', new_template)
```

**Why it works**: Similar UI elements share structural features. Hexagon borders correlate well even if icons differ.

**When to use**:
- Extracting multiple buttons in a row
- Ensuring consistent padding/centering
- When Gemini gives rough coordinates but framing looks off

**Tip**: For buttons on the same row, find best Y for one, use that Y for all.

---

## Masked Template Extraction (Transparent / variable backgrounds)

When an icon sits over varying terrain (popups over the world map, HUD over a
panning scene), the unmasked template picks up background pixels and matches
poorly. Add a mask so only the icon pixels count.

### Use the helper script (preferred)

`scripts/one_off/build_mask.py` automates the diff and auto-locates the icon
via template matching (loose threshold), so you don't need to know the bbox.

#### Single-shot mode (PREFERRED when an existing template exists)

If you already have a template (even a poorly-matching one) and ANY
screenshot containing the icon — including failure screenshots from
`screenshots/debug/<flow>/` — you have everything you need. The existing
template IS the second half of the diff. No new capture, no daemon stop.

```bash
python scripts/one_off/build_mask.py \
    --single-shot screenshots/debug/quick_prod/20260510_134749_04_castle_popup.png \
    --reference class_skill_button_4k.png \
    --name class_skill_button --force
```

What it does: locates the icon in the screenshot, crops it, diffs that crop
against the existing template. Pixels that AGREE (the stable icon body)
become white(255) in the mask; pixels that DIFFER (active-state glow,
background that bled into the original capture) become black(0). The new
template is the live crop, so it reflects current in-game appearance.

#### Two-shot mode (when no usable existing template)

```bash
python scripts/one_off/build_mask.py \
    --shot1 a.png --shot2 b.png \
    --reference some_existing_4k.png \
    --name new_thing --force

# Or, with manually-picked bbox if no reference template exists at all:
python scripts/one_off/build_mask.py \
    --shot1 a.png --shot2 b.png \
    --bbox 1520 1180 200 160 \
    --name new_thing --force
```

The script:
1. Locates the icon in each shot (via `cv2.matchTemplate` with a loose
   threshold, since the whole point of masking is that unmasked matching is
   imperfect — see `AUTO_LOCATE_THRESHOLD = 0.30` in the script).
2. Crops both shots at the matched positions.
3. Diffs them — pixels that AGREE become white(255) in the mask; pixels that
   DIFFER become black(0).
4. Cleans the mask with morphological open+close to drop speckle.
5. Writes `<name>_4k.png` (the live crop from shot1, so the template reflects
   current in-game appearance) and `<name>_mask_4k.png`.
6. Reports mask coverage. Healthy range is **30%-80%**:
   - **<20%** -> bbox too large, or scenes too different (icon moved between
     captures). Try a tighter bbox.
   - **>90%** -> backgrounds too similar. Pan further or vary the scene more.

### How `match_template` uses it

`utils/template_matcher.match_template()` auto-detects masks by name
(`<name>_4k.png` -> `<name>_mask_4k.png`) — no API change needed at the call
site. Internally it uses energy-normalized correlation and **converts back to
the lower=better convention** so `DEFAULT_MASKED_THRESHOLD = 0.05` still
applies.

### Capturing the second screenshot

Use `scripts/one_off/capture_class_skill_for_mask.py` as a template — it does
TOWN -> WORLD -> swipe -> tap-castle-at-new-position. Copy and adapt the
swipe delta / tap target for whatever icon you're masking. Stop the daemon
first or it will fight you.

### Mask convention recap

- Same dimensions as the template. Grayscale.
- **White(255)**: opaque icon — MATCH these pixels.
- **Black(0)**: transparent / variable background — IGNORE these pixels.
- Save to `templates/ground_truth/<name>_mask_4k.png`.

---

## Full Workflow: Templates + Masks

**Tried and true pattern**:

1. **Take first screenshot** with panel open (background A)
2. **Use Gemini** to roughly locate buttons
3. **Use correlation matching** with reference template for exact positions
4. **Extract templates**, save to `ground_truth/`
5. **Take second screenshot** with different background
6. **Use Gemini again** to locate in new screenshot
7. **Correlation match again** using templates you just extracted
8. **Create masks** by comparing the two extractions

---

## Naming Convention

- Template: `<element_name>_4k.png`
- Mask: `<element_name>_mask_4k.png`

**Examples**:
- `rally_button_4k.png` + `rally_button_mask_4k.png`
- `search_button_4k.png` + `search_button_mask_4k.png`

---

## After Extraction

1. Document in `template-catalog` skill (or CLAUDE.md if critical)
2. Create matcher class using patterns in TEMPLATE_MATCHING.md
3. Test matcher with fresh screenshot
4. Integrate into daemon if needed
