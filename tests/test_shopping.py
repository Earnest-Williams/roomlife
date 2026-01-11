from roomlife.engine import apply_action, new_game
from roomlife.models import Item


def test_sell_item_adds_money_and_removes_item():
    """Test that selling an item correctly adds money and removes the item from inventory."""
    state = new_game()
    
    # Add a standard bed that can be sold (price: 2500, condition: 100)
    state.items.append(Item(
        item_id="bed_standard",
        condition="pristine",
        condition_value=100,
        placed_in="room_001",
        slot="floor",
        quality=1.2
    ))
    
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)
    
    # Sell the standard bed
    apply_action(state, "sell_bed_standard", rng_seed=123)
    
    # Check that money was added (40% of 2500 = 1000 pence)
    expected_sell_price = int(2500 * 0.4 * 1.0)  # 40% * condition_multiplier (100/100)
    assert state.player.money_pence == initial_money + expected_sell_price
    
    # Check that item was removed
    assert len(state.items) == initial_item_count - 1
    assert not any(item.item_id == "bed_standard" for item in state.items)
    
    # Check that a sell event was logged
    sell_events = [e for e in state.event_log if e["event_id"] == "shopping.sell"]
    assert len(sell_events) == 1
    assert sell_events[0]["params"]["item_id"] == "bed_standard"
    assert sell_events[0]["params"]["earned_pence"] == expected_sell_price


def test_cannot_sell_item_not_at_current_location():
    """Test that items not at the current location cannot be sold."""
    state = new_game()
    
    # Add a standard bed in a different location (hallway)
    state.items.append(Item(
        item_id="bed_standard",
        condition="used",
        condition_value=80,
        placed_in="hall_001",  # Not at current location (room_001)
        slot="floor",
        quality=1.2
    ))
    
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)
    
    # Try to sell the bed
    apply_action(state, "sell_bed_standard", rng_seed=123)
    
    # Money should not have changed
    assert state.player.money_pence == initial_money
    
    # Item should still exist
    assert len(state.items) == initial_item_count
    assert any(item.item_id == "bed_standard" for item in state.items)
    
    # Check that a failed action event was logged
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) == 1


def test_sell_price_calculation_with_condition():
    """Test that sell price is calculated as 40% of base price adjusted by condition."""
    state = new_game()
    
    # Add a desk with 50% condition (price: 3000)
    state.items.append(Item(
        item_id="desk_basic",
        condition="worn",
        condition_value=50,
        placed_in="room_001",
        slot="wall",
        quality=1.0
    ))
    
    initial_money = state.player.money_pence
    
    # Sell the desk
    apply_action(state, "sell_desk_basic", rng_seed=123)
    
    # Calculate expected sell price: 40% of base price (3000) * condition (50/100)
    # = 3000 * 0.4 * 0.5 = 600 pence
    expected_sell_price = int(3000 * 0.4 * 0.5)
    
    # Check that correct amount was added
    assert state.player.money_pence == initial_money + expected_sell_price
    
    # Verify through event log
    sell_events = [e for e in state.event_log if e["event_id"] == "shopping.sell"]
    assert len(sell_events) == 1
    assert sell_events[0]["params"]["earned_pence"] == expected_sell_price


def test_sell_price_multiple_conditions():
    """Test sell price calculation with various condition values."""
    test_cases = [
        ("bed_premium", 6000, 100, 2400),  # pristine: 6000 * 0.4 * 1.0 = 2400
        ("bed_premium", 6000, 75, 1800),   # good: 6000 * 0.4 * 0.75 = 1800
        ("bed_premium", 6000, 25, 600),    # poor: 6000 * 0.4 * 0.25 = 600
    ]
    
    for item_id, base_price, condition_value, expected_price in test_cases:
        state = new_game()
        
        # Add item with specific condition
        state.items.append(Item(
            item_id=item_id,
            condition="used",
            condition_value=condition_value,
            placed_in="room_001",
            slot="floor",
            quality=1.4
        ))
        
        initial_money = state.player.money_pence
        
        # Sell the item
        apply_action(state, f"sell_{item_id}", rng_seed=123)
        
        # Verify correct price was received
        assert state.player.money_pence == initial_money + expected_price


def test_minimum_sell_price_enforced():
    """Test that minimum sell price of 100 pence is enforced."""
    state = new_game()
    
    # Add a cheap item with poor condition that would sell for less than 100 pence
    # For example, desk_basic (3000) at 5% condition would be: 3000 * 0.4 * 0.05 = 60
    # But minimum is 100
    state.items.append(Item(
        item_id="desk_basic",
        condition="broken",
        condition_value=5,
        placed_in="room_001",
        slot="wall",
        quality=1.0
    ))
    
    initial_money = state.player.money_pence
    
    # Sell the item
    apply_action(state, "sell_desk_basic", rng_seed=123)
    
    # Should receive minimum 100 pence
    assert state.player.money_pence == initial_money + 100
    
    # Verify through event log
    sell_events = [e for e in state.event_log if e["event_id"] == "shopping.sell"]
    assert len(sell_events) == 1
    assert sell_events[0]["params"]["earned_pence"] == 100


def test_starter_items_can_be_sold():
    """Test that starter items (price 0) can be sold but receive minimum price."""
    state = new_game()
    
    # The starter items are already in the game: bed_basic, desk_worn, kettle (all price 0)
    # Find the bed_basic starter item
    bed_basic = next((item for item in state.items if item.item_id == "bed_basic"), None)
    assert bed_basic is not None, "Starter bed_basic should exist"
    
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)
    
    # Try to sell the starter bed
    apply_action(state, "sell_bed_basic", rng_seed=123)
    
    # Item should be removed
    assert len(state.items) == initial_item_count - 1
    
    # Should receive minimum price (100 pence) since base price is 0
    # 0 * 0.4 * condition = 0, so minimum of 100 applies
    assert state.player.money_pence == initial_money + 100
    
    # Verify through event log
    sell_events = [e for e in state.event_log if e["event_id"] == "shopping.sell"]
    assert len(sell_events) == 1
    assert sell_events[0]["params"]["earned_pence"] == 100


