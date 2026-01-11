from roomlife.engine import apply_action, new_game
from roomlife.models import Item


def test_discard_removes_item_without_money():
    """Test that discarding an item removes it without giving money."""
    state = new_game()

    # Add an item to discard
    state.items.append(Item(
        item_id="bed_standard",
        condition="pristine",
        condition_value=100,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))

    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Discard the item
    apply_action(state, "discard_bed_standard", rng_seed=123)

    # Money should NOT change
    assert state.player.money_pence == initial_money

    # Item count should decrease by 1
    assert len(state.items) == initial_item_count - 1

    # Item should be removed
    assert not any(item.item_id == "bed_standard" for item in state.items)

    # Check that a discard event was logged
    discard_events = [e for e in state.event_log if e["event_id"] == "shopping.discard"]
    assert len(discard_events) == 1
    assert discard_events[0]["params"]["item_id"] == "bed_standard"


def test_discard_item_not_at_current_location():
    """Test that you cannot discard an item not at current location."""
    state = new_game()

    # Add an item at a different location
    state.items.append(Item(
        item_id="bed_standard",
        condition="pristine",
        condition_value=100,
        placed_in="room_002",  # Different location
        slot="floor",
        quality=1.0
    ))

    initial_item_count = len(state.items)

    # Try to discard the item (should fail)
    apply_action(state, "discard_bed_standard", rng_seed=123)

    # Item count should not change
    assert len(state.items) == initial_item_count

    # Item should still exist
    assert any(item.item_id == "bed_standard" for item in state.items)

    # Check that a failure event was logged
    failed_events = [e for e in state.event_log
                     if e["event_id"] == "action.failed"
                     and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) == 1


def test_discard_nonexistent_item_fails():
    """Test that trying to discard a non-existent item fails."""
    state = new_game()
    initial_item_count = len(state.items)

    # Try to discard an item that doesn't exist
    apply_action(state, "discard_bed_luxury", rng_seed=123)

    # Item count should not change
    assert len(state.items) == initial_item_count

    # Check that a failure event was logged
    failed_events = [e for e in state.event_log
                     if e["event_id"] == "action.failed"
                     and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) == 1


def test_discard_tracks_minimalism_habit():
    """Test that discarding an item tracks the minimalism habit."""
    state = new_game()

    # Add an item to discard
    state.items.append(Item(
        item_id="desk_basic",
        condition="worn",
        condition_value=50,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))

    initial_minimalism = state.player.habit_tracker.get("minimalism", 0)

    # Discard the item
    apply_action(state, "discard_desk_basic", rng_seed=123)

    # Minimalism habit should increase by 2
    final_minimalism = state.player.habit_tracker.get("minimalism", 0)
    assert final_minimalism == initial_minimalism + 2


def test_discard_works_for_unsellable_items():
    """Test that discard works for items that cannot be sold (price <= 0)."""
    state = new_game()

    # Add a hypothetical zero-price item (using fallback metadata)
    state.items.append(Item(
        item_id="worthless_item",  # Non-existent item gets price 0 from fallback
        condition="broken",
        condition_value=10,
        placed_in="room_001",
        slot="floor",
        quality=0.5
    ))

    initial_item_count = len(state.items)

    # Discard the worthless item (should succeed)
    apply_action(state, "discard_worthless_item", rng_seed=123)

    # Item should be removed
    assert len(state.items) == initial_item_count - 1
    assert not any(item.item_id == "worthless_item" for item in state.items)

    # Check that a discard event was logged
    discard_events = [e for e in state.event_log if e["event_id"] == "shopping.discard"]
    assert len(discard_events) == 1


def test_multiple_discards_in_sequence():
    """Test discarding multiple items in sequence."""
    state = new_game()

    # Add multiple items
    state.items.append(Item(
        item_id="bed_standard",
        condition="pristine",
        condition_value=100,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))
    state.items.append(Item(
        item_id="desk_basic",
        condition="worn",
        condition_value=50,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))

    initial_item_count = len(state.items)
    initial_money = state.player.money_pence

    # Discard both items
    apply_action(state, "discard_bed_standard", rng_seed=123)
    apply_action(state, "discard_desk_basic", rng_seed=124)

    # Both items should be removed
    assert len(state.items) == initial_item_count - 2

    # No money gained
    assert state.player.money_pence == initial_money

    # Check that two discard events were logged
    discard_events = [e for e in state.event_log if e["event_id"] == "shopping.discard"]
    assert len(discard_events) == 2


def test_cannot_discard_same_item_twice():
    """Test that you can't discard an item that was already discarded."""
    state = new_game()

    # Add an item
    state.items.append(Item(
        item_id="bed_standard",
        condition="pristine",
        condition_value=100,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))

    initial_item_count = len(state.items)

    # Discard the item
    apply_action(state, "discard_bed_standard", rng_seed=123)

    # Try to discard it again (should fail)
    apply_action(state, "discard_bed_standard", rng_seed=124)

    # Item count should only decrease by 1 (not 2)
    assert len(state.items) == initial_item_count - 1

    # Only one successful discard event
    discard_events = [e for e in state.event_log if e["event_id"] == "shopping.discard"]
    assert len(discard_events) == 1

    # One failure event for the second attempt
    failed_events = [e for e in state.event_log
                     if e["event_id"] == "action.failed"
                     and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) == 1


def test_discard_logs_item_condition():
    """Test that discard event logs the item condition."""
    state = new_game()

    # Add an item with specific condition
    state.items.append(Item(
        item_id="desk_basic",
        condition="worn",
        condition_value=50,
        placed_in="room_001",
        slot="floor",
        quality=1.0
    ))

    # Discard the item
    apply_action(state, "discard_desk_basic", rng_seed=123)

    # Check that discard event includes condition
    discard_events = [e for e in state.event_log if e["event_id"] == "shopping.discard"]
    assert len(discard_events) == 1
    assert discard_events[0]["params"]["condition"] == "worn"
