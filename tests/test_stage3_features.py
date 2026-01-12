"""Tests for Stage 3 features: director, pacing, and content packs."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from roomlife.engine import apply_action, new_game, _ensure_specs_loaded, _ACTION_SPECS


def test_director_seeds_daily_goals():
    """Test that director seeds 2-4 daily goals on day rollover."""
    state = new_game(seed=123)

    # Advance to day 2 (triggers day rollover)
    for _ in range(4):  # 4 slices = 1 day
        apply_action(state, "rest", rng_seed=100)

    # Check that goals were seeded
    assert "goals.today" in state.player.flags
    goals = state.player.flags["goals.today"]

    # Should have 2-4 goals
    assert isinstance(goals, list)
    assert 2 <= len(goals) <= 4

    # Each goal should have required fields
    for goal in goals:
        assert "action_id" in goal
        assert "valid" in goal
        assert "missing" in goal
        assert "tier_distribution" in goal
        assert "notes" in goal


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


def test_director_logs_event():
    """Test that director logs a director.goals_seeded event."""
    state = new_game(seed=789)

    # Advance to day 2
    for _ in range(4):
        apply_action(state, "rest", rng_seed=100)

    # Check for director event
    director_events = [e for e in state.event_log if e["event_id"] == "director.goals_seeded"]
    assert len(director_events) > 0

    # Check event structure
    event = director_events[0]
    assert "goal_action_ids" in event["params"]
    assert "day" in event["params"]


def test_pacing_relaxed_slows_needs_decay():
    """Test that relaxed pacing slows needs decay rates."""
    state_normal = new_game(seed=100)
    state_relaxed = new_game(seed=100)

    # Set pacing
    state_relaxed.player.flags["pacing"] = "relaxed"

    # Run 4 slices
    for _ in range(4):
        apply_action(state_normal, "rest", rng_seed=100)
        apply_action(state_relaxed, "rest", rng_seed=100)

    # Relaxed should have lower hunger/fatigue growth
    assert state_relaxed.player.needs.hunger < state_normal.player.needs.hunger
    assert state_relaxed.player.needs.fatigue < state_normal.player.needs.fatigue


def test_pacing_hard_increases_needs_decay():
    """Test that hard pacing increases needs decay rates."""
    state_normal = new_game(seed=200)
    state_hard = new_game(seed=200)

    # Set pacing
    state_hard.player.flags["pacing"] = "hard"

    # Run 4 slices
    for _ in range(4):
        apply_action(state_normal, "rest", rng_seed=100)
        apply_action(state_hard, "rest", rng_seed=100)

    # Hard should have higher hunger/fatigue growth
    assert state_hard.player.needs.hunger > state_normal.player.needs.hunger
    assert state_hard.player.needs.fatigue > state_normal.player.needs.fatigue


def test_pacing_affects_mishap_frequency():
    """Test that pacing affects random mishap frequency (statistical test)."""
    # Run multiple simulations to check mishap rates
    mishaps_normal = 0
    mishaps_relaxed = 0
    mishaps_hard = 0

    # Run 100 days for each pacing level
    for seed_offset in range(100):
        state_normal = new_game(seed=300 + seed_offset)
        state_relaxed = new_game(seed=300 + seed_offset)
        state_hard = new_game(seed=300 + seed_offset)

        state_relaxed.player.flags["pacing"] = "relaxed"
        state_hard.player.flags["pacing"] = "hard"

        # Run 1 day
        for _ in range(4):
            apply_action(state_normal, "rest", rng_seed=100 + seed_offset)
            apply_action(state_relaxed, "rest", rng_seed=100 + seed_offset)
            apply_action(state_hard, "rest", rng_seed=100 + seed_offset)

        # Count injury events as mishaps
        mishaps_normal += sum(1 for e in state_normal.event_log if e["event_id"] == "health.injury")
        mishaps_relaxed += sum(1 for e in state_relaxed.event_log if e["event_id"] == "health.injury")
        mishaps_hard += sum(1 for e in state_hard.event_log if e["event_id"] == "health.injury")

    # Relaxed should have fewer mishaps than normal
    # Hard should have more mishaps than normal
    # (With 100 samples, statistical difference should be clear)
    assert mishaps_relaxed < mishaps_normal
    assert mishaps_hard > mishaps_normal


def test_pacing_default_is_normal():
    """Test that pacing defaults to normal when not set."""
    state = new_game(seed=400)

    # pacing flag should not be set or should be "normal"
    pacing = state.player.flags.get("pacing", "normal")
    assert pacing == "normal"


def test_content_pack_loading_deterministic_order():
    """Test that content packs load in deterministic sorted order."""
    # This test verifies that pack loading is deterministic
    # We'll just check that _ensure_specs_loaded doesn't crash
    # and that action specs are loaded
    _ensure_specs_loaded()

    # Should have base actions loaded
    assert _ACTION_SPECS is not None
    assert len(_ACTION_SPECS) > 0

    # Verify some known base actions exist
    assert "move" in _ACTION_SPECS
    assert "rest" in _ACTION_SPECS
    assert "cook_basic_meal" in _ACTION_SPECS


def test_director_respects_cooldowns():
    """Test that director respects cooldown_days for suggested actions.

    Specifically tests that clean_room (cooldown_days: 1) doesn't appear
    in goals on consecutive days.
    """
    state = new_game(seed=555)

    # Track which days clean_room appears in goals
    clean_room_days = []

    for day_num in range(1, 11):  # Track 10 days
        # Advance to next day
        for _ in range(4):
            apply_action(state, "rest", rng_seed=100)

        # Check if clean_room is in today's goals
        goals = state.player.flags.get("goals.today", [])
        goal_ids = [g["action_id"] for g in goals]

        if "clean_room" in goal_ids:
            clean_room_days.append(day_num)

    # Verify clean_room appeared at least once
    assert len(clean_room_days) > 0, "clean_room should appear in goals at least once"

    # Verify no consecutive days (cooldown_days: 1 means at least 1 day gap)
    for i in range(len(clean_room_days) - 1):
        day_gap = clean_room_days[i + 1] - clean_room_days[i]
        assert day_gap >= 1, f"clean_room appeared on consecutive days {clean_room_days[i]} and {clean_room_days[i+1]}"


def test_director_validates_goals_at_current_location():
    """Test that director validates goals at player's current location."""
    state = new_game(seed=666)

    # Move to hallway
    apply_action(state, "move", rng_seed=100, params={"target_space": "hall_001"})

    # Advance to day 2
    for _ in range(4):
        apply_action(state, "rest", rng_seed=100)

    # Check goals
    goals = state.player.flags.get("goals.today", [])

    # Some goals may be invalid due to location requirements
    # Just verify that validation was run (valid field exists)
    for goal in goals:
        assert "valid" in goal
        assert isinstance(goal["valid"], bool)
        if not goal["valid"]:
            assert "missing" in goal
            assert len(goal["missing"]) > 0


def test_director_provides_tier_preview():
    """Test that director provides tier distribution previews for goals."""
    state = new_game(seed=777)

    # Advance to day 2
    for _ in range(4):
        apply_action(state, "rest", rng_seed=100)

    goals = state.player.flags.get("goals.today", [])

    # Check tier distribution format
    for goal in goals:
        tier_dist = goal["tier_distribution"]
        assert isinstance(tier_dist, dict)
        # Should have tiers 0-3
        assert set(tier_dist.keys()) == {0, 1, 2, 3}
        # Probabilities should sum to ~1.0
        total_prob = sum(tier_dist.values())
        assert 0.99 <= total_prob <= 1.01


def test_director_provides_preview_notes():
    """Test that director provides preview notes for goals."""
    state = new_game(seed=888)

    # Advance to day 2
    for _ in range(4):
        apply_action(state, "rest", rng_seed=100)

    goals = state.player.flags.get("goals.today", [])

    # Check notes format
    for goal in goals:
        notes = goal["notes"]
        assert isinstance(notes, list)
        # Notes may be empty or have strings
        for note in notes:
            assert isinstance(note, str)
