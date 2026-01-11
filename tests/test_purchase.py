from roomlife.engine import apply_action, new_game


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
    failed_events = [e for e in state.event_log 
                     if e["event_id"] == "action.failed" 
                     and e["params"].get("reason") == "insufficient_funds"]
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
    
    # Try to purchase a basic bed (price is 0, starter item)
    apply_action(state, "purchase_bed_basic", rng_seed=123)
    
    # Money should not be deducted
    assert state.player.money_pence == initial_money
    
    # Item count should not change
    assert len(state.items) == initial_item_count
    
    # Check that a failure event was logged
    failed_events = [e for e in state.event_log 
                     if e["event_id"] == "action.failed" 
                     and e["params"].get("reason") == "item_not_for_sale"]
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


def test_skill_gains_on_purchase():
    """Test that purchasing items grants resource_management skill XP."""
    state = new_game()
    
    # Give player enough money
    state.player.money_pence = 10000
    
    # Record initial skill value
    initial_skill = state.player.skills_detailed["resource_management"].value
    
    # Make a purchase
    apply_action(state, "purchase_bed_standard", rng_seed=123)
    
    # Skill should have increased
    final_skill = state.player.skills_detailed["resource_management"].value
    assert final_skill > initial_skill
    
    # Check that skill gain was logged in the purchase event
    purchase_events = [e for e in state.event_log if e["event_id"] == "shopping.purchase"]
    assert len(purchase_events) == 1
    assert "skill_gain" in purchase_events[0]["params"]
    assert purchase_events[0]["params"]["skill_gain"] > 0


def test_habit_tracking_on_purchase():
    """Test that purchasing items tracks confidence habit."""
    state = new_game()
    
    # Give player enough money
    state.player.money_pence = 10000
    
    # Record initial confidence habit value
    initial_confidence = state.player.habit_tracker.get("confidence", 0)
    
    # Make a purchase
    apply_action(state, "purchase_bed_standard", rng_seed=123)
    
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


def test_purchase_with_exact_money():
    """Test that a purchase works when player has exact amount needed."""
    state = new_game()
    
    # Give player exact money for a standard bed
    state.player.money_pence = 2500
    
    # Purchase should succeed
    apply_action(state, "purchase_bed_standard", rng_seed=123)
    
    # Money should be 0
    assert state.player.money_pence == 0
    
    # Item should be added
    assert len([item for item in state.items if item.item_id == "bed_standard"]) == 1


def test_purchase_with_one_pence_short():
    """Test that a purchase fails when player has one pence less than required."""
    state = new_game()
    
    # Give player one pence less than required for a standard bed
    state.player.money_pence = 2499
    initial_item_count = len(state.items)
    
    # Purchase should fail
    apply_action(state, "purchase_bed_standard", rng_seed=123)
    
    # Money should not change
    assert state.player.money_pence == 2499
    
    # Item should not be added
    assert len(state.items) == initial_item_count
    
    # Check failure event
    failed_events = [e for e in state.event_log 
                     if e["event_id"] == "action.failed" 
                     and e["params"].get("reason") == "insufficient_funds"]
    assert len(failed_events) == 1
