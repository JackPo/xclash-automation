# Template Matching Audit Suggestions

## High-risk mismatches (likely false positives or wrong clicks)
1) Overly high SQDIFF thresholds (lower is better) will almost always pass.
   Evidence: utils/view_state_detector.py:191 uses threshold=0.98 with match_template on back_button_union_4k.png.
   Risk: UNKNOWN state recovery may click back repeatedly even when no back button exists.
   Suggestion: Use masked default (0.05) or a tuned SQDIFF threshold; log scores before changing.

2) Rally/Scout detection in Royal City uses SQDIFF thresholds that are effectively "always true".
   Evidence: scripts/flows/royal_city_flow.py:228 and scripts/flows/royal_city_flow.py:239 use threshold=0.90.
   Risk: False positives -> wrong button clicks (rally/scout/attack).
   Suggestion: Use a masked-default threshold (0.05) or re-tune; consider has_mask-based thresholds.

3) Masked templates used with explicit thresholds that ignore masked defaults.
   Evidence: scripts/flows/royal_city_flow.py:228, scripts/flows/royal_city_flow.py:239,
             scripts/flows/royal_city_flow.py:64 (attack uses 0.10 while mask exists).
   Risk: Inconsistent acceptance across masked templates; hidden false positives.
   Suggestion: Centralize thresholds per template or use has_mask to pick 0.05 vs 0.10.

## Consistency gaps (tests/docs do not match implementation)
4) Unit tests still assert CCORR behavior, but template_matcher uses SQDIFF for all paths.
   Evidence: tests/unit/test_template_matcher.py:263, tests/unit/test_template_matcher.py:279,
             tests/unit/test_template_matcher.py:738.
   Risk: Tests are misleading or failing; reviewers may reintroduce "higher is better" errors.
   Suggestion: Update tests to validate SQDIFF semantics or reintroduce CCORR intentionally.

5) Comments reference CCORR or mixed scoring that no longer exists.
   Evidence: utils/back_button_matcher.py:33 and tests/test_templates.py:94 mention CCORR.
   Risk: Future edits may revert to "high score is good" assumptions.
   Suggestion: Update docs/comments to state SQDIFF and "lower is better".

## Partial migration / grayscale holdouts (verify thresholds)
6) Grayscale-only matchers remain, so their thresholds may not match the new color pipeline.
   Evidence:
     - utils/rally_plus_matcher.py:56 and utils/rally_plus_matcher.py:60 (IMREAD_GRAYSCALE + cvtColor)
     - utils/shaded_button_helper.py:50 and utils/shaded_button_helper.py:63
     - utils/arms_race_panel_helper.py:113 and utils/arms_race_panel_helper.py:118
     - utils/soldier_panel_slider.py:48 and utils/soldier_panel_slider.py:66
     - utils/hospital_panel_helper.py:68 and utils/hospital_panel_helper.py:93
     - utils/arms_race_ocr.py:150 and utils/arms_race_ocr.py:197
   Risk: Thresholds tuned for grayscale could under/over-match compared to color templates.
   Suggestion: Decide whether these should stay grayscale or move to color; re-tune thresholds accordingly.

7) Direct cv2.matchTemplate calls bypass template_matcher, so mask detection and defaults are skipped.
   Evidence (non-exhaustive):
     - utils/return_to_base_view.py:67, utils/replenish_all_helper.py:116,
       utils/training_slider_helper.py:261, utils/ally_quest_scanner.py:120
     - scripts/flows/rally_join_flow.py:169, scripts/flows/harvest_box_flow.py:81,
       scripts/flows/tavern_quest_flow.py:275
     - scripts/icon_daemon.py:942
   Risk: Inconsistent thresholds, no mask usage, and mixed color/grayscale assumptions.
   Suggestion: Either migrate these to template_matcher or explicitly document why they are special cases.

## Masked template audit (verify call sites use masked thresholds)
8) Templates with masks present in templates/ground_truth:
   back_button_union_4k.png, bag_button_4k.png, search_button_4k.png, rally_button_4k.png,
   royal_city_attack_button_4k.png, royal_city_scout_button_4k.png, title_active_icon_4k.png,
   treasure_ready_circle_4k.png, treasure_not_ready_circle_4k.png, corn_harvest_bubble_4k.png,
   gem_tight_4k.png, gold_coin_tight_4k.png, iron_bar_tight_4k.png.
   Risk: Any call site that hard-codes threshold>0.05 may be too lax for masked SQDIFF.
   Suggestion: Audit each call site and either use has_mask-based defaults or tune per template.

## Suggested verification steps (no code changes required to start)
9) Build a quick score report:
   - Log raw match scores and thresholds for masked vs non-masked templates during normal runs.
   - Flag any template whose "best match" is near threshold in common flows.

10) Add a static audit check:
    - Scan for thresholds >= 0.2 when using SQDIFF_NORMED.
    - Report any match_template call that passes a threshold but ignores has_mask.

11) Add a per-template calibration table:
    - Maintain a JSON/CSV mapping of template_name -> threshold + mode (color/grayscale).
    - This reduces ad-hoc thresholds embedded across flows.
