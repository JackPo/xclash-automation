from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable, List, Tuple

import cv2
import numpy as np


IMAGE_PATH = Path("templates/debug/after_8_zooms.png")
TEMPLATE_PATH = Path("castle_cutouts/castle_011_437_823.png")
OUTPUT_TEMPLATE = Path("templates/complex_castle_{index}.png")
DEBUG_OVERLAY_PATH = Path("templates/debug/complex_castle_boxes.png")

# Bounding box padding around the detected castle center.
HALF_WIDTH = 160
UP = 210
DOWN = 210

# Matching configuration.
INITIAL_THRESHOLD = 0.55
MIN_THRESHOLD = 0.42
THRESHOLD_STEP = 0.02
MIN_SPACING = 200  # pixels between selected castle centers
REQUIRED_MATCHES = 3


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"Failed to read image: {path}")
    return img


def match_castles(
    image: np.ndarray,
    template: np.ndarray,
    initial_threshold: float,
    min_threshold: float,
    step: float,
    min_spacing: int,
    required: int,
) -> List[Tuple[float, int, int]]:
    """Return a list of (score, center_x, center_y) for the best matches."""
    res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    h, w = template.shape[:2]
    img_h, img_w = image.shape[:2]

    thresholds = np.arange(initial_threshold, min_threshold - 1e-6, -step)

    for threshold in thresholds:
        loc = np.where(res >= threshold)
        candidates = sorted(
            ((float(res[y, x]), x + w // 2, y + h // 2) for y, x in zip(*loc)),
            key=lambda item: item[0],
            reverse=True,
        )

        selected: List[Tuple[float, int, int]] = []
        for score, cx, cy in candidates:
            if cx - HALF_WIDTH < 0 or cx + HALF_WIDTH > img_w:
                continue
            if cy - UP < 0 or cy + DOWN > img_h:
                continue
            if any(
                abs(cx - px) < min_spacing and abs(cy - py) < min_spacing
                for _, px, py in selected
            ):
                continue
            selected.append((score, int(cx), int(cy)))
            if len(selected) >= required:
                return selected

    raise SystemExit(
        f"Could not find {required} castle matches using threshold down to {min_threshold}"
    )


def compute_metrics(crop: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, w = gray.shape

    # Top band (player name area).
    top_band = gray[: min(100, h), :]
    top_bright = float(np.mean(top_band > 180))

    # Middle section (castle structure).
    mid_start = max(60, h // 4)
    mid_end = min(mid_start + 140, h)
    mid_band = gray[mid_start:mid_end, :]
    mid_contrast = float(np.std(mid_band))

    # Lower band (level badge / digits).
    lower_start = min(h - 140, max(mid_end, h // 2))
    lower_band = gray[lower_start:h, :]
    lower_band_hsv = hsv[lower_start:h, :]
    lower_bright = float(np.mean(lower_band > 180))
    lower_yellow = float(
        np.mean(
            cv2.inRange(lower_band_hsv, (10, 60, 120), (45, 255, 255)) > 0
        )
    )

    return {
        "top_bright": top_bright,
        "mid_contrast": mid_contrast,
        "lower_bright": lower_bright,
        "lower_yellow": lower_yellow,
    }


def save_crops(
    image: np.ndarray,
    matches: Iterable[Tuple[float, int, int]],
    output_pattern: Path,
) -> List[dict[str, object]]:
    results = []
    for index, (score, cx, cy) in enumerate(matches, start=1):
        x1 = cx - HALF_WIDTH
        x2 = cx + HALF_WIDTH
        y1 = cy - UP
        y2 = cy + DOWN
        crop = image[y1:y2, x1:x2]
        output_path = output_pattern.with_name(output_pattern.name.format(index=index))
        cv2.imwrite(str(output_path), crop)
        metrics = compute_metrics(crop)
        results.append(
            {
                "index": index,
                "score": score,
                "center": (cx, cy),
                "bbox": (x1, y1, x2, y2),
                "path": output_path,
                "metrics": metrics,
            }
        )
    return results


def save_debug_overlay(image: np.ndarray, matches: Iterable[dict[str, object]], path: Path) -> None:
    debug = image.copy()
    for item in matches:
        x1, y1, x2, y2 = item["bbox"]  # type: ignore[assignment]
        idx = item["index"]  # type: ignore[index]
        score = item["score"]  # type: ignore[index]
        cv2.rectangle(debug, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(
            debug,
            f"{idx}:{score:.2f}",
            (x1 + 8, y1 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), debug)


def main() -> None:
    image = load_image(IMAGE_PATH)
    template = load_image(TEMPLATE_PATH)

    matches = match_castles(
        image=image,
        template=template,
        initial_threshold=INITIAL_THRESHOLD,
        min_threshold=MIN_THRESHOLD,
        step=THRESHOLD_STEP,
        min_spacing=MIN_SPACING,
        required=REQUIRED_MATCHES,
    )

    # Order matches from left to right for consistent template naming.
    matches.sort(key=lambda item: item[1])

    crops = save_crops(image, matches, OUTPUT_TEMPLATE)

    save_debug_overlay(image, crops, DEBUG_OVERLAY_PATH)

    for item in crops:
        metrics = item["metrics"]
        print(
            f"Template #{item['index']} -> {item['path']} "
            f"center={item['center']} bbox={item['bbox']} score={item['score']:.3f} "
            f"top_bright={metrics['top_bright']:.3f} "
            f"mid_contrast={metrics['mid_contrast']:.2f} "
            f"lower_bright={metrics['lower_bright']:.3f} "
            f"lower_yellow={metrics['lower_yellow']:.3f}"
        )


if __name__ == "__main__":
    main()
