# Action Capture & Replay

Records **every on-screen action** (tap / swipe / key_event / zoom / arrow) with a
screenshot **before** the command, the command itself, and a **burst of screenshots
after** — for visual debugging of misfires and for replaying a session.

This is the **single screenshot-persistence system** in the project. All the old
per-flow debug-screenshot writers are disabled by default (see "Only one system"
below); the only other screenshot on disk is the manual one from the dashboard button.

## How it works

- Interception lives **inside `ADBHelper.tap/swipe/key_event`** (`utils/adb_helper.py`),
  the single choke point every flow's clicks go through — so it covers every action
  with zero per-call-site changes. The two Win32 paths (`utils/send_zoom.py`,
  `utils/send_arrow_proper.py`) are wrapped explicitly.
- Core module: **`utils/action_capture.py`** (`ActionCapture` singleton via
  `get_action_capture()`). The before-shot is grabbed synchronously (it must precede
  the send); the after-burst and all PNG encoding run on background threads so clicks
  are never blocked.
- The daemon shares its `WindowsScreenshotHelper` and starts a session at startup
  (`scripts/icon_daemon.py`).

## Where it writes

```
screenshots/action_capture/<session_id>/
  actions.jsonl            # one record per action (final)
  actions.pre.jsonl        # crash-safe pre-records
  <seq>_before.png         # full 4K lossless PNG
  <seq>_after_00.png ...   # after-burst frames
```

One session per daemon run. Images are **full-resolution lossless PNG** on purpose —
they must stay pixel-exact so they can be used for template matching. Do **not** switch
to JPEG or downscale.

### Record schema (per line of `actions.jsonl`)

`seq, session_id, ts, ts_sent, source, action_type, params, device, resolution,
before_shot, after_shots[], after_dropped, prev_seq, delay_before_ms`

`params` by type: tap `{x,y}` · swipe `{x1,y1,x2,y2,duration}` · key_event `{keycode}`
· zoom/arrow `{direction}`.

## Config (`config.py`, override in `config_local.py`)

| Key | Default | Notes |
|-----|---------|-------|
| `ACTION_CAPTURE_ENABLED` | `True` | master switch (ANDs with runtime toggle) |
| `ACTION_CAPTURE_BURST_COUNT` | `6` | after-shots per action |
| `ACTION_CAPTURE_BURST_INTERVAL_MS` | `330` | ~2s total for 6 |
| `ACTION_CAPTURE_FORMAT` | `"png"` | **keep png** (lossless, template-match safe) |
| `ACTION_CAPTURE_DOWNSCALE` | `1.0` | **keep 1.0** (full 4K) |
| `ACTION_CAPTURE_MAX_GB` | `40.0` | rolling byte cap for the whole dir |
| `ACTION_CAPTURE_MAX_AGE_HOURS` | `24` | drop whole sessions older than this |
| `ACTION_CAPTURE_MAX_INFLIGHT_BURSTS` | `16` | backpressure: drop after-burst past this |

### Disk bounding (important)

Full-4K-PNG bursts are ~9 MB/frame → **~60 MB per 6-shot click**. The pruner
(`ActionCapture._prune`) enforces the byte cap by deleting **oldest frames first
across ALL sessions, including the active one** (keeping the small `.jsonl` logs).

> History: the original pruner only deleted whole *old* sessions and protected the
> active one, so a single long daemon run grew unbounded and filled a 953 GB disk.
> The current pruner trims the active session too. Regression test:
> `tests/unit/test_action_capture.py::test_prune_trims_current_session_over_cap`.

## Runtime control

- Dashboard **"Captures" tab**: browse sessions, filter by source/time, scrub each
  action's before/after filmstrip; REC on/off toggle + live disk/queue status.
- Endpoints (`dashboard/server.py`): `/api/action-capture/{sessions,list,action/{seq},
  image,state,start,stop}`.
- Daemon-server / CLI: `start_action_capture`, `stop_action_capture`,
  `get_action_capture_status`.

## Replay

```
python -m scripts.replay_actions --session latest [--source-filter flow:x] \
    [--since ISO] [--until ISO] [--speed 1.0] [--max-actions N] [--dry-run]
```

Re-issues the recorded command stream through `ADBHelper`, honoring the inter-action
delays. **Open-loop, no visual verification** — reliable only for short deterministic
sequences from the same starting screen; game-state divergence desyncs coordinate taps.
Not a general macro engine. `--max-actions` defaults small on purpose.

## Only one screenshot system

The action-capture module is the sole screenshot-persistence system. The old debug
writers are off:

- `DEBUG_SCREENSHOTS_ENABLED = False` gates the shared `save_debug_screenshot()` /
  `DaemonDebugCapture` and the per-flow `_save_*` helpers.
- Per-flow `DEBUG_*_FLOW` flags and `DEBUG_RETURN_TO_BASE` are `False` (these dumped
  4K PNGs unbounded and grew `screenshots/debug` to 458 GB).
- `cleanup_old_screenshots()` is a deprecated no-op (it never worked; action-capture
  owns its own cleanup now).
- Kept: the **manual** dashboard screenshot button (`/api/screenshot` →
  `screenshots/debug/manual_screenshot_*.png`).

To debug a specific flow again, set `DEBUG_SCREENSHOTS_ENABLED = True` (or a single
`DEBUG_*_FLOW`) in `config_local.py` temporarily.

## Safety note

Capture is a **bullet-proof no-op when there is no game window** (tests, standalone
scripts) — it catches the missing-window error once and latches disabled, so it never
breaks `ADBHelper`. `tests/conftest.py` also force-disables it for the whole suite.
