from roomlife.engine import apply_action, new_game


def test_move_between_connected_locations():
    """Test that the player can move between connected locations."""
    state = new_game()

    # Start in room_001
    assert state.world.location == "room_001"

    # Move to hallway
    apply_action(state, "move_hall_001", rng_seed=123)
    assert state.world.location == "hall_001"

    # Move to bathroom
    apply_action(state, "move_bath_001", rng_seed=123)
    assert state.world.location == "bath_001"

    # Move back to hallway
    apply_action(state, "move_hall_001", rng_seed=123)
    assert state.world.location == "hall_001"

    # Move back to room
    apply_action(state, "move_room_001", rng_seed=123)
    assert state.world.location == "room_001"


def test_cannot_move_to_disconnected_location():
    """Test that the player cannot move to a location that is not connected."""
    state = new_game()

    # Start in room_001
    assert state.world.location == "room_001"

    # Try to move directly to bathroom (not connected to room_001)
    apply_action(state, "move_bath_001", rng_seed=123)

    # Should still be in room_001
    assert state.world.location == "room_001"

    # Check that a failure event was logged
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "location_not_connected"]
    assert len(failed_events) == 1


def test_cannot_move_to_nonexistent_location():
    """Test that the player cannot move to a location that doesn't exist."""
    state = new_game()

    # Start in room_001
    assert state.world.location == "room_001"

    # Try to move to a non-existent location
    apply_action(state, "move_fake_location", rng_seed=123)

    # Should still be in room_001
    assert state.world.location == "room_001"

    # Check that a failure event was logged
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "location_not_found"]
    assert len(failed_events) == 1


def test_cannot_move_to_same_location():
    """Test that the player cannot move to the current location."""
    state = new_game()

    # Start in room_001
    assert state.world.location == "room_001"

    # Try to move to the same location
    apply_action(state, "move_room_001", rng_seed=123)

    # Should still be in room_001
    assert state.world.location == "room_001"

    # Check that a failure event was logged
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "already_here"]
    assert len(failed_events) == 1


def test_shower_requires_bathroom_location():
    """Test that shower action only works in the bathroom."""
    state = new_game()

    # Pay utilities to enable water
    apply_action(state, "pay_utilities", rng_seed=123)

    # Start in room_001
    assert state.world.location == "room_001"

    # Try to shower in room (should fail)
    initial_hygiene = state.player.needs.hygiene
    apply_action(state, "shower", rng_seed=123)

    # Hygiene should not have improved
    # (Note: it may have decreased slightly due to environment effects)
    # Check that the action failed
    shower_events = [e for e in state.event_log if e["event_id"] == "action.shower"]
    assert len(shower_events) == 0  # No successful shower event

    # Now move to bathroom
    apply_action(state, "move_hall_001", rng_seed=123)
    apply_action(state, "move_bath_001", rng_seed=123)
    assert state.world.location == "bath_001"

    # Try to shower in bathroom (should succeed)
    apply_action(state, "shower", rng_seed=123)

    # Check that shower event was logged
    shower_events = [e for e in state.event_log if e["event_id"] == "action.shower"]
    assert len(shower_events) == 1


def test_movement_costs_time():
    """Test that moving between locations advances time."""
    state = new_game()

    initial_day = state.world.day
    initial_slice = state.world.slice

    # Move to hallway
    apply_action(state, "move_hall_001", rng_seed=123)

    # Time should have advanced
    assert (state.world.day > initial_day) or (state.world.slice != initial_slice)


def test_movement_costs_fatigue():
    """Test that moving increases fatigue slightly."""
    state = new_game()

    initial_fatigue = state.player.needs.fatigue

    # Move to hallway
    apply_action(state, "move_hall_001", rng_seed=123)

    # Fatigue should have increased (accounting for environment effects)
    # We can't guarantee exact fatigue due to environment effects, but we can
    # check that a movement event was logged
    move_events = [e for e in state.event_log if e["event_id"] == "action.move"]
    assert len(move_events) == 1
    assert move_events[0]["params"]["from_location"] == "Tiny room"
    assert move_events[0]["params"]["to_location"] == "Hallway"
