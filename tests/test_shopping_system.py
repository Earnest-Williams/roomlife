"""Tests for shopping system: purchase, sell, and discard actions."""

from roomlife.engine import apply_action, new_game
from roomlife.models import Item, generate_instance_id


def _get_failed_events(state, reason):
    """Helper function to get failed events by reason."""
    return [e for e in state.event_log
            if e["event_id"] == "action.failed"
            and e["params"].get("reason") == reason]


# ===== PURCHASE TESTS =====

def test_successful_purchase_deducts_money_and_adds_item():
    """Test that a successful purchase deducts money and adds the item to inventory."""
    state = new_game()

    # Give player enough money for a standard bed (2500 pence)
    state.player.money_pence = 5000
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Purchase a standard bed
    apply_action(state, "purchase_bed_standard", rng_seed=123)

    # Money should be deducted (standard bed costs 2500 pence)
    assert state.player.money_pence == initial_money - 2500

    # Item count should increase by 1
    assert len(state.items) == initial_item_count + 1

    # The new item should be a bed_standard with pristine condition
    new_item = state.items[-1]
    assert new_item.item_id == "bed_standard"
    assert new_item.condition == "pristine"
    assert new_item.condition_value == 100
    assert new_item.placed_in == state.world.location
    assert new_item.slot == "floor"

    # Check that a success event was logged
    purchase_events = [e for e in state.event_log if e["event_id"] == "shopping.purchase"]
    assert len(purchase_events) == 1
    assert purchase_events[0]["params"]["item_id"] == "bed_standard"
    assert purchase_events[0]["params"]["cost_pence"] == 2500


def test_insufficient_funds_rejected():
    """Test that purchases are rejected when player has insufficient funds."""
    state = new_game()

    # Give player less money than required for a standard bed (2500 pence)
    state.player.money_pence = 1000
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Try to purchase a standard bed
    apply_action(state, "purchase_bed_standard", rng_seed=123)

    # Money should not be deducted
    assert state.player.money_pence == initial_money

    # Item count should not change
    assert len(state.items) == initial_item_count

    # Check that a failure event was logged
    failed_events = _get_failed_events(state, "insufficient_funds")
    assert len(failed_events) == 1
    assert failed_events[0]["params"]["required_pence"] == 2500
    assert failed_events[0]["params"]["current_pence"] == 1000


def test_cannot_purchase_items_with_price_zero():
    """Test that items with price 0 cannot be purchased."""
    state = new_game()

    # Give player plenty of money
    state.player.money_pence = 10000
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Try to purchase a non-existent item (which gets price 0 from fallback)
    apply_action(state, "purchase_nonexistent_item", rng_seed=123)

    # Money should not be deducted
    assert state.player.money_pence == initial_money

    # Item count should not change
    assert len(state.items) == initial_item_count

    # Check that a failure event was logged
    failed_events = _get_failed_events(state, "item_not_for_sale")
    assert len(failed_events) == 1


def test_quality_correctly_applied_to_purchased_items():
    """Test that quality from metadata is correctly applied to purchased items."""
    state = new_game()

    # Give player enough money
    state.player.money_pence = 20000

    # Purchase items with different quality levels
    # Standard bed has quality 1.2
    apply_action(state, "purchase_bed_standard", rng_seed=123)
    bed_standard = [item for item in state.items if item.item_id == "bed_standard"][-1]
    assert bed_standard.quality == 1.2

    # Premium bed has quality 1.4
    apply_action(state, "purchase_bed_premium", rng_seed=123)
    bed_premium = [item for item in state.items if item.item_id == "bed_premium"][-1]
    assert bed_premium.quality == 1.4

    # Basic desk has quality 1.0
    apply_action(state, "purchase_desk_basic", rng_seed=123)
    desk_basic = [item for item in state.items if item.item_id == "desk_basic"][-1]
    assert desk_basic.quality == 1.0


def test_purchase_grants_skill_and_tracks_habit():
    """Test that purchasing items grants resource_management skill XP and tracks confidence habit."""
    state = new_game()

    # Give player enough money
    state.player.money_pence = 10000

    # Record initial values
    initial_skill = state.player.skills_detailed["resource_management"].value
    initial_confidence = state.player.habit_tracker.get("confidence", 0)

    # Make a purchase
    apply_action(state, "purchase_bed_standard", rng_seed=123)

    # Skill should have increased
    final_skill = state.player.skills_detailed["resource_management"].value
    assert final_skill > initial_skill

    # Check that skill gain was logged
    skill_events = [e for e in state.event_log if e["event_id"] == "skill.gain"]
    rm_gains = [e for e in skill_events if e["params"].get("skill") == "resource_management"]
    assert len(rm_gains) > 0
    assert rm_gains[-1]["params"]["xp"] > 0

    # Confidence habit should have increased by 3
    final_confidence = state.player.habit_tracker.get("confidence", 0)
    assert final_confidence == initial_confidence + 3


def test_multiple_purchases():
    """Test that multiple purchases work correctly."""
    state = new_game()

    # Give player enough money for multiple items
    state.player.money_pence = 20000
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Purchase multiple items
    apply_action(state, "purchase_bed_standard", rng_seed=123)  # 2500 pence
    apply_action(state, "purchase_desk_basic", rng_seed=123)    # 3000 pence
    apply_action(state, "purchase_bed_premium", rng_seed=123)   # 6000 pence

    # Check money deduction (total: 11500 pence)
    assert state.player.money_pence == initial_money - 11500

    # Check item count increased by 3
    assert len(state.items) == initial_item_count + 3

    # Check all items were added
    item_ids = [item.item_id for item in state.items]
    assert "bed_standard" in item_ids
    assert "desk_basic" in item_ids
    assert "bed_premium" in item_ids


