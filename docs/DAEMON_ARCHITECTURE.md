# Daemon Architecture (post-refactor, 2026-07-10; hazards updated 2026-07-11)

One screen + one input channel → **detection parallelizes, action serializes.**

```
 frames (every capture anywhere: main loop, flows, action-capture)
   │  publish hook in WindowsScreenshotHelper.get_screenshot_cv2
   ▼
 FrameBus (utils/frame_bus.py)          latest-frame pub/sub, zero extra GDI
   │
   ▼
 DetectorThread (utils/opportunity_detector.py)   ~2 ticks/s, never taps,
   │  classify view ONCE per frame                never blocked by flows
   ├─ DetectorSpecs (~20)  → OpportunityBoard (sightings, TTL)
   ├─ TrackerSpecs (3)     → vote histories + stamina (2s cadence,
   │                          busy-suppressed, single-writer)
   └─ PerceptionState      → last reading per spec, view persistence
   ▼
 IntentQueue (utils/intent_queue.py)    THE single action funnel
   │  producers: candidates (main loop), manual commands (priority 100),
   │             schedules; coalesce-by-name, admission-at-POP, TTL,
   │             pre_execute re-verify, on_complete callbacks
   ▼
 Actor (icon_daemon run() → _dispatch_intents)   pops best ADMISSIBLE intent,
    executes ONE flow at a time via _run_flow (active_flows/critical markers
    preserved for dashboard/API)
```

## Key invariants

- **Perception never taps.** DetectorSpecs are read-only `frame -> (found, score, center)`.
- **Single writer for mutating state.** Hospital/barracks vote histories and the
  stamina reader are fed ONLY by perception TrackerSpecs (at the legacy 2s
  cadence — the 10-reading 60% vote rule is a time window in disguise).
  Trackers are suppressed while the actor executes (mid-flow frames poison
  votes) and reject frames older than 1.5s.
- **Corrupt frames never reach perception** (publish happens after the
  black-band check; "corrupt" = ≥90% pure black, i.e. a whole unwritten frame).
- **Admission at pop, not submit.** An intent waits in the queue until its
  gates pass (idle thresholds, tavern guard, mode flags) — this replaced the
  old deferred_flow_queue. TTL bounds the wait; expiry is logged with the last
  denial reason.
- **Manual = priority 100.** Web/CLI commands outrank everything and pop the
  moment the current flow ends. Responses are truthful: `started` /
  `queued behind X` / `busy (Ns in)` / `already queued (waiting on: <reason>)`.
  `get_status` exposes the whole queue (name/priority/age/last_denial).
- **Blind-tap flows re-verify.** treasure/harvest_box/afk get a pre_execute
  fresh-frame check at pop time; flows with internal re-checks don't need it.
- **Recovery yields to the user.** `_should_abort_for_user_activity` has
  cumulative fight detection: user activity across 3 checks → recovery stops
  entirely (covers click-cadence jitter the instant-check misses).
  **Paused = zero game touch**, including startup recovery.
- **Rollback:** `DETECTOR_THREAD_ENABLED=False` in config_local.py restores
  legacy inline scanning (every consumption site has an inline fallback via
  `_perceive`/`_sight`); the queue/actor changes revert via git.

## What still runs inline (Phase C5, pending)

Arms-race checkpoints (enhance-hero / construction / tech-research / beast
training 60-30min), soldier-training multi-barrack sequence, UNKNOWN recovery,
royal-city Friday window, reinforce/sniper mode ticks. They work through their
pre-refactor code paths inside run(). Beast training has result-dependent
block-latching that needs the on_complete callback channel — migrate carefully,
never blind (failed rallies burn troops). C7 (deleting the legacy inline
fallbacks) comes after C5.

## Hazards learned the hard way (live soak)

- **Never put `from x import y` inside run()** — Python makes the name local to
  the WHOLE function; any code path reaching the name before that line raises
  "cannot access local variable" (crashed every iteration twice: BarrackState,
  get_override_manager). AST sweep in the C4 fix verified run() is clean.
- The daemon **broadcasts events to the requesting client too** — WS readers
  must skip `type=="event"` frames and wait for `type=="response"`.
- Iteration-count cadences (gc, state save, resolution check) are TIME-based
  now — they must never be tied to loop tick rate.
- Template thresholds flap across frames: when perception sights something the
  acting flow can't confirm, back off via the skipped/cooldown_seconds result
  channel instead of re-popping every cooldown (see map_gift_box).

## Hazards, wave 2 (2026-07-11 — the "everything stopped working" night)

- **"User activity" means input AT THE GAME, not at the machine.**
  `utils/user_idle_tracker.py` originally counted ANY system input (typing in a
  terminal, clicking the dashboard, a browser overlapping the BlueStacks
  rectangle) as game activity → idle pinned at 0 → every gated action starved
  AND recovery kept "yielding to the user" who wasn't there. Now: system input
  counts only when BlueStacks is the FOREGROUND window; mouse-over checks are
  z-order aware (WindowFromPoint, not rectangle overlap); fresh processes
  start IDLE (init used to set last-activity=now, so every new process aborted
  its own first navigation); Win32 SendInput senders (`send_zoom`,
  `send_arrow`) self-mark as daemon actions at the source.
- **Yield must return failure.** All 19 `_should_abort_for_user_activity`
  sites in return_to_base_view returned TRUE on yield — callers believed
  navigation succeeded and tapped TOWN coordinates into whatever was actually
  open (with the idle bug above, EVERY call yielded instantly and "succeeded"
  while the game sat in CHAT — this alone explained most "flows stopped
  working"). Yield returns False now.
- **Left edge / bottom center = CHAT territory.** UNKNOWN-recovery edge clicks
  at (100,1080) and (1920,2050) opened the chat panel and stranded the game
  there. Removed; only right-middle and top-center remain.
- **Don't wipe perception-owned vote histories on view blips.** The loop reset
  hospital_state_history on every non-TOWN frame; the view flaps TOWN↔WORLD
  every ~10s, so the 10-vote threshold was unreachable and auto-heal was
  silently dead. Perception's tracker is already TOWN-gated — the loop-side
  reset now applies only when the loop owns the votes.
- **State actions must (re)establish their view.** Hospital taps fired blindly
  at the fixed TOWN position from whatever view was current. All hospital
  actions route through `_open_hospital_bubble()` (navigate → verify TOWN →
  tap) — and do NOT gate that tap on a single fresh bubble frame (animated
  bubble + transitional post-nav frames read IDLE; the vote history is the
  evidence).
- **Animated bubbles break per-reading thresholds.** The HELP_READY handshake
  scores 0.002↔0.079 with animation phase; a 60% vote majority is unreachable.
  Per-state vote minimums (HELP_READY 3/10) instead of one blanket rule.
- **Scheduler cooldown must come from ONE source.** `record_flow_run` backdated
  with the stale per-entry cooldown while `is_flow_ready` used the config value;
  after a config change the mismatch turned long overrides into 5-min retries
  (quick_production ran all day). Both read config now.
- **NEVER send Android BACK (keyevent 4)** — it exits the game app entirely.
  Deselect map objects by tapping empty terrain; close panels via their own
  buttons.
- **Mask filename convention**: `<name>_mask_4k.png` — the loader replaces the
  first `_4k.png`. A wrong name (e.g. `x_4k_mask_4k.png`) is silently ignored
  and matching quietly degrades to unmasked.

See also: docs/HOSPITAL_AND_ALLIANCE_HELP.md and
docs/GAME_UI_CHANGES_2026-07.md (screenshots included).
