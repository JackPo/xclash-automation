# Union Technology Donation Flow

Automation flow for donating to Union Technology research.

## Trigger conditions
- Scheduler-based cooldown (default 1 hour)
- Idle time >= `IDLE_THRESHOLD`
- TOWN view recommended (Union button is on the bottom bar)

## Flow steps
1. Click the Union button on the bottom bar.
2. Click the Union Technology menu item.
3. Verify the Technology panel header at a fixed position.
4. Find a red thumbs-up badge (donation available).
5. Click the badge (chooses the lowest badge when multiple exist).
6. Verify the donate dialog by matching the Donate 200 button.
7. Long-press the Donate button to donate.
8. Return to base view.

## Templates and fixed positions (4K)
Templates used by `scripts/flows/union_technology_flow.py`:
- `union_technology_header_4k.png`
- `tech_donate_thumbs_up_4k.png`
- `tech_donate_200_button_4k.png`

Fixed click positions:
- Union button: (3165, 2033)
- Union Technology: (2175, 1382)
- Donate 200: (2157, 1535)
- Back: (1407, 2055)

## Notes
- Detection uses `WindowsScreenshotHelper` (not ADB screenshots).
- The flow is low priority and runs after in-town actions.
- Union Gifts is handled by a separate flow (`scripts/flows/union_gifts_flow.py`).

## Related docs
- `../docs/README.md` for the documentation index
