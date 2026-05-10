"""
Build a masked template from two screenshots taken with different backgrounds.

Two modes:

  AUTO-LOCATE (preferred — needs an existing reference template):
    Uses template matching with a LOOSE threshold to find the icon's exact
    position in each screenshot. You don't need to know the bbox.

  MANUAL BBOX:
    You pass --bbox X Y W H. Use only if no reference template exists yet.

The pixel-diff between the two crops identifies STABLE pixels (the icon —
same in both) vs VARIABLE pixels (the background — different between
shots). Stable -> white(255) in mask, variable -> black(0).

Usage (auto-locate):
    python scripts/one_off/build_mask.py \\
        --shot1 screenshots/debug/quick_prod/20260510_134749_04_castle_popup.png \\
        --shot2 screenshots/debug/mask_capture/popup_panned.png \\
        --reference class_skill_button_4k.png \\
        --name class_skill_button --force

Usage (manual bbox):
    python scripts/one_off/build_mask.py \\
        --shot1 a.png --shot2 b.png \\
        --bbox 1520 1180 200 160 \\
        --name class_skill_button --force

Writes:
    templates/ground_truth/<name>_4k.png       (template, cropped from shot1's matched location)
    templates/ground_truth/<name>_mask_4k.png  (mask)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

TEMPLATE_DIR = REPO_ROOT / "templates" / "ground_truth"

# Per-pixel BGR L1 difference below this -> "identical"
DIFF_THRESHOLD = 10
# Morphological cleanup kernel (0 disables)
MORPH_KERNEL = 3
# Loose threshold for the auto-locate step. The whole reason we're building a
# mask is that the unmasked match is poor, so we MUST be lenient here.
AUTO_LOCATE_THRESHOLD = 0.30


def auto_locate(shot: np.ndarray, reference: np.ndarray, label: str) -> tuple[int, int, int, int]:
    """Find reference template's top-left in shot using TM_SQDIFF_NORMED. Returns (x, y, w, h)."""
    th, tw = reference.shape[:2]
    result = cv2.matchTemplate(shot, reference, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    print(f"[locate:{label}] best score={min_val:.4f} at top-left={min_loc} (lower=better)")
    if min_val > AUTO_LOCATE_THRESHOLD:
        raise RuntimeError(
            f"Auto-locate failed for {label}: score {min_val:.4f} > threshold {AUTO_LOCATE_THRESHOLD}. "
            f"The reference template is too dissimilar — pass --bbox manually."
        )
    return (min_loc[0], min_loc[1], tw, th)


def build_mask(crop1: np.ndarray, crop2: np.ndarray) -> np.ndarray:
    if crop1.shape != crop2.shape:
        raise ValueError(f"Crop shape mismatch: {crop1.shape} vs {crop2.shape}")
    diff = cv2.absdiff(crop1, crop2)
    diff_mag = diff.sum(axis=2).astype(np.uint16) if diff.ndim == 3 else diff.astype(np.uint16)
    mask = (diff_mag < DIFF_THRESHOLD).astype(np.uint8) * 255
    if MORPH_KERNEL > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL, MORPH_KERNEL))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shot1", type=Path, help="First screenshot (e.g. existing daemon popup)")
    ap.add_argument("--shot2", type=Path, help="Second screenshot (different background)")
    ap.add_argument("--single-shot", type=Path, help="One screenshot + --reference. The reference template IS the second half of the diff (no second screenshot needed). Use when the icon's appearance is mostly stable but background varies and you already have the existing template.")
    ap.add_argument("--reference", help="Existing template name in templates/ground_truth (auto-locate mode, or second-half source for --single-shot)")
    ap.add_argument("--bbox", nargs=4, type=int, metavar=("X", "Y", "W", "H"), help="Manual bbox (skip auto-locate)")
    ap.add_argument("--name", required=True, help="Output template base name (e.g. class_skill_button)")
    ap.add_argument("--out-dir", type=Path, default=TEMPLATE_DIR, help="Output directory")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    if not (args.shot1 and args.shot2) and not args.single_shot:
        ap.error("must provide either --shot1 + --shot2, or --single-shot")
    if args.single_shot and not args.reference:
        ap.error("--single-shot requires --reference (the existing template is the second half of the diff)")
    if (args.shot1 or args.shot2) and not args.reference and not args.bbox:
        ap.error("two-shot mode needs either --reference (auto-locate) or --bbox (manual)")

    if args.single_shot:
        img1 = cv2.imread(str(args.single_shot))
        if img1 is None: raise FileNotFoundError(args.single_shot)
        ref_path = TEMPLATE_DIR / args.reference
        ref = cv2.imread(str(ref_path))
        if ref is None:
            raise FileNotFoundError(f"reference template not found: {ref_path}")
        bbox1 = auto_locate(img1, ref, "single-shot")
        x1, y1, w, h = bbox1
        crop1 = img1[y1:y1+h, x1:x1+w]   # the LIVE icon (with current state, e.g. glow)
        crop2 = ref                        # the EXISTING template (no glow / older background)
        if crop1.shape != crop2.shape:
            raise RuntimeError(f"crop/reference shape mismatch: {crop1.shape} vs {crop2.shape}")
    else:
        img1 = cv2.imread(str(args.shot1))
        img2 = cv2.imread(str(args.shot2))
        if img1 is None: raise FileNotFoundError(args.shot1)
        if img2 is None: raise FileNotFoundError(args.shot2)
        if img1.shape != img2.shape:
            raise ValueError(f"Screenshots differ in shape: {img1.shape} vs {img2.shape}")

        if args.reference:
            ref_path = TEMPLATE_DIR / args.reference
            ref = cv2.imread(str(ref_path))
            if ref is None:
                raise FileNotFoundError(f"reference template not found: {ref_path}")
            bbox1 = auto_locate(img1, ref, "shot1")
            bbox2 = auto_locate(img2, ref, "shot2")
        else:
            bbox1 = bbox2 = tuple(args.bbox)

        x1, y1, w, h = bbox1
        x2, y2, _, _ = bbox2
        crop1 = img1[y1:y1+h, x1:x1+w]
        crop2 = img2[y2:y2+h, x2:x2+w]

    mask = build_mask(crop1, crop2)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    template_path = args.out_dir / f"{args.name}_4k.png"
    mask_path = args.out_dir / f"{args.name}_mask_4k.png"

    if not args.force:
        for p in (template_path, mask_path):
            if p.exists():
                print(f"REFUSING: {p} exists. Use --force.", file=sys.stderr)
                return 2

    # Write the live crop (not the original reference) as the new template, so
    # the saved template reflects the icon's CURRENT in-game appearance.
    cv2.imwrite(str(template_path), crop1)
    cv2.imwrite(str(mask_path), mask)

    coverage = 100.0 * np.sum(mask == 255) / mask.size
    print(f"Wrote {template_path}  ({w}x{h})")
    print(f"Wrote {mask_path}      ({w}x{h})")
    print(f"Mask coverage: {coverage:.1f}% white (opaque) — typical 30%-80%")
    if coverage < 20:
        print("WARN: low coverage — bbox too large, or scenes too different. Consider tighter bbox.")
    elif coverage > 90:
        print("WARN: high coverage — scenes too similar. Pan map further between captures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
