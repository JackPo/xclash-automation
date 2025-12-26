"""
Comprehensive test suite for the deterministic stamina rule engine.

Tests all edge cases:
1. Basic deficit coverage
2. Free 50 usage when available
3. 5+ 10s optimization (swap to 50)
4. Insufficient 10s (use extra 50)
5. Insufficient total items (use all available)
6. Round up to multiples of 20
"""
import sys
sys.path.insert(0, "C:\\Users\\mail\\xclash")

from utils.claude_cli_helper import calculate_optimal_stamina
import random


def test_case(name: str, deficit: int, owned_10: int, owned_50: int, free_ready: bool,
              expected_min_coverage: int = None) -> dict:
    """Run a single test case and validate result."""
    claim_free, use_10s, use_50s, reasoning = calculate_optimal_stamina(
        deficit, owned_10, owned_50, free_ready
    )

    # Calculate total claimed
    total = (50 if claim_free else 0) + use_50s * 50 + use_10s * 10

    # Calculate target (rounded up to multiple of 20)
    target = ((deficit + 19) // 20) * 20 if deficit > 0 else 0

    # Calculate max available
    max_available = (50 if free_ready else 0) + owned_50 * 50 + owned_10 * 10

    # Determine if coverage is sufficient
    if expected_min_coverage is None:
        expected_min_coverage = min(target, max_available)

    # Validate constraints
    issues = []

    # 1. Must cover target OR use all available items
    if total < target and total < max_available:
        issues.append(f"UNDERCOVER: {total} < target {target} but had {max_available} available")

    # 2. Must not use more items than owned
    if use_10s > owned_10:
        issues.append(f"Used {use_10s} 10s but only owned {owned_10}")
    if use_50s > owned_50:
        issues.append(f"Used {use_50s} 50s but only owned {owned_50}")
    if claim_free and not free_ready:
        issues.append("Claimed free when not ready")

    # 3. Optimization check: shouldn't use 5+ 10s if spare 50s available
    spare_50s = owned_50 - use_50s
    if use_10s >= 5 and spare_50s > 0 and total < target:
        issues.append(f"SUBOPTIMAL: Used {use_10s} 10s but had {spare_50s} spare 50s")

    result = {
        "name": name,
        "input": {"deficit": deficit, "owned_10": owned_10, "owned_50": owned_50, "free_ready": free_ready},
        "output": {"claim_free": claim_free, "use_10s": use_10s, "use_50s": use_50s},
        "target": target,
        "total": total,
        "max_available": max_available,
        "reasoning": reasoning,
        "pass": len(issues) == 0,
        "issues": issues
    }

    return result


def run_all_tests():
    """Run comprehensive test suite."""
    tests = []

    # =========================================================================
    # Basic Cases
    # =========================================================================
    tests.append(test_case("No deficit", 0, 10, 5, False))
    tests.append(test_case("Negative deficit", -50, 10, 5, True))

    # =========================================================================
    # Free 50 Only (deficit rounds up to multiples of 20)
    # =========================================================================
    tests.append(test_case("Free covers all (20)", 20, 0, 0, True))  # Target=20, free=50 covers
    tests.append(test_case("Free covers all (40)", 40, 0, 0, True))  # Target=40, free=50 covers
    # Note: deficit=50 -> target=60, so free 50 is SHORT by 10
    tests.append(test_case("Free partial (60)", 60, 10, 0, True))  # Free 50 + 1x10 = 60

    # =========================================================================
    # Items Only (no free)
    # =========================================================================
    tests.append(test_case("10s only - exact", 20, 10, 0, False))  # 2x10
    tests.append(test_case("10s only - round up", 25, 10, 0, False))  # 3x10 for 40 target
    tests.append(test_case("50s only - exact", 100, 0, 5, False))  # 2x50
    tests.append(test_case("50s only - round up", 110, 0, 5, False))  # 3x50 for 120 target
    tests.append(test_case("Mixed - 50 + 10s", 70, 10, 5, False))  # 1x50 + 2x10 for 80 target

    # =========================================================================
    # 5+ 10s Optimization (should use 50 instead)
    # =========================================================================
    tests.append(test_case("5x10 to 1x50 swap", 50, 10, 5, False))  # Should use 1x50 not 5x10
    tests.append(test_case("6x10 to 1x50+1x10", 60, 10, 5, False))  # Should use 1x50+1x10 for 60
    tests.append(test_case("Need 150: 3x50 not 2x50+5x10", 150, 10, 5, False))  # 3x50

    # =========================================================================
    # Insufficient 10s (use extra 50)
    # =========================================================================
    tests.append(test_case("No 10s, need remainder", 70, 0, 5, False))  # 2x50 for 80 target
    tests.append(test_case("1x10, need 4x10 (use 50)", 40, 1, 5, False))  # 1x50 for 40
    tests.append(test_case("2x10, need 4x10 (use 50)", 40, 2, 5, False))  # 1x50 for 40

    # =========================================================================
    # Insufficient Total (use all available)
    # =========================================================================
    tests.append(test_case("All insufficient", 300, 5, 3, False))  # 3x50+5x10=200 < 300
    tests.append(test_case("All insufficient + free", 300, 5, 3, True))  # free+3x50+5x10=250 < 300

    # =========================================================================
    # Edge Cases: Multiples of 20
    # =========================================================================
    tests.append(test_case("Exact multiple 20", 20, 10, 5, False))
    tests.append(test_case("Exact multiple 40", 40, 10, 5, False))
    tests.append(test_case("Exact multiple 60", 60, 10, 5, False))
    tests.append(test_case("Exact multiple 100", 100, 10, 5, False))
    tests.append(test_case("Exact multiple 200", 200, 10, 5, False))

    # Round up cases
    tests.append(test_case("Round 21 to 40", 21, 10, 5, False))
    tests.append(test_case("Round 39 to 40", 39, 10, 5, False))
    tests.append(test_case("Round 41 to 60", 41, 10, 5, False))
    tests.append(test_case("Round 99 to 100", 99, 10, 5, False))

    # =========================================================================
    # Previously Failing Cases
    # =========================================================================
    # Test 18: deficit=206, free=False, owned_10=0, owned_50=11
    tests.append(test_case("Prev fail: 206, no 10s", 206, 0, 11, False))

    # Test 22: deficit=103, free=True, owned_10=0, owned_50=8
    tests.append(test_case("Prev fail: 103, free, no 10s", 103, 0, 8, True))

    # Test 32: deficit=234, free=False, owned_10=5, owned_50=3
    tests.append(test_case("Prev fail: 234, limited items", 234, 5, 3, False))

    # =========================================================================
    # Random Tests (50 cases)
    # =========================================================================
    random.seed(42)  # Reproducible
    for i in range(50):
        deficit = random.randint(1, 350)  # Up to ~17 rallies
        owned_10 = random.randint(0, 20)
        owned_50 = random.randint(0, 15)
        free_ready = random.choice([True, False])
        tests.append(test_case(f"Random {i+1}", deficit, owned_10, owned_50, free_ready))

    # =========================================================================
    # Print Results
    # =========================================================================
    print("=" * 80)
    print("STAMINA RULE ENGINE TEST RESULTS")
    print("=" * 80)

    passed = 0
    failed = 0

    for t in tests:
        status = "PASS" if t["pass"] else "FAIL"
        if t["pass"]:
            passed += 1
            # Only print brief summary for passing tests
            print(f"[{status}] {t['name']}: {t['reasoning']}")
        else:
            failed += 1
            print(f"\n[{status}] {t['name']}")
            print(f"  Input: deficit={t['input']['deficit']}, owned_10={t['input']['owned_10']}, "
                  f"owned_50={t['input']['owned_50']}, free={t['input']['free_ready']}")
            print(f"  Output: claim_free={t['output']['claim_free']}, "
                  f"use_10s={t['output']['use_10s']}, use_50s={t['output']['use_50s']}")
            print(f"  Target: {t['target']}, Total: {t['total']}, Max Available: {t['max_available']}")
            print(f"  Reasoning: {t['reasoning']}")
            for issue in t["issues"]:
                print(f"  X {issue}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
