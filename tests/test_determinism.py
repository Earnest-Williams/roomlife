"""Tests for deterministic behavior across all game systems."""

from dataclasses import asdict
from roomlife.engine import apply_action, new_game, _ensure_specs_loaded, _ACTION_SPECS


def _snapshot_state(state):
    """Helper to snapshot full game state for comparison."""
    return {
        "world": (state.world.day, state.world.slice, state.world.location),
        "player": {
            "money_pence": state.player.money_pence,
            "utilities_paid": state.player.utilities_paid,
            "needs": asdict(state.player.needs),
            "traits": asdict(state.player.traits),
            "aptitudes": asdict(state.player.aptitudes),
            "skills": {
                name: (skill.value, skill.last_tick)
                for name, skill in state.player.skills_detailed.items()
            },
            "habits": dict(state.player.habit_tracker),
        },
        "items": [
            (
                it.instance_id,
                it.item_id,
                it.placed_in,
                it.slot,
                it.condition_value,
                it.quality,
                it.bulk,
            )
            for it in sorted(state.items, key=lambda item: item.instance_id)
        ],
        "event_log": list(state.event_log),
    }


def _prepare_state_for_spec(state, spec):
    """Prepare state to satisfy action spec requirements."""
    if spec.id == "drop_item" and state.items:
        state.items[0].placed_in = "inventory"
        state.items[0].slot = "inventory"


def _build_params(state, spec):
    """Build parameters for action based on spec requirements."""
    params = {}
    for param in spec.parameters or []:
        name = param.get("name")
        ptype = param.get("type")
        constraints = param.get("constraints", {})
        if ptype == "space_id":
            current = state.world.location
            space = state.spaces.get(current)
            if space and space.connections:
                params[name] = space.connections[0]
            else:
                params[name] = current
        elif ptype == "item_ref":
            if constraints.get("in_inventory"):
                candidate = next(
                    (it for it in state.items if it.placed_in == "inventory"),
                    None,
                )
            else:
                candidate = next(
                    (it for it in state.items if it.placed_in in (state.world.location, "inventory")),
                    None,
                )
            if candidate:
                params[name] = {"mode": "by_item_id", "item_id": candidate.item_id}
        else:
            candidate = next(
                (it for it in state.items if it.placed_in == state.world.location),
                None,
            )
            if candidate and name:
                params[name] = candidate.item_id
    if spec.id == "repair_item" and state.items:
        candidate = next(
            (it for it in state.items if it.placed_in in (state.world.location, "inventory")),
            None,
        )
        if candidate:
            params.setdefault(
                "item_ref",
                {"mode": "by_item_id", "item_id": candidate.item_id},
            )
    return params


# ===== CORE DETERMINISM TESTS =====

def test_determinism_basic():
    """Test basic determinism with same seed and rng_seed."""
    s1 = new_game()
    s2 = new_game()
    actions = ["work", "study", "eat_charity_rice", "skip_utilities", "sleep", "pay_utilities"]
    for a in actions:
        apply_action(s1, a, rng_seed=123)
        apply_action(s2, a, rng_seed=123)
    assert s1.player.money_pence == s2.player.money_pence
    assert s1.player.needs.hunger == s2.player.needs.hunger
    assert s1.world.day == s2.world.day
    assert s1.world.slice == s2.world.slice


def test_each_action_has_deterministic_outcome_with_seed():
    """Test that every action produces deterministic outcomes with same seed."""
    _ensure_specs_loaded()
    assert _ACTION_SPECS is not None

    for spec in _ACTION_SPECS.values():
        # Use the same seed for both games to ensure deterministic instance IDs
        s1 = new_game(seed=100)
        s2 = new_game(seed=100)
        _prepare_state_for_spec(s1, spec)
        _prepare_state_for_spec(s2, spec)
        params1 = _build_params(s1, spec)
        params2 = _build_params(s2, spec)
        apply_action(s1, spec.id, rng_seed=42, params=params1)
        apply_action(s2, spec.id, rng_seed=42, params=params2)
        assert _snapshot_state(s1) == _snapshot_state(s2)


def test_new_game_deterministic_with_seed():
    """Test that new_game with same seed produces identical states."""
    state1 = new_game(seed=42)
    state2 = new_game(seed=42)

    # Check that item instance IDs are the same
    for i in range(len(state1.items)):
        assert state1.items[i].instance_id == state2.items[i].instance_id


def test_new_game_different_seeds_produce_different_states():
    """Test that new_game with different seeds produces different states."""
    state1 = new_game(seed=42)
    state2 = new_game(seed=99)

    # Check that at least some item instance IDs are different
    different_ids = False
    for i in range(min(len(state1.items), len(state2.items))):
        if state1.items[i].instance_id != state2.items[i].instance_id:
            different_ids = True
            break

    assert different_ids


# ===== NPC SYSTEM DETERMINISM =====

def test_npc_event_scheduler_deterministic_by_seed_and_day():
    """Test that NPC events are deterministic based on seed + day."""
    # Run two simulations with the same seed
    s1 = new_game(seed=42)
    s2 = new_game(seed=42)

    # Advance both simulations 7 day rollovers (night slice -> morning of next day)
    for _ in range(7 * 4):  # 4 slices per day
        apply_action(s1, "rest", rng_seed=100)
        apply_action(s2, "rest", rng_seed=100)

    # Collect NPC events from both simulations
    npc_events_1 = [
        (e["params"].get("npc_id"), e["params"].get("action_id"), e["params"].get("tier"))
        for e in s1.event_log
        if e["event_id"] == "npc.event"
    ]
    npc_events_2 = [
        (e["params"].get("npc_id"), e["params"].get("action_id"), e["params"].get("tier"))
        for e in s2.event_log
        if e["event_id"] == "npc.event"
    ]

    # Events should match exactly
    assert npc_events_1 == npc_events_2

    # Run a third simulation with a different seed
    s3 = new_game(seed=999)
    for _ in range(7 * 4):
        apply_action(s3, "rest", rng_seed=100)

    npc_events_3 = [
        (e["params"].get("npc_id"), e["params"].get("action_id"), e["params"].get("tier"))
        for e in s3.event_log
        if e["event_id"] == "npc.event"
    ]

    # Events should differ with different seed
    # Verify that events were generated
    assert len(npc_events_3) > 0


# ===== DIRECTOR SYSTEM DETERMINISM =====

def test_director_goals_are_deterministic():
    """Test that director goals are deterministic based on seed."""
    s1 = new_game(seed=456)
    s2 = new_game(seed=456)

    # Advance both to day 2
    for _ in range(4):
        apply_action(s1, "rest", rng_seed=100)
        apply_action(s2, "rest", rng_seed=100)

    goals1 = s1.player.flags.get("goals.today", [])
    goals2 = s2.player.flags.get("goals.today", [])

    # Goal action_ids should match
    goal_ids1 = [g["action_id"] for g in goals1]
    goal_ids2 = [g["action_id"] for g in goals2]
    assert goal_ids1 == goal_ids2

    # Tier distributions should match
    for g1, g2 in zip(goals1, goals2):
        assert g1["tier_distribution"] == g2["tier_distribution"]


def test_simulation_seed_storage():
    """Test that simulation seed is stored in world.rng_seed."""
    state1 = new_game(seed=123)
    assert state1.world.rng_seed == 123

    state2 = new_game(seed=456)
    assert state2.world.rng_seed == 456

    state3 = new_game()
    assert state3.world.rng_seed == 0  # Default when no seed provided
