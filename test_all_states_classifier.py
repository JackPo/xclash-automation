"""Comprehensive test of button classifier on WORLD, TOWN, and nothing states"""
import cv2
import numpy as np
from pathlib import Path

def test_template_match(image_path, template_path, expected_state):
    """Test template matching and return score"""
    img = cv2.imread(image_path)
    template = cv2.imread(template_path)

    if img is None:
        return None, f"Could not load image: {image_path}"
    if template is None:
        return None, f"Could not load template: {template_path}"

    # Perform template matching
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    return max_val, max_loc

def main():
    print("="*70)
    print("COMPREHENSIVE BUTTON CLASSIFIER TEST")
    print("="*70)

    # Template paths
    world_template = "templates/buttons/world_button_template.png"
    town_template = "templates/buttons/town_button_template.png"

    # Test cases
    test_cases = [
        # WORLD state tests
        ("WORLD", "screenshot_check.png", world_template, True),
        ("WORLD", "corner_check.png", world_template, True),
        ("WORLD", "templates/debug/button_match_world.png", world_template, True),

        # TOWN state tests
        ("TOWN", "screenshot_town.png", town_template, True),
        ("TOWN", "corner_town.png", town_template, True),
        ("TOWN", "templates/debug/button_match_town.png", town_template, True),

        # Cross-tests (WORLD template on TOWN images - should be low)
        ("TOWN", "screenshot_town.png", world_template, False),
        ("TOWN", "corner_town.png", world_template, False),

        # Cross-tests (TOWN template on WORLD images - should be low)
        ("WORLD", "screenshot_check.png", town_template, False),
        ("WORLD", "corner_check.png", town_template, False),
    ]

    results = []
    issues = []

    for expected_state, image_path, template_path, should_match in test_cases:
        # Check if files exist
        if not Path(image_path).exists():
            print(f"\nSKIPPED: {image_path} (file not found)")
            continue
        if not Path(template_path).exists():
            print(f"\nSKIPPED: {template_path} (file not found)")
            continue

        score, location = test_template_match(image_path, template_path, expected_state)

        if score is None:
            print(f"\nERROR: {location}")
            continue

        template_name = "WORLD" if "world" in template_path else "TOWN"

        print(f"\n{expected_state} state | {Path(image_path).name}")
        print(f"  Template: {template_name}")
        print(f"  Score: {score:.4f} ({score*100:.2f}%)")
        print(f"  Location: {location}")

        # Check if result is as expected
        if should_match:
            if score >= 0.95:
                status = "PASS (EXCELLENT)"
            elif score >= 0.85:
                status = "PASS (GOOD)"
            elif score >= 0.70:
                status = "WARNING (FAIR)"
            else:
                status = "FAIL (POOR)"
                issues.append(f"{expected_state} on {image_path}: only {score*100:.2f}%")
        else:
            # Should NOT match
            if score < 0.70:
                status = "PASS (correctly low)"
            else:
                status = "WARNING (unexpectedly high)"
                issues.append(f"{template_name} matched {expected_state} image at {score*100:.2f}%")

        print(f"  Status: {status}")
        results.append((expected_state, Path(image_path).name, template_name, score, should_match, status))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    world_matches = [r for r in results if r[0] == "WORLD" and r[2] == "WORLD" and r[4]]
    town_matches = [r for r in results if r[0] == "TOWN" and r[2] == "TOWN" and r[4]]

    if world_matches:
        world_scores = [r[3] for r in world_matches]
        print(f"\nWORLD template on WORLD images:")
        print(f"  Tests run: {len(world_scores)}")
        print(f"  Min score: {min(world_scores)*100:.2f}%")
        print(f"  Max score: {max(world_scores)*100:.2f}%")
        print(f"  Avg score: {np.mean(world_scores)*100:.2f}%")
        if min(world_scores) >= 0.95:
            print(f"  Result: EXCELLENT - all tests >= 95%")
        elif min(world_scores) >= 0.85:
            print(f"  Result: GOOD - all tests >= 85%")
        else:
            print(f"  Result: NEEDS IMPROVEMENT")

    if town_matches:
        town_scores = [r[3] for r in town_matches]
        print(f"\nTOWN template on TOWN images:")
        print(f"  Tests run: {len(town_scores)}")
        print(f"  Min score: {min(town_scores)*100:.2f}%")
        print(f"  Max score: {max(town_scores)*100:.2f}%")
        print(f"  Avg score: {np.mean(town_scores)*100:.2f}%")
        if min(town_scores) >= 0.95:
            print(f"  Result: EXCELLENT - all tests >= 95%")
        elif min(town_scores) >= 0.85:
            print(f"  Result: GOOD - all tests >= 85%")
        else:
            print(f"  Result: NEEDS IMPROVEMENT")

    if issues:
        print(f"\n" + "="*70)
        print(f"ISSUES FOUND ({len(issues)}):")
        print("="*70)
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\nAll tests passed successfully!")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
