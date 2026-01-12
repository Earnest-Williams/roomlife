"""NPC AI for building events and encounters.

This module handles NPC-initiated events (noise complaints, maintenance notices, etc.)
and NPC encounters when the player moves to hallways/shared spaces.
"""

from __future__ import annotations

import random
import zlib
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from .constants import MAX_EVENT_LOG, TIME_SLICES
from .models import NPC, State


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


def choose_source_npc(state: State, roles: List[str], seed: int) -> Optional[str]:
    """Choose an NPC deterministically from sorted candidates.

    Args:
        state: Game state
        roles: List of acceptable NPC roles (e.g., ["neighbor", "landlord"])
        seed: Random seed for deterministic selection

    Returns:
        NPC id, or None if no matching NPCs exist
    """
    # Filter NPCs by role and sort for determinism
    candidates = sorted([
        npc_id for npc_id, npc in state.npcs.items()
        if npc.role in roles
    ])

    if not candidates:
        return None

    rng = random.Random(seed)
    return rng.choice(candidates)


@contextmanager
def _actor_scope(state: State, npc: NPC):
    """Temporarily replace state.player with NPC for tier computation.

    This context manager ensures state.player is always restored, even if tier computation raises.

    Args:
        state: Game state
        npc: NPC to temporarily use as actor

    Yields:
        None
    """
    original_player = state.player
    try:
        # Create a temporary player-like object with NPC's skills/traits
        # We don't need full player state, just what tier computation needs
        state.player = type('NPCActor', (), {
            'skills_detailed': npc.skills_detailed,
            'aptitudes': npc.aptitudes,
            'traits': npc.traits,
            'needs': original_player.needs,  # Use player needs for health penalty
        })()  # type: ignore
        yield
    finally:
        state.player = original_player


def maybe_trigger_daily_building_event(
    state: State,
    action_specs: Dict[str, Any],
    item_meta: Dict[str, Any],
    current_tick: int,
) -> None:
    """Trigger at most one NPC-initiated building event per day.

    This function is called on day rollover. It:
    1. Builds candidate actions where dynamic.npc.initiates == true
    2. Filters by allowed_slices, cooldowns, and validate_action_spec
    3. Picks one via deterministic weighted choice
    4. Computes tier under NPC scope (temporarily scoping state.player to NPC)
    5. Applies outcome to the player (with state.player restored)
    6. Logs event and updates cooldowns

    Args:
        state: Game state
        action_specs: Action specifications registry
        item_meta: Item metadata registry
        current_tick: Current game tick
    """
    from .action_engine import apply_outcome, compute_tier, validate_action_spec

    # Use deterministic RNG seeded from simulation seed + day
    day_seed = state.world.rng_seed + state.world.day * 97

    # Build candidate actions
    candidates: List[Tuple[str, Any, str, float]] = []  # (action_id, spec, npc_id, weight)

    for action_id, spec in sorted(action_specs.items()):
        dynamic = spec.dynamic or {}
        npc_config = dynamic.get("npc", {})

        # Must be NPC-initiated
        if not npc_config.get("initiates"):
            continue

        # Check allowed_slices
        allowed_slices = npc_config.get("allowed_slices", [])
        if allowed_slices and state.world.slice not in allowed_slices:
            continue

        # Check cooldown
        cooldown_days = npc_config.get("cooldown_days", 0)
        if cooldown_days > 0:
            cooldown_key = f"npc.cooldown.{action_id}"
            last_day = state.player.flags.get(cooldown_key, 0)
            if state.world.day - last_day < cooldown_days:
                continue

        # Choose source NPC deterministically
        roles = npc_config.get("roles", ["neighbor", "landlord", "maintenance"])
        npc_seed = day_seed + stable_hash(action_id)
        npc_id = choose_source_npc(state, roles, npc_seed)
        if npc_id is None:
            continue

        # Validate action (using player state, as outcomes will apply to player)
        ok, _, _ = validate_action_spec(state, spec, item_meta, params=None)
        if not ok:
            continue

        # Add to candidates with weight
        weight = float(npc_config.get("weight", 1.0))
        candidates.append((action_id, spec, npc_id, weight))

    if not candidates:
        return  # No valid events today

    # Pick one event deterministically using weighted choice
    rng = random.Random(day_seed)
    total_weight = sum(w for _, _, _, w in candidates)
    pick = rng.random() * total_weight
    cumulative = 0.0
    chosen_action_id = None
    chosen_spec = None
    chosen_npc_id = None

    for action_id, spec, npc_id, weight in candidates:
        cumulative += weight
        if pick <= cumulative:
            chosen_action_id = action_id
            chosen_spec = spec
            chosen_npc_id = npc_id
            break

    if chosen_spec is None or chosen_npc_id is None:
        return  # Shouldn't happen, but be safe

    # Get the NPC
    npc = state.npcs.get(chosen_npc_id)
    if npc is None:
        return

    # Compute tier under NPC scope (NPC is the actor for skill/trait computation)
    tier_seed = day_seed + stable_hash(chosen_action_id) + stable_hash(chosen_npc_id)
    tier = 1  # Default tier
    try:
        with _actor_scope(state, npc):
            tier = compute_tier(state, chosen_spec, item_meta, rng_seed=tier_seed)
    except Exception as e:
        # If tier computation fails, log and use default tier
        print(f"Warning: Tier computation failed for NPC event {chosen_action_id}: {e}")
        tier = 1

    # Apply outcome to the player (state.player is now restored)
    # NOTE: We do NOT apply consumes for NPC events unless explicitly intended
    # (building events should not consume player items/money by default)
    try:
        apply_outcome(state, chosen_spec, tier, item_meta, current_tick, emit_events=True)
    except Exception as e:
        print(f"Warning: Outcome application failed for NPC event {chosen_action_id}: {e}")

    # Log the NPC event
    _log(
        state,
        "npc.event",
        npc_id=chosen_npc_id,
        npc_name=npc.display_name,
        npc_role=npc.role,
        action_id=chosen_action_id,
        tier=tier,
    )

    # Update cooldown
    dynamic = chosen_spec.dynamic or {}
    npc_config = dynamic.get("npc", {})
    cooldown_days = npc_config.get("cooldown_days", 0)
    if cooldown_days > 0:
        cooldown_key = f"npc.cooldown.{chosen_action_id}"
        state.player.flags[cooldown_key] = state.world.day


