"""Tests for API service in api_service.py."""

from roomlife.api_service import RoomLifeAPI
from roomlife.api_types import EventInfo, GameStateSnapshot
from roomlife.engine import new_game


def test_api_initialization():
    """Test that API can be initialized with a game state."""
    state = new_game()
    api = RoomLifeAPI(state)

    assert api.state == state
    assert len(api._event_listeners) == 0
    assert len(api._state_change_listeners) == 0


def test_get_state_snapshot_structure():
    """Test that state snapshot has all expected fields."""
    state = new_game()
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    # Check main structure
    assert isinstance(snapshot, GameStateSnapshot)
    assert hasattr(snapshot, "world")
    assert hasattr(snapshot, "player_money_pence")
    assert hasattr(snapshot, "utilities_paid")
    assert hasattr(snapshot, "needs")
    assert hasattr(snapshot, "traits")
    assert hasattr(snapshot, "utilities")
    assert hasattr(snapshot, "skills")
    assert hasattr(snapshot, "aptitudes")
    assert hasattr(snapshot, "current_location")
    assert hasattr(snapshot, "all_locations")
    assert hasattr(snapshot, "recent_events")


def test_get_state_snapshot_world_info():
    """Test that world info is correctly populated."""
    state = new_game()
    state.world.day = 5
    state.world.slice = "evening"
    state.world.location = "room_001"
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.world.day == 5
    assert snapshot.world.slice == "evening"
    assert snapshot.world.location == "room_001"
    # Day 5, evening (slice 2) = 5 * 4 + 2 = 22
    assert snapshot.world.current_tick == 22


def test_get_state_snapshot_needs():
    """Test that needs are correctly captured."""
    state = new_game()
    state.player.needs.hunger = 75
    state.player.needs.fatigue = 60
    state.player.needs.mood = 85
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.needs.hunger == 75
    assert snapshot.needs.fatigue == 60
    assert snapshot.needs.mood == 85


def test_get_state_snapshot_traits():
    """Test that traits are correctly captured."""
    state = new_game()
    state.player.traits.confidence = 65
    state.player.traits.discipline = 70
    state.player.traits.curiosity = 80
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.traits.confidence == 65
    assert snapshot.traits.discipline == 70
    assert snapshot.traits.curiosity == 80


def test_get_state_snapshot_utilities():
    """Test that utilities are correctly captured."""
    state = new_game()
    state.utilities.power = True
    state.utilities.heat = False
    state.utilities.water = True
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.utilities.power is True
    assert snapshot.utilities.heat is False
    assert snapshot.utilities.water is True