# ===== SELL TESTS =====

def test_sell_item_adds_money_and_removes_item():
    """Test that selling an item correctly adds money and removes the item from inventory."""
    state = new_game()

    # Add a standard bed that can be sold (price: 2500, condition: 100)
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.2,
        condition="pristine",
        condition_value=100
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


def test_sell_price_calculation_with_condition():
    """Test that sell price is calculated as 40% of base price adjusted by condition."""
    test_cases = [
        ("bed_premium", 6000, 100, 2400),  # pristine: 6000 * 0.4 * 1.0 = 2400
        ("bed_premium", 6000, 75, 1800),   # good: 6000 * 0.4 * 0.75 = 1800
        ("bed_premium", 6000, 50, 1200),   # worn: 6000 * 0.4 * 0.5 = 1200
    ]

    for item_id, base_price, condition_value, expected_price in test_cases:
        state = new_game()

        # Add item with specific condition
        state.items.append(Item(
            instance_id=generate_instance_id(),
            item_id=item_id,
            placed_in="room_001",
            container=None,
            slot="floor",
            quality=1.4,
            condition="used",
            condition_value=condition_value
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
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="desk_basic",
        placed_in="room_001",
        container=None,
        slot="wall",
        quality=1.0,
        condition="broken",
        condition_value=5
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


def test_sell_grants_skill_and_tracks_habit():
    """Test that selling items grants resource_management skill XP and tracks frugality habit."""
    state = new_game()

    # Give player some existing skill so we can see the gain before rust
    state.player.skills_detailed["resource_management"].value = 5.0
    state.player.skills_detailed["resource_management"].last_tick = 4

    # Add an item to sell
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.2,
        condition="used",
        condition_value=80
    ))

    # Get initial values
    initial_frugality = state.player.habit_tracker.get("frugality", 0)

    # Sell the item
    apply_action(state, "sell_bed_standard", rng_seed=123)

    # Verify skill gain was logged
    skill_events = [e for e in state.event_log if e["event_id"] == "skill.gain"]
    rm_gains = [e for e in skill_events if e["params"].get("skill") == "resource_management"]
    assert len(rm_gains) > 0
    assert rm_gains[-1]["params"]["xp"] > 0

    # Check that frugality habit was tracked (should increase by 5)
    final_frugality = state.player.habit_tracker.get("frugality", 0)
    assert final_frugality == initial_frugality + 5


def test_sell_multiple_items_sequentially():
    """Test selling multiple items works correctly."""
    state = new_game()

    # Add multiple items
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.2,
        condition="used",
        condition_value=80
    ))
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="desk_basic",
        placed_in="room_001",
        container=None,
        slot="wall",
        quality=1.0,
        condition="used",
        condition_value=70
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


# ===== DISCARD TESTS =====

def test_discard_removes_item_without_money():
    """Test that discarding an item removes it without giving money."""
    state = new_game()

    # Add an item to discard
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100
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


def test_discard_tracks_minimalism_habit():
    """Test that discarding an item tracks the minimalism habit."""
    state = new_game()

    # Add an item to discard
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="desk_basic",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="worn",
        condition_value=50
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
        instance_id=generate_instance_id(),
        item_id="worthless_item",  # Non-existent item gets price 0 from fallback
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=0.5,
        condition="broken",
        condition_value=10
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


# ===== SHARED FAILURE TESTS =====

def test_item_operations_fail_for_nonexistent_items():
    """Test that all item operations fail for nonexistent items."""
    state = new_game()
    initial_money = state.player.money_pence
    initial_item_count = len(state.items)

    # Try each operation on nonexistent item
    apply_action(state, "sell_bed_luxury", rng_seed=123)
    apply_action(state, "discard_bed_luxury", rng_seed=124)

    # Money and item count should not change
    assert state.player.money_pence == initial_money
    assert len(state.items) == initial_item_count

    # Check that failure events were logged
    failed_events = _get_failed_events(state, "item_not_found")
    assert len(failed_events) >= 2


def test_cannot_operate_on_same_item_twice():
    """Test that trying to sell/discard the same item twice fails on the second attempt."""
    # Test sell twice
    state = new_game()
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="bed_standard",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.2,
        condition="used",
        condition_value=80
    ))

    initial_money = state.player.money_pence

    # Sell once (should succeed)
    apply_action(state, "sell_bed_standard", rng_seed=123)
    money_after_first = state.player.money_pence
    assert money_after_first > initial_money

    # Try to sell again (should fail)
    apply_action(state, "sell_bed_standard", rng_seed=124)
    assert state.player.money_pence == money_after_first

    # Test discard twice
    state = new_game()
    state.items.append(Item(
        instance_id=generate_instance_id(),
        item_id="desk_basic",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="worn",
        condition_value=50
    ))

    initial_count = len(state.items)

    # Discard once (should succeed)
    apply_action(state, "discard_desk_basic", rng_seed=123)
    assert len(state.items) == initial_count - 1

    # Try to discard again (should fail)
    apply_action(state, "discard_desk_basic", rng_seed=124)
    assert len(state.items) == initial_count - 1