def on_player_entered_space(
    state: State,
    from_space: Optional[str],
    to_space: str,
    action_specs: Dict[str, Any],
    item_meta: Dict[str, Any],
    current_tick: int,
) -> None:
    """Handle NPC encounters when player enters a space.

    This function is called after the player moves. It:
    1. Detects hallway/landing spaces by tags
    2. Makes a deterministic encounter roll
    3. Chooses an NPC and sets encounter flags/goals (does not force actions)

    Args:
        state: Game state
        from_space: Previous space id (may be None)
        to_space: New space id
        action_specs: Action specifications registry
        item_meta: Item metadata registry
        current_tick: Current game tick
    """
    # Check if the new space is a hallway/landing (has "hallway" tag)
    space = state.spaces.get(to_space)
    if space is None:
        return

    tags = getattr(space, "tags", [])
    if "hallway" not in tags:
        return

    # Deterministic encounter roll based on stable seed components
    encounter_seed = (
        state.world.rng_seed
        + state.world.day * 97
        + TIME_SLICES.index(state.world.slice) * 13
        + stable_hash(to_space)
    )
    rng = random.Random(encounter_seed)

    # Low encounter chance (at most 1 per day per location)
    encounter_chance = 0.15
    if rng.random() > encounter_chance:
        return

    # Check if we've already had an encounter today
    encounter_today_key = f"encounter.today.{state.world.day}"
    if state.player.flags.get(encounter_today_key, 0) >= 1:
        return  # At most 1 encounter per day

    # Choose an NPC deterministically
    npc_id = choose_source_npc(state, ["neighbor", "landlord", "maintenance"], encounter_seed)
    if npc_id is None:
        return

    npc = state.npcs.get(npc_id)
    if npc is None:
        return

    # Set encounter flag
    state.player.flags["encounter.available"] = npc_id
    state.player.flags[encounter_today_key] = 1

    # Log encounter
    _log(
        state,
        "npc.encounter",
        npc_id=npc_id,
        npc_name=npc.display_name,
        npc_role=npc.role,
        location=to_space,
    )