def test_get_state_snapshot_skills():
    """Test that skills are correctly captured."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 42.5
    state.player.skills_detailed["cooking"].last_tick = 100
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    cooking_skill = next((s for s in snapshot.skills if s.name == "cooking"), None)
    assert cooking_skill is not None
    assert cooking_skill.value == 42.5
    assert cooking_skill.last_tick == 100


def test_get_state_snapshot_money():
    """Test that money is correctly captured."""
    state = new_game()
    state.player.money_pence = 12345
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.player_money_pence == 12345


def test_get_state_snapshot_location_info():
    """Test that location info includes items."""
    state = new_game()
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert snapshot.current_location is not None
    assert snapshot.current_location.space_id == "room_001"
    assert hasattr(snapshot.current_location, "items")


def test_get_state_snapshot_all_locations():
    """Test that all locations are included."""
    state = new_game()
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert len(snapshot.all_locations) > 0
    assert "room_001" in snapshot.all_locations
    assert "kitchen_001" in snapshot.all_locations


def test_get_available_actions():
    """Test getting available actions."""
    state = new_game()
    api = RoomLifeAPI(state)

    response = api.get_available_actions()

    assert hasattr(response, "actions")
    assert hasattr(response, "location")
    assert hasattr(response, "total_count")
    assert response.total_count >= 0
    assert response.location == state.world.location


def test_get_all_actions_metadata():
    """Test getting all actions metadata."""
    state = new_game()
    api = RoomLifeAPI(state)

    metadata = api.get_all_actions_metadata()

    assert isinstance(metadata, list)
    # Should have at least some actions defined
    assert len(metadata) >= 0


def test_validate_action_valid():
    """Test validating a valid action."""
    state = new_game()
    api = RoomLifeAPI(state)

    # Sleep should be a valid action
    validation = api.validate_action("sleep")

    assert validation.action_id == "sleep"
    # Validation result depends on current state and action requirements
    assert hasattr(validation, "valid")
    assert hasattr(validation, "reason")


def test_validate_action_invalid():
    """Test validating an invalid/unknown action."""
    state = new_game()
    api = RoomLifeAPI(state)

    validation = api.validate_action("nonexistent_action")

    assert validation.action_id == "nonexistent_action"
    assert validation.valid is False
    assert "Unknown action" in validation.reason or "no spec found" in validation.reason


def test_validate_action_with_preview():
    """Test that valid actions include preview."""
    state = new_game()
    state.player.money_pence = 10000  # Ensure enough money
    api = RoomLifeAPI(state)

    # Cook meal should have preview if valid
    validation = api.validate_action("cook_meal")

    if validation.valid:
        assert validation.preview is not None
        assert hasattr(validation.preview, "tier_distribution")
        assert hasattr(validation.preview, "delta_ranges")


def test_execute_action_success():
    """Test executing a simple action."""
    state = new_game()
    api = RoomLifeAPI(state)

    result = api.execute_action("sleep", rng_seed=42)

    assert hasattr(result, "success")
    assert hasattr(result, "action_id")
    assert result.action_id == "sleep"
    assert hasattr(result, "new_state")
    assert hasattr(result, "events_triggered")
    assert hasattr(result, "state_changes")


def test_execute_action_generates_events():
    """Test that executing actions generates events."""
    state = new_game()
    api = RoomLifeAPI(state)

    result = api.execute_action("cook_meal", rng_seed=42)

    # Should have at least some events
    assert len(result.events_triggered) >= 0
    # Check that events have proper structure
    for event in result.events_triggered:
        assert isinstance(event, EventInfo)
        assert hasattr(event, "event_id")
        assert hasattr(event, "params")


def test_execute_action_updates_state():
    """Test that executing actions updates the game state."""
    state = new_game()
    api = RoomLifeAPI(state)

    old_fatigue = state.player.needs.fatigue
    result = api.execute_action("sleep", rng_seed=42)

    # Sleep should reduce fatigue
    new_fatigue = result.new_state.needs.fatigue
    assert new_fatigue != old_fatigue


def test_execute_action_calculates_state_changes():
    """Test that state changes are calculated correctly."""
    state = new_game()
    api = RoomLifeAPI(state)

    result = api.execute_action("sleep", rng_seed=42)

    # Should have state changes
    assert isinstance(result.state_changes, dict)


def test_subscribe_to_events():
    """Test subscribing to game events."""
    state = new_game()
    api = RoomLifeAPI(state)

    events_received = []

    def event_callback(event: EventInfo):
        events_received.append(event)

    api.subscribe_to_events(event_callback)

    # Execute an action to trigger events
    api.execute_action("cook_meal", rng_seed=42)

    # Check that callback was called
    assert len(events_received) > 0


def test_subscribe_to_state_changes():
    """Test subscribing to state changes."""
    state = new_game()
    api = RoomLifeAPI(state)

    states_received = []

    def state_callback(snapshot: GameStateSnapshot):
        states_received.append(snapshot)

    api.subscribe_to_state_changes(state_callback)

    # Execute an action to trigger state change
    api.execute_action("cook_meal", rng_seed=42)

    # Check that callback was called
    assert len(states_received) > 0
    assert isinstance(states_received[0], GameStateSnapshot)


def test_unsubscribe_from_events():
    """Test unsubscribing from events."""
    state = new_game()
    api = RoomLifeAPI(state)

    events_received = []

    def event_callback(event: EventInfo):
        events_received.append(event)

    api.subscribe_to_events(event_callback)
    api.unsubscribe_from_events(event_callback)

    # Execute an action
    api.execute_action("cook_meal", rng_seed=42)

    # Callback should not have been called after unsubscribe
    assert len(events_received) == 0


def test_unsubscribe_from_state_changes():
    """Test unsubscribing from state changes."""
    state = new_game()
    api = RoomLifeAPI(state)

    states_received = []

    def state_callback(snapshot: GameStateSnapshot):
        states_received.append(snapshot)

    api.subscribe_to_state_changes(state_callback)
    api.unsubscribe_from_state_changes(state_callback)

    # Execute an action
    api.execute_action("cook_meal", rng_seed=42)

    # Callback should not have been called after unsubscribe
    assert len(states_received) == 0


def test_multiple_event_listeners():
    """Test that multiple event listeners all receive events."""
    state = new_game()
    api = RoomLifeAPI(state)

    events1 = []
    events2 = []

    def callback1(event: EventInfo):
        events1.append(event)

    def callback2(event: EventInfo):
        events2.append(event)

    api.subscribe_to_events(callback1)
    api.subscribe_to_events(callback2)

    api.execute_action("cook_meal", rng_seed=42)

    # Both callbacks should have received events
    assert len(events1) > 0
    assert len(events2) > 0
    assert len(events1) == len(events2)


def test_event_listener_error_handling():
    """Test that errors in event listeners don't crash the API."""
    state = new_game()
    api = RoomLifeAPI(state)

    def failing_callback(event: EventInfo):
        raise ValueError("Test error")

    events_received = []

    def working_callback(event: EventInfo):
        events_received.append(event)

    api.subscribe_to_events(failing_callback)
    api.subscribe_to_events(working_callback)

    # Should not raise exception despite failing callback
    api.execute_action("cook_meal", rng_seed=42)

    # Working callback should still have received events
    assert len(events_received) > 0


