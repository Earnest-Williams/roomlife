#!/usr/bin/env python3
"""Content validation tool for RoomLife.

This tool validates that:
1. All actions can be reached/validated by archetypes
2. Tier distributions are rich (not all tier 0 or all tier 3)
3. Actions have reasonable requirements and outcomes

Usage:
    python tools/validate_content.py [--packs]
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from roomlife import engine
from roomlife.action_engine import preview_tier_distribution, validate_action_spec
from roomlife.models import State


def create_archetype_states() -> Dict[str, State]:
    """Create several archetype states representing typical player conditions.

    Returns:
        Dict mapping archetype name to State
    """
    archetypes = {}

    # Archetype 1: Fresh start (default new game)
    archetypes["fresh_start"] = engine.new_game(seed=123)

    # Archetype 2: Skilled player with money
    skilled = engine.new_game(seed=456)
    for skill_name in skilled.player.skills_detailed:
        skilled.player.skills_detailed[skill_name].value = 50.0
    skilled.player.money_pence = 10000
    archetypes["skilled"] = skilled

    # Archetype 3: Broke and desperate
    broke = engine.new_game(seed=789)
    broke.player.money_pence = 100
    broke.player.needs.hunger = 80
    broke.player.needs.fatigue = 70
    broke.player.needs.hygiene = 80
    archetypes["broke"] = broke

    # Archetype 4: High skill master
    master = engine.new_game(seed=999)
    for skill_name in master.player.skills_detailed:
        master.player.skills_detailed[skill_name].value = 100.0
    master.player.money_pence = 50000
    archetypes["master"] = master

    return archetypes


def check_action_reachability(
    action_id: str,
    spec: Any,
    item_meta: Dict[str, Any],
    archetypes: Dict[str, State],
) -> Dict[str, Any]:
    """Check if an action is reachable by at least one archetype.

    Args:
        action_id: Action identifier
        spec: Action specification
        item_meta: Item metadata
        archetypes: Dict of archetype states

    Returns:
        Dict with reachability info:
        {
            "reachable": bool,
            "reachable_by": [archetype_names],
            "common_missing": [requirements that block all archetypes]
        }
    """
    reachable_by = []
    validation_results = {}

    for archetype_name, state in archetypes.items():
        ok, reason, missing = validate_action_spec(state, spec, item_meta, params=None)
        validation_results[archetype_name] = {
            "ok": ok,
            "reason": reason,
            "missing": missing,
        }
        if ok:
            reachable_by.append(archetype_name)

    # Find common missing requirements (blockers across all archetypes)
    if not reachable_by:
        # Action is unreachable - find common blockers
        all_missing = [set(v["missing"]) for v in validation_results.values()]
        common_missing = list(set.intersection(*all_missing)) if all_missing else []
    else:
        common_missing = []

    return {
        "reachable": len(reachable_by) > 0,
        "reachable_by": reachable_by,
        "common_missing": common_missing,
        "validation_results": validation_results,
    }


def check_tier_richness(
    action_id: str,
    spec: Any,
    item_meta: Dict[str, Any],
    state: State,
) -> Dict[str, Any]:
    """Check if tier distribution is rich (not degenerate).

    A "rich" tier distribution has:
    - At least 2 different tiers with non-zero probability
    - No single tier dominates (>90% probability)

    Args:
        action_id: Action identifier
        spec: Action specification
        item_meta: Item metadata
        state: Game state for tier computation

    Returns:
        Dict with tier richness info:
        {
            "rich": bool,
            "tier_distribution": {0: 0.11, 1: 0.33, 2: 0.44, 3: 0.11},
            "num_tiers": 3,
            "max_tier_prob": 0.44,
            "issues": ["single tier dominates", ...]
        }
    """
    tier_dist = preview_tier_distribution(state, spec, item_meta, rng_seed=12345, samples=9)

    num_tiers = sum(1 for prob in tier_dist.values() if prob > 0)
    max_tier_prob = max(tier_dist.values())

    issues = []
    if num_tiers < 2:
        issues.append("degenerate: only 1 tier occurs")
    if max_tier_prob > 0.9:
        issues.append(f"single tier dominates ({max_tier_prob:.0%})")

    return {
        "rich": len(issues) == 0,
        "tier_distribution": tier_dist,
        "num_tiers": num_tiers,
        "max_tier_prob": max_tier_prob,
        "issues": issues,
    }


def validate_content() -> Dict[str, Any]:
    """Run all content validation checks.

    Returns:
        Dict with validation results and metrics
    """
    # Ensure specs are loaded (including packs)
    engine._ensure_specs_loaded()

    # Create archetypes
    archetypes = create_archetype_states()

    # Run validation checks
    results = {
        "total_actions": len(engine._ACTION_SPECS),
        "reachability": {},
        "tier_richness": {},
        "unreachable_actions": [],
        "degenerate_tiers": [],
    }

    # Check each action
    for action_id, spec in sorted(engine._ACTION_SPECS.items()):
        # Reachability check
        reachability = check_action_reachability(action_id, spec, engine._ITEM_META, archetypes)
        results["reachability"][action_id] = reachability

        if not reachability["reachable"]:
            results["unreachable_actions"].append({
                "action_id": action_id,
                "common_missing": reachability["common_missing"],
            })

        # Tier richness check (use "skilled" archetype as baseline)
        tier_richness = check_tier_richness(action_id, spec, engine._ITEM_META, archetypes["skilled"])
        results["tier_richness"][action_id] = tier_richness

        if not tier_richness["rich"]:
            results["degenerate_tiers"].append({
                "action_id": action_id,
                "issues": tier_richness["issues"],
                "tier_distribution": tier_richness["tier_distribution"],
            })

    # Compute summary metrics
    results["metrics"] = {
        "total_actions": results["total_actions"],
        "reachable_actions": sum(1 for r in results["reachability"].values() if r["reachable"]),
        "unreachable_actions": len(results["unreachable_actions"]),
        "rich_tiers": sum(1 for r in results["tier_richness"].values() if r["rich"]),
        "degenerate_tiers": len(results["degenerate_tiers"]),
        "reachability_rate": sum(1 for r in results["reachability"].values() if r["reachable"]) / len(engine._ACTION_SPECS) if engine._ACTION_SPECS else 0.0,
        "tier_richness_rate": sum(1 for r in results["tier_richness"].values() if r["rich"]) / len(engine._ACTION_SPECS) if engine._ACTION_SPECS else 0.0,
    }

    return results


def print_report(results: Dict[str, Any]) -> None:
    """Print validation report to console.

    Args:
        results: Validation results from validate_content()
    """
    metrics = results["metrics"]

    print("=" * 70)
    print("ROOMLIFE CONTENT VALIDATION REPORT")
    print("=" * 70)
    print()
    print(f"Total actions: {metrics['total_actions']}")
    print(f"Reachable actions: {metrics['reachable_actions']} ({metrics['reachability_rate']:.1%})")
    print(f"Unreachable actions: {metrics['unreachable_actions']}")
    print(f"Rich tier distributions: {metrics['rich_tiers']} ({metrics['tier_richness_rate']:.1%})")
    print(f"Degenerate tier distributions: {metrics['degenerate_tiers']}")
    print()

    if results["unreachable_actions"]:
        print("UNREACHABLE ACTIONS:")
        print("-" * 70)
        for item in results["unreachable_actions"]:
            print(f"  {item['action_id']}")
            if item["common_missing"]:
                print(f"    Common blockers: {', '.join(item['common_missing'])}")
        print()

    if results["degenerate_tiers"]:
        print("DEGENERATE TIER DISTRIBUTIONS:")
        print("-" * 70)
        for item in results["degenerate_tiers"]:
            print(f"  {item['action_id']}")
            print(f"    Issues: {', '.join(item['issues'])}")
            tier_dist_str = ", ".join(f"T{t}:{p:.0%}" for t, p in sorted(item['tier_distribution'].items()) if p > 0)
            print(f"    Distribution: {tier_dist_str}")
        print()

    print("=" * 70)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 = pass, 1 = validation failures)
    """
    print("Loading content and running validation checks...")
    print()

    results = validate_content()
    print_report(results)

    # Define thresholds for pass/fail
    REACHABILITY_THRESHOLD = 0.90  # At least 90% of actions should be reachable
    TIER_RICHNESS_THRESHOLD = 0.70  # At least 70% of actions should have rich tier distributions

    metrics = results["metrics"]
    passed = True

    if metrics["reachability_rate"] < REACHABILITY_THRESHOLD:
        print(f"FAIL: Reachability rate {metrics['reachability_rate']:.1%} below threshold {REACHABILITY_THRESHOLD:.1%}")
        passed = False

    if metrics["tier_richness_rate"] < TIER_RICHNESS_THRESHOLD:
        print(f"FAIL: Tier richness rate {metrics['tier_richness_rate']:.1%} below threshold {TIER_RICHNESS_THRESHOLD:.1%}")
        passed = False

    if passed:
        print("PASS: All validation checks passed!")
        return 0
    else:
        print("FAIL: Some validation checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
