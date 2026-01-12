"""Light narrative director for daily goals and pacing.

This module provides the director system that:
- Seeds 2-4 daily goals on day rollover
- Validates goals and provides tier preview notes
- Considers player needs and recent activity when choosing goals
"""

from __future__ import annotations

import random
import zlib
from typing import Any, Dict, List

from .action_engine import build_preview_notes, preview_tier_distribution, validate_action_spec
from .constants import MAX_EVENT_LOG
from .models import State


def stable_hash(s: str) -> int:
    """Stable hash using zlib.crc32 (not Python hash).

    Args:
        s: String to hash

    Returns:
        Deterministic 32-bit hash value
    """
    return zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF


def _log(state: State, event_id: str, **params: Any) -> None:
    """Log an event to the state's event log.

    Args:
        state: Game state
        event_id: Event identifier
        **params: Event parameters
    """
    state.event_log.append({"event_id": event_id, "params": params})
    if len(state.event_log) > MAX_EVENT_LOG:
        state.event_log = state.event_log[-MAX_EVENT_LOG:]


def _score_action_urgency(state: State, action_id: str, spec: Any) -> float:
    """Score how urgent/relevant an action is based on current needs.

    Args:
        state: Game state
        action_id: Action identifier
        spec: Action specification

    Returns:
        Urgency score (higher = more urgent)
    """
    score = 1.0  # Base score
    needs = state.player.needs

    # Check if action addresses high needs
    # Look at outcomes to see what needs this action affects
    for tier, outcome in spec.outcomes.items():
        deltas = outcome.get("deltas", {})
        need_deltas = deltas.get("needs", {})

        # Prioritize actions that reduce high needs
        if "hunger" in need_deltas and needs.hunger > 60:
            score += 2.0
        if "fatigue" in need_deltas and needs.fatigue > 60:
            score += 2.0
        if "hygiene" in need_deltas and needs.hygiene > 60:
            score += 1.5
        if "stress" in need_deltas and needs.stress > 50:
            score += 1.5
        if "mood" in need_deltas and needs.mood < 40:
            score += 1.0

    # Check dynamic tags for priority hints
    dynamic = spec.dynamic or {}
    director_config = dynamic.get("director", {})
    tags = director_config.get("tags", [])

    if "selfcare" in tags and (needs.hygiene > 50 or needs.mood < 50):
        score += 1.0
    if "chore" in tags:
        score += 0.5  # Lower priority for chores
    if "finance" in tags and state.player.money_pence < 2000:
        score += 1.5

    return score


def seed_daily_goals(
    state: State,
    action_specs: Dict[str, Any],
    item_meta: Dict[str, Any],
) -> None:
    """Seed 2-4 daily goals deterministically on day rollover.

    This function:
    1. Builds candidate actions where dynamic.director.suggest == true
    2. Scores candidates by urgency (based on needs/flags/etc.)
    3. Picks 2-4 goals deterministically
    4. For each goal, validates and generates tier preview
    5. Stores goals in state.player.flags["goals.today"]
    6. Logs director.goals_seeded event

    Goals are stored as a list of dicts:
    [
        {
            "action_id": "cook_basic_meal",
            "valid": True,
            "missing": [],
            "tier_distribution": {0: 0.0, 1: 0.33, 2: 0.44, 3: 0.23},
            "notes": ["Primary skill: nutrition (2.5)", "Optional: item providing 'cook_surface'"]
        },
        ...
    ]

    Args:
        state: Game state
        action_specs: Action specifications registry
        item_meta: Item metadata registry
    """
    # Use deterministic RNG seeded from simulation seed + day
    day_seed = state.world.rng_seed + state.world.day * 97
    rng = random.Random(day_seed)

    # Build candidate actions
    candidates: List[tuple[str, Any, float]] = []  # (action_id, spec, score)

    for action_id, spec in sorted(action_specs.items()):
        dynamic = spec.dynamic or {}
        director_config = dynamic.get("director", {})

        # Must have suggest flag
        if not director_config.get("suggest"):
            continue

        # Check cooldown (optional)
        cooldown_days = director_config.get("cooldown_days", 0)
        if cooldown_days > 0:
            cooldown_key = f"director.cooldown.{action_id}"
            last_day = state.player.flags.get(cooldown_key, 0)
            if state.world.day - last_day < cooldown_days:
                continue

        # Score urgency
        score = _score_action_urgency(state, action_id, spec)

        candidates.append((action_id, spec, score))

    if not candidates:
        # No suggested actions available
        state.player.flags["goals.today"] = []
        return

    # Sort by score (descending) for deterministic ordering, then by action_id for stable tie-breaking
    candidates.sort(key=lambda x: (-x[2], x[0]))

    # Pick 2-4 goals weighted by score
    num_goals = min(4, max(2, len(candidates)))
    # Use weighted random sampling without replacement
    chosen_goals: List[Dict[str, Any]] = []

    # Create a copy of candidates for sampling
    remaining = list(candidates)

    for _ in range(num_goals):
        if not remaining:
            break

        # Weighted choice based on scores
        total_weight = sum(score for _, _, score in remaining)
        if total_weight <= 0:
            # All scores are 0 or negative, just pick first
            chosen_action_id, chosen_spec, _ = remaining.pop(0)
        else:
            pick = rng.random() * total_weight
            cumulative = 0.0
            chosen_idx = 0
            for idx, (action_id, spec, score) in enumerate(remaining):
                cumulative += score
                if pick < cumulative:
                    chosen_idx = idx
                    break
            chosen_action_id, chosen_spec, _ = remaining.pop(chosen_idx)

        # Validate action at current location (do not teleport player)
        ok, reason, missing = validate_action_spec(state, chosen_spec, item_meta, params=None)

        # Generate tier preview
        tier_seed = day_seed + stable_hash(chosen_action_id)
        tier_dist = preview_tier_distribution(state, chosen_spec, item_meta, rng_seed=tier_seed, samples=9)

        # Generate preview notes (use empty ActionCall since we don't have params yet)
        from .action_call import ActionCall
        dummy_call = ActionCall(chosen_action_id, {})
        notes = build_preview_notes(state, chosen_spec, item_meta, dummy_call)

        # Build goal dict
        goal = {
            "action_id": chosen_action_id,
            "valid": ok,
            "reason": reason if not ok else "",
            "missing": missing,
            "tier_distribution": tier_dist,
            "notes": notes,
        }

        chosen_goals.append(goal)

    # Store goals in flags
    state.player.flags["goals.today"] = chosen_goals

    # Log event
    goal_action_ids = [g["action_id"] for g in chosen_goals]
    _log(state, "director.goals_seeded", goal_action_ids=goal_action_ids, day=state.world.day)