def test_sell_action_grants_resource_management_skill():
    """Test that selling items grants resource_management skill XP.
    
    Note: The skill gain from a single sell action (0.3 base) may be offset by
    skill rust when time advances, so we start with an existing skill value to
    verify that the gain is applied before rust.
    """
    state = new_game()
    
    # Give player some existing skill so we can see the gain before rust
    # Start with enough skill that rust won't reduce it to zero
    state.player.skills_detailed["resource_management"].value = 5.0
    state.player.skills_detailed["resource_management"].last_tick = 4  # Current tick
    
    # Add an item to sell
    state.items.append(Item(
        item_id="bed_standard",
        condition="used",
        condition_value=80,
        placed_in="room_001",
        slot="floor",
        quality=1.2
    ))
    
    # Get initial skill value
    initial_skill_value = state.player.skills_detailed["resource_management"].value
    
    # Sell the item
    apply_action(state, "sell_bed_standard", rng_seed=123)
    
    # Verify through event log that skill gain was recorded
    # The actual skill gain is calculated during the action
    sell_events = [e for e in state.event_log if e["event_id"] == "shopping.sell"]
    assert len(sell_events) == 1
    assert "skill_gain" in sell_events[0]["params"]
    skill_gain_logged = sell_events[0]["params"]["skill_gain"]
    assert skill_gain_logged > 0
    
    # The final skill value will be: initial + gain - rust
    # We know the gain from the event log, and can calculate expected final value
    # Rust is skill.rust_rate * ticks_passed * (1.0 - discipline/100 * 0.3)
    skill = state.player.skills_detailed["resource_management"]
    rust_per_tick = skill.rust_rate * (1.0 - state.player.traits.discipline / 100.0 * 0.3)
    # Time advanced by 1 tick during the action
    expected_final = initial_skill_value + skill_gain_logged - rust_per_tick
    
    final_skill_value = skill.value
    # Allow for small floating point differences (within 0.01)
    assert abs(final_skill_value - expected_final) < 0.01, \
        f"Expected {expected_final:.3f}, got {final_skill_value:.3f}"


def test_sell_action_tracks_frugality_habit():
    """Test that selling items tracks the frugality habit."""
    state = new_game()
    
    # Add an item to sell
    state.items.append(Item(
        item_id="desk_basic",
        condition="used",
        condition_value=70,
        placed_in="room_001",
        slot="wall",
        quality=1.0
    ))
    
    # Get initial frugality tracker value
    initial_frugality = state.player.habit_tracker.get("frugality", 0)
    
    # Sell the item
    apply_action(state, "sell_desk_basic", rng_seed=123)
    
    # Check that frugality habit was tracked (should increase by 5)
    final_frugality = state.player.habit_tracker.get("frugality", 0)
    assert final_frugality == initial_frugality + 5


def test_sell_multiple_items_sequentially():
    """Test selling multiple items works correctly."""
    state = new_game()
    
    # Add multiple items
    state.items.append(Item(
        item_id="bed_standard",
        condition="used",
        condition_value=80,
        placed_in="room_001",
        slot="floor",
        quality=1.2
    ))
    state.items.append(Item(
        item_id="desk_basic",
        condition="used",
        condition_value=70,
        placed_in="room_001",
        slot="wall",
        quality=1.0
    ))
    
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)
    
    # Sell both items
    apply_action(state, "sell_bed_standard", rng_seed=123)
    apply_action(state, "sell_desk_basic", rng_seed=123)
    
    # Check that money increased appropriately
    # bed_standard: 2500 * 0.4 * 0.8 = 800
    # desk_basic: 3000 * 0.4 * 0.7 = 840
    expected_total = 800 + 840
    assert state.player.money_pence == initial_money + expected_total
    
    # Check that both items were removed
    assert len(state.items) == initial_item_count - 2
    assert not any(item.item_id == "bed_standard" for item in state.items)
    assert not any(item.item_id == "desk_basic" for item in state.items)


def test_cannot_sell_same_item_twice():
    """Test that trying to sell the same item twice fails on the second attempt."""
    state = new_game()
    
    # Add one item
    state.items.append(Item(
        item_id="bed_standard",
        condition="used",
        condition_value=80,
        placed_in="room_001",
        slot="floor",
        quality=1.2
    ))
    
    initial_money = state.player.money_pence
    
    # Sell the item once (should succeed)
    apply_action(state, "sell_bed_standard", rng_seed=123)
    money_after_first_sell = state.player.money_pence
    assert money_after_first_sell > initial_money
    
    # Try to sell again (should fail)
    apply_action(state, "sell_bed_standard", rng_seed=123)
    
    # Money should not have changed
    assert state.player.money_pence == money_after_first_sell
    
    # Check that a failed action event was logged for the second attempt
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) >= 1


def test_sell_nonexistent_item_fails():
    """Test that trying to sell an item that doesn't exist fails."""
    state = new_game()
    
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)
    
    # Try to sell an item that doesn't exist in inventory
    apply_action(state, "sell_bed_luxury", rng_seed=123)
    
    # Money should not have changed
    assert state.player.money_pence == initial_money
    
    # Item count should not have changed
    assert len(state.items) == initial_item_count
    
    # Check that a failed action event was logged
    failed_events = [e for e in state.event_log if e["event_id"] == "action.failed" and e["params"].get("reason") == "item_not_found"]
    assert len(failed_events) == 1
