"""Tests for parameter resolution and validation in param_resolver.py."""

from roomlife.engine import new_game
from roomlife.models import Item, generate_instance_id
from roomlife.param_resolver import (
    apply_drop,
    apply_pickup,
    is_item_reachable,
    resolve_param_item_ref,
    resolve_param_space_id,
    select_item_instance,
    validate_connected_to_param,
    validate_parameters,
)


def test_resolve_param_space_id_valid():
    """Test that valid space IDs are accepted."""
    state = new_game()
    ok, msg = resolve_param_space_id(state, "room_001")
    assert ok is True
    assert msg == ""


def test_resolve_param_space_id_invalid():
    """Test that invalid space IDs are rejected."""
    state = new_game()
    ok, msg = resolve_param_space_id(state, "nonexistent_space")
    assert ok is False
    assert "unknown space_id" in msg


def test_resolve_param_space_id_not_string():
    """Test that non-string space IDs are rejected."""
    state = new_game()
    ok, msg = resolve_param_space_id(state, 123)
    assert ok is False
    assert "must be a string" in msg


def test_resolve_param_item_ref_instance_id_valid():
    """Test that valid item instance IDs are accepted."""
    state = new_game()
    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    ok, msg = resolve_param_item_ref(state, {"mode": "instance_id", "instance_id": "test_001"})
    assert ok is True
    assert msg == ""


def test_resolve_param_item_ref_instance_id_invalid():
    """Test that invalid instance IDs are rejected."""
    state = new_game()
    ok, msg = resolve_param_item_ref(state, {"mode": "instance_id", "instance_id": "nonexistent"})
    assert ok is False
    assert "unknown instance_id" in msg


def test_resolve_param_item_ref_by_item_id_valid():
    """Test that valid item IDs are accepted."""
    state = new_game()
    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    ok, msg = resolve_param_item_ref(state, {"mode": "by_item_id", "item_id": "bed_standard"})
    assert ok is True
    assert msg == ""


def test_resolve_param_item_ref_by_item_id_invalid():
    """Test that invalid item IDs are rejected."""
    state = new_game()
    ok, msg = resolve_param_item_ref(state, {"mode": "by_item_id", "item_id": "nonexistent_item"})
    assert ok is False
    assert "no such item_id" in msg


def test_resolve_param_item_ref_invalid_mode():
    """Test that invalid modes are rejected."""
    state = new_game()
    ok, msg = resolve_param_item_ref(state, {"mode": "invalid_mode"})
    assert ok is False
    assert "must be instance_id or by_item_id" in msg


def test_is_item_reachable_inventory():
    """Test that items in inventory are reachable."""
    state = new_game()
    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="inventory",
        container=None,
        slot="inventory",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    assert is_item_reachable(state, item) is True


def test_is_item_reachable_current_location():
    """Test that items at current location are reachable."""
    state = new_game()
    state.world.location = "room_001"
    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    assert is_item_reachable(state, item) is True


def test_is_item_reachable_other_location():
    """Test that items at other locations are not reachable."""
    state = new_game()
    state.world.location = "room_001"
    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    assert is_item_reachable(state, item) is False


def test_select_item_instance_by_instance_id():
    """Test selecting an item by instance ID."""
    state = new_game()
    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    item = select_item_instance(state, {"mode": "instance_id", "instance_id": "test_001"})
    assert item is not None
    assert item.instance_id == "test_001"
    assert item.item_id == "bed_standard"


def test_select_item_instance_by_item_id_prefers_best_condition():
    """Test that selecting by item ID prefers highest condition."""
    state = new_game()
    state.world.location = "room_001"

    # Add multiple instances with different conditions
    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="worn",
        condition_value=50,
        bulk=1
    ))
    state.items.append(Item(
        instance_id="test_002",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))
    state.items.append(Item(
        instance_id="test_003",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="used",
        condition_value=75,
        bulk=1
    ))

    item = select_item_instance(state, {"mode": "by_item_id", "item_id": "bed_standard"})
    assert item is not None
    assert item.instance_id == "test_002"  # Highest condition
    assert item.condition_value == 100


def test_select_item_instance_only_reachable():
    """Test that item selection only considers reachable items."""
    state = new_game()
    state.world.location = "room_001"

    # Add item in different location (not reachable)
    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    # Add item in current location (reachable)
    state.items.append(Item(
        instance_id="test_002",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="used",
        condition_value=80,
        bulk=1
    ))

    item = select_item_instance(state, {"mode": "by_item_id", "item_id": "bed_standard"})
    assert item is not None
    assert item.instance_id == "test_002"  # Only reachable one


def test_apply_pickup_success():
    """Test successful item pickup."""
    state = new_game()
    state.world.location = "room_001"
    state.player.carry_capacity = 10

    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    state.items.append(item)

    ok, msg = apply_pickup(state, item)
    assert ok is True
    assert msg == ""
    assert item.placed_in == "inventory"
    assert item.slot == "inventory"


def test_apply_pickup_item_not_at_location():
    """Test that pickup fails if item is not at current location."""
    state = new_game()
    state.world.location = "room_001"

    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    state.items.append(item)

    ok, msg = apply_pickup(state, item)
    assert ok is False
    assert "not at current location" in msg


