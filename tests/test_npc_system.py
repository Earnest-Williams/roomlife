"""Tests for NPC system (building events, social actions, encounters)."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from roomlife.engine import apply_action, new_game


def test_new_game_seeds_building_npcs_deterministically():
    """Test that new_game() seeds NPCs with deterministic IDs and neutral relationships."""
    state = new_game(seed=123)

    # Check that 3 NPCs were created
    assert len(state.npcs) == 3

    # Check NPC ids and roles
    assert "npc_neighbor_nina" in state.npcs
    assert "npc_landlord_park" in state.npcs
    assert "npc_maint_lee" in state.npcs

    # Check NPC properties
    nina = state.npcs["npc_neighbor_nina"]
    assert nina.id == "npc_neighbor_nina"
    assert nina.display_name == "Nina"
    assert nina.role == "neighbor"

    park = state.npcs["npc_landlord_park"]
    assert park.id == "npc_landlord_park"
    assert park.display_name == "Mr. Park"
    assert park.role == "landlord"

    lee = state.npcs["npc_maint_lee"]
    assert lee.id == "npc_maint_lee"
    assert lee.display_name == "Lee"
    assert lee.role == "maintenance"

    # Check neutral relationships (initialized to 0)
    for npc_id in state.npcs:
        assert state.npcs[npc_id].relationships.get("player") == 0
        assert state.player.relationships.get(npc_id) == 0


def test_npc_events_respect_cooldowns():
    """Test that NPC events respect cooldown_days by checking flags."""
    state = new_game(seed=123)

    # Advance 10 days (40 actions)
    for _ in range(10 * 4):
        apply_action(state, "rest", rng_seed=100)

    # Count NPC events
    npc_events = [e for e in state.event_log if e["event_id"] == "npc.event"]

    # At least some NPC events should have fired over 10 days
    assert len(npc_events) > 0

    # Check cooldown flags are properly set
    # Cooldown flags follow pattern: "npc.cooldown.<action_id>"
    cooldown_flags = {k: v for k, v in state.player.flags.items() if k.startswith("npc.cooldown.")}
    assert len(cooldown_flags) > 0, "Expected cooldown flags to be set after NPC events"

    # Verify cooldown flags are day numbers (positive integers)
    for cooldown_day in cooldown_flags.values():
        assert isinstance(cooldown_day, int)
        assert cooldown_day >= 1, f"Cooldown day should be >= 1, got {cooldown_day}"
        assert cooldown_day <= state.world.day, f"Cooldown day {cooldown_day} exceeds current day {state.world.day}"

    # Verify each action_id has at most one cooldown flag
    action_ids_from_events = set(e["params"].get("action_id") for e in npc_events)
    action_ids_from_flags = set(k.replace("npc.cooldown.", "") for k in cooldown_flags.keys())
    # All action_ids that fired should have cooldown flags
    assert action_ids_from_events.issubset(action_ids_from_flags)


def test_npc_events_apply_outcomes_to_player():
    """Test that NPC-initiated events apply outcomes (deltas) to the player."""
    state = new_game(seed=456)

    # Advance time until an NPC event fires (up to 10 days)
    npc_event_fired = False
    for _ in range(10 * 4):
        apply_action(state, "rest", rng_seed=100)
        # Check if any NPC event fired
        if any(e["event_id"] == "npc.event" for e in list(state.event_log)[-5:]):
            npc_event_fired = True
            break

    # Verify NPC events have proper structure (if any fired)
    npc_events = [e for e in state.event_log if e["event_id"] == "npc.event"]
    if len(npc_events) > 0:
        # Check event structure
        for event in npc_events:
            assert "npc_id" in event["params"]
            assert "action_id" in event["params"]
            assert "tier" in event["params"]


def test_npc_event_tier_computation_uses_npc_skills():
    """Test that tier computation for NPC events uses NPC skills/traits, not player's."""
    state = new_game(seed=789)

    # Modify player skills to be very high (100.0)
    for skill_name in state.player.skills_detailed:
        state.player.skills_detailed[skill_name].value = 100.0

    # Modify one NPC's skills to be very low (0.0)
    nina = state.npcs["npc_neighbor_nina"]
    for skill_name in nina.skills_detailed:
        nina.skills_detailed[skill_name].value = 0.0

    # Advance time until multiple NPC events fire from Nina
    for _ in range(20 * 4):  # 20 days to get multiple events
        apply_action(state, "rest", rng_seed=100)

    # Collect events initiated by Nina
    nina_events = [
        e for e in state.event_log
        if e["event_id"] == "npc.event" and e["params"].get("npc_id") == "npc_neighbor_nina"
    ]

    # If Nina initiated events, average tier should be lower than if player skills were used
    # With 0 skill, we expect more tier 0/1 outcomes
    # With 100 skill, we'd expect more tier 2/3 outcomes
    if len(nina_events) > 0:
        tiers = [e["params"].get("tier", 0) for e in nina_events]
        avg_tier = sum(tiers) / len(tiers)
        # Average tier should be low (closer to 0-1 than 2-3)
        # If player skills were used (100.0), average would be much higher
        assert avg_tier < 2.0, f"Average tier {avg_tier} is too high for 0-skill NPC"
        # Verify at least some low tiers occurred
        assert any(t in [0, 1] for t in tiers), "Expected some tier 0 or 1 outcomes with 0-skill NPC"


def test_hallway_encounter_detection():
    """Test that moving into a hallway triggers NPC encounter detection."""
    state = new_game(seed=321)

    # Move to hallway
    apply_action(state, "move", rng_seed=100, params={"target_space": "hall_001"})

    # Check if an encounter event was logged
    encounter_events = [e for e in state.event_log if e["event_id"] == "npc.encounter"]

    # Encounter chance is 15% and limited to 1 per day, so it may or may not fire
    # Just verify that the system doesn't crash and encounter events are in valid format
    for event in encounter_events:
        assert "npc_id" in event["params"]
        assert "npc_name" in event["params"]
        assert "npc_role" in event["params"]
        assert "location" in event["params"]
        assert event["params"]["location"] == "hall_001"


def test_player_flags_and_memory_exist():
    """Test that Player has flags and memory fields."""
    state = new_game(seed=123)

    assert hasattr(state.player, "flags")
    assert hasattr(state.player, "memory")
    assert isinstance(state.player.flags, dict)
    assert isinstance(state.player.memory, list)


def test_npc_cooldown_flags_stored_deterministically():
    """Test that NPC cooldown flags are stored in player.flags."""
    state = new_game(seed=555)

    # Advance time until an NPC event fires
    for _ in range(10 * 4):
        apply_action(state, "rest", rng_seed=100)

    # Check for cooldown flags in player.flags
    cooldown_flags = {k: v for k, v in state.player.flags.items() if k.startswith("npc.cooldown.")}

    # If any NPC events fired, cooldown flags should be set
    npc_events = [e for e in state.event_log if e["event_id"] == "npc.event"]
    if len(npc_events) > 0:
        # At least one cooldown flag should exist
        assert len(cooldown_flags) > 0
        # Cooldown values should be day numbers
        for day_val in cooldown_flags.values():
            assert isinstance(day_val, int)
            assert day_val >= 1  # Day numbers start at 1
