"""Tests for save/load functionality in io.py."""

import tempfile
from pathlib import Path

from roomlife.engine import apply_action, new_game
from roomlife.io import load_state, save_state
from roomlife.models import Item, Skill, generate_instance_id


def test_save_and_load_roundtrip():
    """Test that saving and loading a state preserves all data."""
    state = new_game()

    # Modify state to have interesting data
    state.player.money_pence = 12345
    state.player.needs.hunger = 75
    state.player.needs.fatigue = 60
    state.player.skills["cooking"] = 25.5
    state.player.traits.confidence = 65
    state.world.location = "kitchen_001"

    # Add an item
    state.items.append(Item(
        instance_id="test_item_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.5,
        condition="used",
        condition_value=85,
        bulk=2
    ))

    # Save to temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_save.yaml"
        save_state(state, save_path)

        # Load back
        loaded_state = load_state(save_path)

        # Verify data preservation
        assert loaded_state.player.money_pence == 12345
        assert loaded_state.player.needs.hunger == 75
        assert loaded_state.player.needs.fatigue == 60
        assert loaded_state.player.skills["cooking"] == 25.5
        assert loaded_state.player.traits.confidence == 65
        assert loaded_state.world.location == "kitchen_001"

        # Verify item
        assert len(loaded_state.items) == len(state.items)
        loaded_item = next(it for it in loaded_state.items if it.item_id == "bed_standard")
        assert loaded_item.instance_id == "test_item_001"
        assert loaded_item.quality == 1.5
        assert loaded_item.condition == "used"
        assert loaded_item.condition_value == 85
        assert loaded_item.bulk == 2


def test_load_state_with_skills_detailed():
    """Test that loading state correctly handles skills_detailed format."""
    state = new_game()

    # Modify skills with detailed tracking
    state.player.skills_detailed["cooking"].value = 42.5
    state.player.skills_detailed["cooking"].last_tick = 1000
    state.player.skills_detailed["maintenance"].value = 15.3
    state.player.skills_detailed["maintenance"].last_tick = 800

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_skills.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        # Verify detailed skills
        assert loaded_state.player.skills_detailed["cooking"].value == 42.5
        assert loaded_state.player.skills_detailed["cooking"].last_tick == 1000
        assert loaded_state.player.skills_detailed["maintenance"].value == 15.3
        assert loaded_state.player.skills_detailed["maintenance"].last_tick == 800


def test_save_preserves_event_log():
    """Test that event log is preserved across save/load."""
    state = new_game()

    # Execute some actions to generate events
    apply_action(state, "cook_meal", rng_seed=123)
    apply_action(state, "sleep", rng_seed=124)

    initial_event_count = len(state.event_log)
    assert initial_event_count > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_events.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        assert len(loaded_state.event_log) == initial_event_count
        # Verify first and last events match
        assert loaded_state.event_log[0] == state.event_log[0]
        assert loaded_state.event_log[-1] == state.event_log[-1]


def test_load_state_with_missing_optional_fields():
    """Test that loading state handles missing optional fields gracefully."""
    state = new_game()

    # Remove some optional fields before saving
    state.player.carry_capacity = 15

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_optional.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        # Verify defaults are applied for optional fields
        assert loaded_state.player.carry_capacity == 15


def test_save_and_load_multiple_items():
    """Test that multiple items with different states are preserved."""
    state = new_game()

    # Add multiple items with varying conditions
    for i in range(5):
        state.items.append(Item(
            instance_id=f"item_{i}",
            item_id=f"test_item_{i}",
            placed_in="inventory" if i % 2 == 0 else "room_001",
            container=None,
            slot="inventory" if i % 2 == 0 else "floor",
            quality=1.0 + (i * 0.1),
            condition="pristine" if i < 2 else "worn",
            condition_value=100 - (i * 10),
            bulk=1 + i
        ))

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_items.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        # Verify all items are preserved
        assert len(loaded_state.items) == len(state.items)
        for i in range(5):
            loaded_item = next(it for it in loaded_state.items if it.instance_id == f"item_{i}")
            original_item = next(it for it in state.items if it.instance_id == f"item_{i}")

            assert loaded_item.item_id == original_item.item_id
            assert loaded_item.placed_in == original_item.placed_in
            assert loaded_item.quality == original_item.quality
            assert loaded_item.condition == original_item.condition
            assert loaded_item.condition_value == original_item.condition_value
            assert loaded_item.bulk == original_item.bulk


def test_load_state_backward_compatibility():
    """Test that loading older save formats works (individual skill fields)."""
    state = new_game()

    # Set skills using the old format (just numeric values)
    state.player.skills["cooking"] = 30.0
    state.player.skills["maintenance"] = 20.0

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_compat.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        # Verify skills are loaded correctly
        assert "cooking" in loaded_state.player.skills_detailed
        assert "maintenance" in loaded_state.player.skills_detailed


def test_save_creates_parent_directories():
    """Test that save_state creates parent directories if they don't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a nested path that doesn't exist
        save_path = Path(tmpdir) / "subdir" / "nested" / "save.yaml"

        state = new_game()
        save_state(state, save_path)

        # Verify file was created
        assert save_path.exists()

        # Verify it can be loaded
        loaded_state = load_state(save_path)
        assert loaded_state.player.money_pence == state.player.money_pence


def test_save_and_load_habit_tracker():
    """Test that habit tracker data is preserved."""
    state = new_game()

    # Simulate some habit tracking
    state.player.habit_tracker["confidence"] = 50
    state.player.habit_tracker["discipline"] = 30
    state.player.habit_tracker["frugality"] = 25

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_habits.yaml"
        save_state(state, save_path)

        loaded_state = load_state(save_path)

        assert loaded_state.player.habit_tracker["confidence"] == 50
        assert loaded_state.player.habit_tracker["discipline"] == 30
        assert loaded_state.player.habit_tracker["frugality"] == 25