def test_apply_pickup_inventory_full():
    """Test that pickup fails if inventory is full."""
    state = new_game()
    state.world.location = "room_001"
    state.player.carry_capacity = 5

    # Fill inventory
    for i in range(5):
        state.items.append(Item(
            instance_id=f"existing_{i}",
            item_id="small_item",
            placed_in="inventory",
            container=None,
            slot="inventory",
            quality=1.0,
            condition="pristine",
            condition_value=100,
            bulk=1
        ))

    # Try to pick up another item
    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    state.items.append(item)

    ok, msg = apply_pickup(state, item)
    assert ok is False
    assert "inventory full" in msg


def test_apply_drop_success():
    """Test successful item drop."""
    state = new_game()
    state.world.location = "room_001"

    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="inventory",
        container=None,
        slot="inventory",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    state.items.append(item)

    ok, msg = apply_drop(state, item)
    assert ok is True
    assert msg == ""
    assert item.placed_in == "room_001"
    assert item.slot == "floor"


def test_apply_drop_item_not_in_inventory():
    """Test that drop fails if item is not in inventory."""
    state = new_game()
    state.world.location = "room_001"

    item = Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )
    state.items.append(item)

    ok, msg = apply_drop(state, item)
    assert ok is False
    assert "not in inventory" in msg


def test_validate_connected_to_param_success():
    """Test that connected space validation succeeds."""
    state = new_game()
    state.world.location = "room_001"

    # room_001 is connected to hall_001 by default
    ok, msg = validate_connected_to_param(state, "target_space", {"target_space": "hall_001"})
    assert ok is True
    assert msg == ""


def test_validate_connected_to_param_not_connected():
    """Test that validation fails for non-connected spaces."""
    state = new_game()
    state.world.location = "room_001"

    # room_001 is not connected to kitchen_001
    ok, msg = validate_connected_to_param(state, "target_space", {"target_space": "kitchen_001"})
    assert ok is False
    assert "not connected" in msg


def test_validate_connected_to_param_invalid_space():
    """Test that validation fails for invalid space ID."""
    state = new_game()
    state.world.location = "room_001"

    ok, msg = validate_connected_to_param(state, "target_space", {"target_space": "nonexistent"})
    assert ok is False
    assert "not connected" in msg


def test_validate_parameters_with_required_params():
    """Test parameter validation with required parameters."""
    state = new_game()

    # Mock action spec with required space_id parameter
    class MockSpec:
        parameters = [{"name": "target_space", "type": "space_id", "required": True}]

    spec = MockSpec()
    ok, missing = validate_parameters(state, spec, {"target_space": "room_001"})
    assert ok is True
    assert len(missing) == 0


def test_validate_parameters_missing_required():
    """Test that validation fails when required parameters are missing."""
    state = new_game()

    class MockSpec:
        parameters = [{"name": "target_space", "type": "space_id", "required": True}]

    spec = MockSpec()
    ok, missing = validate_parameters(state, spec, {})
    assert ok is False
    assert len(missing) == 1
    assert "missing param" in missing[0]


def test_validate_parameters_with_item_ref_constraints():
    """Test parameter validation with item_ref constraints."""
    state = new_game()
    state.world.location = "room_001"

    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    class MockSpec:
        parameters = [
            {
                "name": "item",
                "type": "item_ref",
                "required": True,
                "constraints": {"reachable": True}
            }
        ]

    spec = MockSpec()
    ok, missing = validate_parameters(
        state,
        spec,
        {"item": {"mode": "instance_id", "instance_id": "test_001"}}
    )
    assert ok is True
    assert len(missing) == 0


def test_validate_parameters_item_not_reachable():
    """Test that validation fails when item is not reachable."""
    state = new_game()
    state.world.location = "room_001"

    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="kitchen_001",  # Different location
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    class MockSpec:
        parameters = [
            {
                "name": "item",
                "type": "item_ref",
                "required": True,
                "constraints": {"reachable": True}
            }
        ]

    spec = MockSpec()
    ok, missing = validate_parameters(
        state,
        spec,
        {"item": {"mode": "instance_id", "instance_id": "test_001"}}
    )
    assert ok is False
    assert any("reachable" in m for m in missing)


def test_validate_parameters_in_inventory_constraint():
    """Test validation of in_inventory constraint."""
    state = new_game()

    state.items.append(Item(
        instance_id="test_001",
        item_id="bed_standard",
        placed_in="inventory",
        container=None,
        slot="inventory",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    class MockSpec:
        parameters = [
            {
                "name": "item",
                "type": "item_ref",
                "required": True,
                "constraints": {"in_inventory": True}
            }
        ]

    spec = MockSpec()
    ok, missing = validate_parameters(
        state,
        spec,
        {"item": {"mode": "instance_id", "instance_id": "test_001"}}
    )
    assert ok is True
    assert len(missing) == 0


def test_validate_parameters_string_type():
    """Test validation of string parameters."""
    state = new_game()

    class MockSpec:
        parameters = [{"name": "job_id", "type": "string", "required": True}]

    spec = MockSpec()
    ok, missing = validate_parameters(state, spec, {"job_id": "bartender"})
    assert ok is True
    assert len(missing) == 0


def test_validate_parameters_string_type_invalid():
    """Test that non-string values fail string validation."""
    state = new_game()

    class MockSpec:
        parameters = [{"name": "job_id", "type": "string", "required": True}]

    spec = MockSpec()
    ok, missing = validate_parameters(state, spec, {"job_id": 123})
    assert ok is False
    assert any("must be a string" in m for m in missing)