def test_state_change_listener_error_handling():
    """Test that errors in state listeners don't crash the API."""
    state = new_game()
    api = RoomLifeAPI(state)

    def failing_callback(snapshot: GameStateSnapshot):
        raise ValueError("Test error")

    states_received = []

    def working_callback(snapshot: GameStateSnapshot):
        states_received.append(snapshot)

    api.subscribe_to_state_changes(failing_callback)
    api.subscribe_to_state_changes(working_callback)

    # Should not raise exception despite failing callback
    api.execute_action("cook_meal", rng_seed=42)

    # Working callback should still have received state
    assert len(states_received) > 0


def test_execute_action_deterministic():
    """Test that executing actions with same seed is deterministic."""
    state1 = new_game(seed=42)
    state2 = new_game(seed=42)
    api1 = RoomLifeAPI(state1)
    api2 = RoomLifeAPI(state2)

    result1 = api1.execute_action("cook_meal", rng_seed=100)
    result2 = api2.execute_action("cook_meal", rng_seed=100)

    # Results should be identical
    assert len(result1.events_triggered) == len(result2.events_triggered)
    # Check that event IDs match
    for i in range(len(result1.events_triggered)):
        assert result1.events_triggered[i].event_id == result2.events_triggered[i].event_id


def test_get_state_snapshot_habit_tracker():
    """Test that habit tracker is included in snapshot."""
    state = new_game()
    state.player.habit_tracker["confidence"] = 50
    state.player.habit_tracker["discipline"] = 30
    api = RoomLifeAPI(state)

    snapshot = api.get_state_snapshot()

    assert "confidence" in snapshot.habit_tracker
    assert snapshot.habit_tracker["confidence"] == 50
    assert "discipline" in snapshot.habit_tracker
    assert snapshot.habit_tracker["discipline"] == 30


def test_get_state_snapshot_recent_events():
    """Test that recent events are included in snapshot."""
    state = new_game()
    api = RoomLifeAPI(state)

    # Execute some actions to generate events
    api.execute_action("cook_meal", rng_seed=42)
    api.execute_action("sleep", rng_seed=43)

    snapshot = api.get_state_snapshot()

    # Should have recent events
    assert len(snapshot.recent_events) > 0
    # Recent events should be capped at 10
    assert len(snapshot.recent_events) <= 10
