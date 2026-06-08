# xclash-automation

Automation daemon for **X-Clash** (`com.xman.na.gp`) running on BlueStacks at
4K (3840×2160). Drives the game with Windows-side screenshots, OpenCV
template matching (with masks for transparent UI), a local Qwen2.5-VL OCR
server, and ADB taps/swipes. A persistent scheduler tracks cooldowns and
daily limits across daemon restarts, a web dashboard surfaces live state,
and a WebSocket API lets you trigger flows on demand.

![Town layout reference](docs/town_layout_example.png)

The daemon is designed to **only act when the user is idle** (configurable
threshold). If you start touching the screen, in-progress automation backs
off to give you control.

---

## Table of Contents

- [What it automates](#what-it-automates)
- [Architecture overview](#architecture-overview)
- [How the detection pipeline works](#how-the-detection-pipeline-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running it](#running-it)
- [Web dashboard](#web-dashboard)
- [Configuration](#configuration)
- [Recent improvements](#recent-improvements)
- [Adding a new flow](#adding-a-new-flow)
- [Troubleshooting](#troubleshooting)
- [Documentation index](#documentation-index)
- [License](#license)

---

## What it automates

### Passive / idle-time flows
- **Handshake popups**, **treasure-map** notifications, **harvest boxes**,
  **AFK reward** chests, **gift box** rewards
- **Bag** items (resources, hero chests, special items)
- **Daily community check-in** (4-hour cooldown)

### Resource & town management
- **Resource bubble harvest** (corn, gold, iron, gem, cabbage,
  equipment-enhancement) — requires calibrated town-layout coordinates
- **Hospital healing** in batches with HELP_READY detection
- **Barracks soldier training** — auto-claim READY barracks, kick off
  PENDING ones, and run soldier promotion on Soldier Training days

### Tavern quests (full lifecycle)
| Mode | What it does |
|---|---|
| `scan` | OCR all visible quest timers, persist the schedule, attempt a dispatch follow-up |
| `dispatch` | Start new gold-scroll quests inside the configured Pacific time window |
| `claim` | Claim quests whose timers have expired |
| `ally` | Assist ally quests (gold 4+ star logic) |

VS-day gating turns question-mark quests on/off via
`VS_QUESTION_MARK_SKIP_DAYS`.

### Union flows
- Daily **gifts** distribution
- **Technology donations**
- **Coal** collection & **Furnace** donations

### Rally joining (Union War / monsters)
- Filters rallies by monster type with per-monster level caps
- Honors daily-limit dialogs (with override toggles per monster type)
- **Elite Zombie** stamina-based rallies for Mystic Beast points

### Arms Race events — all 5 event types automated

| Event | Trigger window | What runs |
|---|---|---|
| **Mystic Beast Training** | aggressive throughout block | Stamina management (free claim + recovery items) + Elite Zombie rallies |
| **Enhance Hero** | last 10 min | **NEW** Level OCR + EXP budget tracking. Scrolls the hero grid, finds sub-Lv150 heroes, repeat-clicks Upgrade and measures actual hero EXP spent until chest3 (12k points / ~24M EXP) is crossed |
| **Soldier Training** | aggressive throughout block | Train + promote soldiers; auto-recover stuck Training popup |
| **Technology Research** | last 20 min | OCR both queue timers, speed up the **smaller** queue, click Complete (anchored search with full-screen fallback) |
| **City Construction** | last 20 min | OCR both queue timers, speed up the **smaller** queue, click Complete (anchored search with full-screen fallback) |

### Class Skills
- **Quick Production** — 24 hour cooldown, grants 24h of wheat/iron/gold
  production instantly. Triggered automatically and also available via the
  dashboard's "**Mark QP Done**" button (verifies in-game cooldown via OCR
  so manual usage doesn't desync the schedule).

### VS Day / arms-race-aware behavior
- Day-specific config overrides (e.g., chest opening on Day 7, skip-day
  filtering for tavern question-mark quests)
- Real-time arms-race progress check via Events panel OCR (skips a flow if
  chest3 is already reached)

### Manual / on-demand (not daemon-automated)
- **Faction Trials**, **Title management**, **Marshall + speedup** combos,
  **Royal City** garrison/attack — exposed via the dashboard and WS API

> Planned/missing items are tracked in `docs/future_steps.md`.

---

## Architecture overview

```
                    +-------------------------+
                    |    BlueStacks (4K)      |
                    |  X-Clash game running   |
                    +-----+--------------+----+
                          |              ^
            Windows API   |              |  ADB (taps, swipes, keys)
             screenshots  v              |
                +------------------------+--+
                |   WindowsScreenshotHelper |
                |   ADBHelper               |
                +------------+--------------+
                             |
                             v
              +-----------------------------------+
              |  Detection layer                  |
              |   - template_matcher (CPU/GPU)    |
              |   - mask-aware (sqdiff+mask)      |
              |   - view_state_detector           |
              |   - qwen_ocr (HTTP -> local       |
              |     Qwen2.5-VL-3B server)         |
              +------------------+----------------+
                                 |
                                 v
                +--------------------------------+
                |  Flow library (scripts/flows/) |
                |  60+ task-specific flows       |
                +----+-----------------------+---+
                     |                       |
                     v                       v
        +-----------------------+   +-----------------------+
        |  icon_daemon main     |   |  daemon_server (WS)   |
        |  loop                 |   |  external triggers    |
        |   - polls view+state  |   +-----------+-----------+
        |   - selects flow      |               |
        |   - records to        |               |
        |     scheduler         |               |
        +----------+------------+               |
                   |                            |
                   v                            v
       +---------------------+        +--------------------+
       |  Scheduler (JSON)   |<-------|   Dashboard        |
       |  cooldowns          |        |   FastAPI + Alpine |
       |  daily limits       |        |   (browser UI)     |
       |  arms-race state    |        +--------------------+
       +---------------------+
```

Key state files:

| File | Purpose |
|---|---|
| `data/daemon_schedule.json` | Flow cooldowns, daily counters, arms-race block state |
| `data/daemon_current_state.json` | Live stamina, view, tavern counters, queue times |
| `data/config_overrides.json` | Runtime config overrides (dashboard-set) |

---

## How the detection pipeline works

### Why Windows screenshots (not ADB)
ADB screenshots go through a different render path and have **different
pixel values** than what's on screen. Templates extracted from a Windows
screenshot will not reliably match an ADB screenshot of the same scene.
The daemon uses `WindowsScreenshotHelper` exclusively for detection.

ADB is only used for **input** (taps, swipes, hardware-back, key events).

### Template matching
- Default method: `cv2.TM_SQDIFF_NORMED` (lower score = better, 0 = perfect)
- COLOR matching by default; grayscale is optional
- **GPU-accelerated** for full-frame searches via CUDA (~20x faster)
- **Mask-aware**: any `<name>_4k.png` template with a sibling
  `<name>_mask_4k.png` automatically uses energy-normalized masked
  correlation. This is how we handle UI elements that sit over varying
  backgrounds (popups over the world map, hero tiles, etc.) without
  background pixels poisoning the match score.

To build a mask for a template, use:
```bash
python scripts/one_off/build_mask.py \
    --single-shot screenshots/debug/<failure_shot>.png \
    --reference <existing_template>_4k.png \
    --name <name> --force
```
See `.claude/skills/screenshot-detection/TEMPLATE_EXTRACTION.md` for the
full mask recipe.

### View state machine
`utils/view_state_detector.py` classifies every frame as `TOWN`, `WORLD`,
`CHAT`, `WEBVIEW`, or `UNKNOWN`. The daemon uses these for gating (e.g.
harvest only fires in `TOWN`, rallies require `WORLD`). `return_to_base_view()`
is the canonical recovery primitive — fast-path uses simple back-button taps,
slow-path does multi-step click + hardware-back to dig out of arbitrary modal
hell.

### OCR
A local Qwen2.5-VL-3B server handles all OCR. The client wraps it as
`utils/ocr_client.py` with helpers for numbers, text, and JSON extraction.
Refusal/hallucination outputs (Qwen sometimes returns "I cannot read this
image" or hallucinates digits on empty crops) are **filtered out** in
detection layers so they never become silently wrong actions.

---

## Prerequisites

### Hardware
- Windows 10/11
- GPU with CUDA support recommended for OCR (Qwen2.5-VL-3B). RTX 30/40/50
  series tested.
- ~8 GB free RAM during operation; 4 GB VRAM for OCR

### Software
- **Python 3.12+**
- **BlueStacks 5** with Android Pie 64-bit, configured for **3840×2160 at
  560 DPI** (see `scripts/setup_bluestacks.py`)
- BlueStacks **right sidebar must be enabled** — `WindowsScreenshotHelper`
  crops 30 px from the right edge to match
- ADB available at `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- (Optional) Gemini API key for one-off element location via
  `calibration/detect_object.py`

---

## Installation

```bash
# 1. Clone
git clone <repo-url> xclash && cd xclash

# 2. Virtual env
python -m venv .venv
.venv\Scripts\activate

# 3. CUDA PyTorch (RTX 50 series example; check pytorch.org for your GPU)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 4. Other dependencies
pip install -r requirements.txt

# 5. Configure BlueStacks resolution (two-step required: 3088x1440 -> 3840x2160)
python scripts/setup_bluestacks.py

# 6. Local config overrides
cp config_local.py.example config_local.py
# Edit config_local.py: GOOGLE_API_KEY (optional), IDLE_THRESHOLD, calibration

# 7. Verify ADB connectivity
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" devices
# Should show: emulator-5554  device
```

---

## Running it

### Normal mode
```bash
python scripts/icon_daemon.py
```
Logs to `logs/current_daemon.log`. The dashboard starts on an auto-detected
free port (see startup logs for the URL, typically <http://localhost:8000>).

### Dashboard-only mode
```bash
python dashboard/server.py
```
Connects to a running daemon via WebSocket on `ws://localhost:9876`.

### CLI control
```bash
python scripts/daemon_cli.py status
python scripts/daemon_cli.py run_flow elite_zombie
python scripts/daemon_cli.py run_flow quick_production
python scripts/daemon_cli.py pause
python scripts/daemon_cli.py resume
```

---

## Web dashboard

The dashboard surfaces live state and lets you trigger flows manually:

- **Status row** — paused/running, active flow, stamina, idle time, current
  view, arms-race event + time remaining
- **Arms Race panel** — current event, points toward each chest, time to
  next block, full 7-day schedule
- **Quick Actions row** — Faction Trials, Tavern, Bag, Community check-in,
  Apply Marshall, Speedup Barracks, **Mark Quick Production Done**, etc.
- **Title management** — apply any title from `data/kingdom_titles.json`
- **Shield inventory** — list shields in bag, use one, schedule a future use
- **Zombie mode** — switch between elite / gold / food / iron-mine targets
- **Reinforce loop** — auto-reinforce the alliance city on a configurable
  interval
- **Live config overrides** — toggle features without editing files
- **Timeline** — recent flow runs with success/failure markers
- **Events feed** — incoming tavern quests, chat alerts

Mark Quick Production Done is the safety valve: if you manually use the
Class Skill in-game, click this button to make the daemon OCR the
in-game cooldown timer and update the next-run time precisely (falls back
to a flat 24h cooldown if OCR can't reach the panel).

---

## Configuration

| File | Tracked? | Purpose |
|---|---|---|
| `config.py` | yes | Defaults: positions, thresholds, feature toggles, idle threshold |
| `config_local.py` | **no** (gitignored) | Per-user overrides: API keys, calibrated positions, lower idle threshold for testing |
| `data/config_overrides.json` | no | Runtime overrides set from the dashboard |

Important parameters in `config.py`:

```python
IDLE_THRESHOLD = 300          # seconds; override in config_local.py to e.g. 30 for testing
DEBUG_SCREENSHOTS_ENABLED = False  # set True to save step screenshots for every flow

# Arms Race trigger windows (last-N-minutes of each event block)
ARMS_RACE_CONSTRUCTION_LAST_MINUTES = 20
ARMS_RACE_TECH_RESEARCH_LAST_MINUTES = 20
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 10

# Safety cap on hero upgrades per block (real stop = EXP budget, see below)
ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES = 10

# Tavern dispatch window (Pacific)
TAVERN_QUEST_START_HOUR = 6     # 06:00 PT
TAVERN_QUEST_START_MINUTE = 0
TAVERN_SERVER_RESET_HOUR = 18   # 18:00 PT
TAVERN_MIN_DISPATCH_GAP_MINUTES = 30

# Skip question-mark quests on these VS days
VS_QUESTION_MARK_SKIP_DAYS = [2, 5, 6]
```

Arms Race event metadata lives in `utils/arms_race.py`:

```python
ARMS_RACE_EVENTS = {
    "Enhance Hero": {
        "chest1": 2000, "chest2": 4000, "chest3": 12000,
        "exp_per_arms_race_point": 2000,  # in-game scoring constant
        ...
    },
    # similar for Mystic Beast / Soldier / Construction / Research
}
```

---

## Recent improvements

These are the changes that landed in the current development cycle:

### Quick Production Class Skill loop fix
The Class Skill button (in the castle action popup) had been matching at score
~0.066 against a 0.05 threshold — just close enough to miss every single retry,
causing a 15-minute retry storm that re-applied the "Minister of Domestic
Affairs" title every time. **Fix**: built a mask (`class_skill_button_mask_4k.png`)
covering the icon + text while ignoring the background corners. New match score:
**0.0000**. See `scripts/one_off/build_mask.py` for the reusable mask-extraction
helper, including a single-shot mode that uses the existing template as one half
of the diff (no daemon stop required).

### Construction & Research queue speedup picked the wrong queue
The `parse_time_remaining()` regex used a negative lookahead `(?!:)` that
**rejected** OCR captures ending in a trailing colon (e.g. `"1d 14:00:"`,
common when the seconds digits get cropped). It returned `None`, and the
"pick smaller queue" chooser fell back to "the failing queue must be empty —
use the other one". The result: speedups dumped on the BIGGER queue.
**Fix**: extracted both copies of `parse_time_remaining` to a single
`utils/time_parsing.py`, strip trailing colons before matching, switch
lookahead from `(?!:)` to `(?!\d)`. Verified with 11 test cases including
the exact failing input.

### Research speedup never clicked Complete on queue 2
The Complete-button search region was hardcoded to queue 1's row coords.
When the smaller-queue chooser picked queue 2, Complete appeared in queue 2's
row but the search looked at queue 1's row — so it was never found and never
clicked. **Fix**: anchor the search region to the actual `speedup_click`
coordinates we used. Plus full-screen fallback search + debug-screenshot-on-miss
on both construction and research flows.

### Daemon stuck on Soldier Training popup
`soldier_upgrade_flow` has multiple early-return paths that don't close the
Soldier Training popup. When one of them triggered (e.g., promote button
missing after a UI change), the daemon ended up in `view=UNKNOWN` with all
template scores at 1.000 and the main loop waiting forever for `TOWN`/`WORLD`
to come back. **Fix**: every barrack upgrade attempt now ends with a forced
`return_to_base_view(target=TOWN, respect_idle=False)` regardless of result.

### `go_to_town` silently no-op when user was active
`go_to_world` passed `respect_idle=False` but `go_to_town` did not. If you
were touching the screen, `go_to_town` returned True without actually
navigating, while saving a screenshot named `02_town.png` of whatever was
actually displayed. The Quick Production flow then assumed it had gone
TOWN -> WORLD to recenter on the castle, but really stayed where the title
flow had left it (Royal City) and tried to use a Royal City popup as the
castle action popup. **Fix**: one-line — `go_to_town` now also passes
`respect_idle=False`.

### Mark Quick Production Done dashboard button
New button + WS handler + REST endpoint that lets you tell the daemon "I
already used QP manually". If `verify_ocr=True` (default) the daemon
navigates to the Class Skill panel and OCRs the actual cooldown timer; if it
can't reach the panel (e.g., castle in protection mode showing the wrong
popup) it falls back to a flat 24h cooldown. Either way, the retry storm
stops.

### Enhance Hero — level OCR + EXP budget (major rewrite)
The old flow scanned hero tiles for "red dots" as the upgrade-needed signal.
That worked when most heroes were fresh, but became unreliable as most
heroes hit Lv150 — some maxed heroes still show transient dots while
genuinely-upgradable lower-level heroes don't.

**New approach** (`scripts/flows/hero_upgrade_arms_race_flow.py`):
1. Open Hero panel and scroll through pages (sub-Lv150 heroes cluster at the
   bottom of the roster).
2. **OCR the "Lv. NNN" banner under each visible tile** to identify the level.
   Refusal/hallucination outputs from Qwen are filtered out, and any reading
   above MAX_HERO_LEVEL (150) is rejected as a hallucination.
3. For each sub-max tile, click in and **repeat-click Upgrade**, measuring
   actual hero EXP spent per click as `owned_before - owned_after` from the
   resource line ("A / B"). This is correct even when the per-click cost
   rises as the hero levels up mid-sequence.
4. Stop when cumulative EXP spent crosses the Arms Race budget
   (`(chest3 - current_points) * exp_per_arms_race_point`).
5. Safety cap at 10 upgrades per block as a last-line defense if OCR or
   budget metadata is off.

Tested end-to-end against the live game: from 3840/12000 points, the flow
identified Reina (Lv 74), clicked 4 times spending 17M EXP, and crossed the
budget in one session.

### Mask-extraction skill upgrade
The `screenshot-detection` skill now documents the proven workflow:
existing-template + one screenshot at a different scroll position is enough
to build a mask. The reusable `build_mask.py` script supports `--single-shot`
auto-locate (no daemon stop, no second screenshot needed) and `--two-shot`
mode for new templates from scratch.

### Tavern scan: 4 tavern opens per trigger → 1
A scheduled `tavern_scan` used to open the tavern **four times** in ~30 s:
two scan passes (`_run_tavern_scan_twice`) × (scan + dispatch follow-up
that closed and reopened the panel). With the existing `is_in_tavern()`
verification + 3-attempt retry inside `_open_tavern`, the second scan pass
was almost always wasted work. **Fix**:
- `_run_tavern_scan_twice` now runs scan once (name preserved for callsite
  stability).
- `_run_dispatch_mode` split into a thin gate-check shell + an
  `_dispatch_in_open_tavern()` helper. `_run_scan_mode` calls the helper
  directly while still in the tavern instead of close+reopen. Standalone
  dispatch callers unchanged.

Single scheduled `tavern_scan` trigger now opens the tavern **once**.
Claim-mode multi-attempt is intentionally untouched — it relies on
re-checking the tavern across timing edge cases (a quest can become
claimable mid-cycle, claim animation can race the next claim's
appearance).

### Tavern dispatchable counter (three-tier model)
The dashboard now shows how many quest slots are visible without
re-opening the tavern. Three concentric tiers tracked per dispatch attempt:

- **dispatchable** (Tier 1) — total visible Go buttons on the first screen,
  any quest type. Counted via new `find_all_go_buttons()` helper that
  reuses `templates/ground_truth/go_button_4k.png` with NMS + Y bound
  `820..1700` (so the Mega Dispatch row doesn't false-positive).
- **directly_startable** (Tier 2) — subset our code can click Go on right
  now (gold-scroll + question-mark post VS-day filter).
- **refresh_candidates** = `dispatchable - directly_startable` — visible
  Gos of unsupported types the player can in-game refresh to potentially
  roll into a supported type.

A `dispatch_exhausted_date` flag fires **only when Tier 1 = 0** — truly
empty quest panel. If unsupported-type Gos are visible, daemon keeps
checking so we can refresh them later. Claim and ally are independent of
this flag.

Dashboard surface: a "Dispatchable" tile in the Tavern Quests card with a
"3+" / number / "DONE" display and a subtitle showing `X startable now +
Y refresh candidates`. New endpoints `/api/tavern-status` and
`POST /api/tavern-status/clear-exhaustion`.

Bonus fix: tightened `QUEST_LIST_Y_MAX` from 1850 to 1700 to stop the
Mega Dispatch button from matching as a fake gold-scroll quest at y=1826.

---

## Adding a new flow

The architecture is intentionally fine-grained — every detection is a
small matcher, every action is a small flow. To add one:

### 1. Get a screenshot
```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2

win = WindowsScreenshotHelper()
cv2.imwrite("element.png", win.get_screenshot_cv2())
```

### 2. Find your element with Gemini (one-off)
```bash
python calibration/detect_object.py element.png "the green Use button"
# Outputs: detect_crop.png (the cropped element) and detect_debug.png
```
Crop and save as `templates/ground_truth/your_element_4k.png`.

### 3. (Optional) Build a mask if the element sits over varying background
```bash
python scripts/one_off/build_mask.py \
    --single-shot another_screenshot.png \
    --reference your_element_4k.png \
    --name your_element --force
```

### 4. Use it in a flow
```python
from utils.template_matcher import match_template

found, score, center = match_template(
    frame, "your_element_4k.png",
    search_region=(x, y, w, h),  # optional
    threshold=0.05,
)
if found:
    adb.tap(*center, source="flow:your_flow:click_element")
```

### 5. Register with the daemon
- Add the flow to `scripts/flows/__init__.py`
- Add a trigger candidate in `scripts/icon_daemon.py` (or a manual handler
  in `utils/daemon_server.py`)
- Add a cooldown entry in `utils/scheduler.py`'s `FLOW_CONFIGS` if
  appropriate

See `.claude/skills/screenshot-detection/SKILL.md` for the full detection
playbook and `.claude/skills/template-catalog/` for an index of existing
templates with their positions and thresholds.

---

## Troubleshooting

### "No device found" / ADB connection issues
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" devices
```
If empty: restart BlueStacks, ensure ADB is enabled under Settings > Advanced.
The daemon expects `emulator-5554`; multiple emulator instances are not
supported.

### Template matching always fails (high scores)
- Confirm you're using `WindowsScreenshotHelper`, not `adb_helper.take_screenshot()`.
  ADB and Windows screenshots have **different pixel values**.
- Confirm BlueStacks is at 3840×2160 (560 DPI). `setup_bluestacks.py`
  enforces the right resolution.
- BlueStacks right sidebar must be visible (helper crops 30px from right).
- If the element matches at score 0.06 with threshold 0.05: it almost-but-not-quite
  matches — usually because the element has an active-state highlight or sits
  over a varying background. **Build a mask** rather than loosening the threshold.
  See "Recent improvements > Quick Production Class Skill loop fix" for an example.

### OCR returns wrong values or refusals
- The Qwen server may be slow to start. Wait ~20s after first daemon
  startup before testing.
- Verify: `python -c "from utils.ocr_client import OCRClient; print(OCRClient().probe_inference())"` should print `True`.
- When OCR returns refusal text ("I cannot read this image", "I'm sorry"),
  it means the crop is degenerate (empty / off-target). Check the saved step
  screenshots under `screenshots/debug/<flow>/` to confirm the crop region
  contains the expected content.

### Daemon stuck in UNKNOWN state
View detection cycling through UNKNOWN with all template scores at 1.000
means an unexpected modal is open and covering all the icons the daemon
uses for state. Recent fixes auto-recover from the Soldier Training popup
specifically; other cases need a `return_to_base_view` call to clear. The
fastest fix is `python scripts/daemon_cli.py run_flow return_to_base_view`
(or close the modal manually in BlueStacks).

### Quick Production keeps re-applying Minister of Domestic Affairs title
Indicates the flow keeps failing and retrying. Open the dashboard, click
**Mark QP Done** → daemon will OCR the actual cooldown (or default to 24h)
and stop retrying. Then check `screenshots/debug/quick_prod/` to see why the
flow couldn't reach the Class Skill panel — most commonly because the castle
is in protection mode showing a different popup.

### Construction/Research speedup hit the wrong queue
Check the daemon log for the `Queue 1/2 time: ...` lines. If one of them
shows `Nones (Time Remaining: 1d 14:00:)` or similar with a trailing colon,
that's the OCR-trailing-colon bug — fixed in `utils/time_parsing.py`. Make
sure the daemon was restarted to pick up the fix.

### Parsec / Remote Desktop display issues
`WindowsScreenshotHelper` reads from the active framebuffer. Over Parsec
or RDP the framebuffer may be downscaled or paused when the window isn't
focused. Run a debug capture and check the shape and brightness:
```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2
f = WindowsScreenshotHelper().get_screenshot_cv2()
print(f"Shape: {f.shape}, mean: {f.mean():.1f}")  # should be (2160, 3840, 3), mean > 10
```

---

## Documentation index

- `docs/README.md` — the canonical documentation index
- `docs/game_overview.md` — primer on the game and why each flow exists
- `docs/arms_race.md` — Arms Race 7-day cycle and per-event scoring
- `docs/tavern_quests.md` — Tavern quest lifecycle, dispatch window
  semantics, claim timing edge cases
- `docs/joining_rallies.md` — Rally matcher logic, daily-limit handling
- `docs/BEAST_TRAINING_LOGIC.md` — Mystic Beast Training strategy
- `docs/KINGDOM_TITLES.md` — Title application and Royal City interaction
- `docs/DASHBOARD.md` — Dashboard endpoints and UI structure
- `docs/CHAT_INTERCEPT.md` — In-game chat capture pipeline
- `docs/GAME_DATA_STORAGE.md` — Where the game stores state on disk
- `docs/EXTRACTED_ASSETS_ANALYSIS.md` — Game asset extraction notes
- `docs/future_steps.md` — Roadmap and known gaps

### Skill files (for Claude Code workflow)
- `.claude/skills/daemon-flow/` — Daemon flow documentation, WebSocket API
- `.claude/skills/screenshot-detection/` — Detection / template / mask
  workflow including `TEMPLATE_EXTRACTION.md`
- `.claude/skills/template-catalog/` — Template positions, sizes, thresholds
- `.claude/skills/mitm-proxy/` — Frida SSL bypass + MITM capture

---

## License

Personal-use automation; no warranty. Use at your own risk. The game
publisher may consider automation against their ToS; this repository is
not affiliated with or endorsed by them.

## Acknowledgments

- Qwen2.5-VL by Alibaba for the local OCR model
- Gemini for one-off element location
- OpenCV CUDA contrib for GPU template matching
- BlueStacks for the Android emulator
