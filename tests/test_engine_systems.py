"""Tests for skill, health, trait, and job systems in engine.py."""

from roomlife.engine import (
    _apply_skill_rust,
    _apply_trait_drift,
    _calculate_current_tick,
    _calculate_health,
    _check_job_requirements,
    _gain_skill_xp,
    _get_health_penalty,
    _get_item_effectiveness,
    new_game,
)
from roomlife.models import Item, Skill


def test_calculate_health_from_illness_and_injury():
    """Test that health is calculated from illness and injury."""
    state = new_game()

    # No illness or injury
    state.player.needs.illness = 0
    state.player.needs.injury = 0
    _calculate_health(state)
    assert state.player.needs.health == 100

    # Some illness
    state.player.needs.illness = 40
    state.player.needs.injury = 0
    _calculate_health(state)
    assert state.player.needs.health == 80  # 100 - (40 * 0.5)

    # Some injury
    state.player.needs.illness = 0
    state.player.needs.injury = 60
    _calculate_health(state)
    assert state.player.needs.health == 70  # 100 - (60 * 0.5)

    # Both illness and injury
    state.player.needs.illness = 40
    state.player.needs.injury = 60
    _calculate_health(state)
    assert state.player.needs.health == 50  # 100 - ((40 + 60) * 0.5)


def test_calculate_health_cannot_go_negative():
    """Test that health cannot go below 0."""
    state = new_game()
    state.player.needs.illness = 100
    state.player.needs.injury = 100
    _calculate_health(state)
    assert state.player.needs.health == 0


def test_calculate_health_cannot_exceed_100():
    """Test that health cannot exceed 100."""
    state = new_game()
    state.player.needs.illness = -50  # Negative values shouldn't happen but test boundary
    state.player.needs.injury = 0
    _calculate_health(state)
    assert state.player.needs.health == 100


def test_get_health_penalty_full_health():
    """Test health penalty when health is above threshold."""
    state = new_game()
    state.player.needs.illness = 0
    state.player.needs.injury = 0
    penalty = _get_health_penalty(state)
    assert penalty == 1.0


def test_get_health_penalty_low_health():
    """Test health penalty when health is low."""
    state = new_game()
    state.player.needs.illness = 60
    state.player.needs.injury = 40
    # Total health = 100 - ((60 + 40) * 0.5) = 50
    penalty = _get_health_penalty(state)
    # At health 50 (threshold), penalty should be 1.0
    assert penalty == 1.0


def test_get_health_penalty_zero_health():
    """Test health penalty at zero health."""
    state = new_game()
    state.player.needs.illness = 100
    state.player.needs.injury = 100
    penalty = _get_health_penalty(state)
    assert penalty == 0.5


def test_get_health_penalty_below_threshold():
    """Test health penalty below threshold."""
    state = new_game()
    # Set health to 25 (below threshold of 50)
    state.player.needs.illness = 75
    state.player.needs.injury = 75
    penalty = _get_health_penalty(state)
    # At health 25, penalty = 0.5 + (25 / 50) * 0.5 = 0.75
    assert penalty == 0.75


def test_apply_skill_rust_reduces_skills():
    """Test that skill rust reduces skill values over time."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 50.0
    state.player.skills_detailed["cooking"].last_tick = 0
    state.player.skills_detailed["cooking"].rust_rate = 0.1
    state.player.traits.discipline = 0  # No discipline modifier

    current_tick = 10
    _apply_skill_rust(state, current_tick)

    # Skill should have rusted: 50 - (0.1 * 10) = 49.0
    assert state.player.skills_detailed["cooking"].value < 50.0
    assert state.player.skills_detailed["cooking"].last_tick == current_tick


def test_apply_skill_rust_discipline_reduces_rust():
    """Test that high discipline reduces skill rust."""
    state = new_game()

    # Two identical setups, one with high discipline
    state1 = new_game()
    state1.player.skills_detailed["cooking"].value = 50.0
    state1.player.skills_detailed["cooking"].last_tick = 0
    state1.player.skills_detailed["cooking"].rust_rate = 0.1
    state1.player.traits.discipline = 0

    state2 = new_game()
    state2.player.skills_detailed["cooking"].value = 50.0
    state2.player.skills_detailed["cooking"].last_tick = 0
    state2.player.skills_detailed["cooking"].rust_rate = 0.1
    state2.player.traits.discipline = 90  # High discipline

    current_tick = 10
    _apply_skill_rust(state1, current_tick)
    _apply_skill_rust(state2, current_tick)

    # State2 with high discipline should have less rust
    assert state2.player.skills_detailed["cooking"].value > state1.player.skills_detailed["cooking"].value


def test_apply_skill_rust_cannot_go_negative():
    """Test that skill values cannot go below 0."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 1.0
    state.player.skills_detailed["cooking"].last_tick = 0
    state.player.skills_detailed["cooking"].rust_rate = 1.0
    state.player.traits.discipline = 0

    current_tick = 100
    _apply_skill_rust(state, current_tick)

    assert state.player.skills_detailed["cooking"].value == 0.0


def test_gain_skill_xp_increases_skill():
    """Test that gaining XP increases skill value."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 20.0
    state.player.traits.curiosity = 0
    state.player.needs.illness = 0
    state.player.needs.injury = 0

    gained = _gain_skill_xp(state, "cooking", 10.0, current_tick=1)

    assert state.player.skills_detailed["cooking"].value == 30.0
    assert gained == 10.0


def test_gain_skill_xp_curiosity_bonus():
    """Test that high curiosity increases XP gain."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 20.0
    state.player.traits.curiosity = 100  # Max curiosity
    state.player.needs.illness = 0
    state.player.needs.injury = 0

    gained = _gain_skill_xp(state, "cooking", 10.0, current_tick=1)

    # With 100 curiosity, modifier is 1.0 + (100 / 100) * 0.3 = 1.3
    expected = 10.0 * 1.3
    assert abs(state.player.skills_detailed["cooking"].value - (20.0 + expected)) < 0.01
    assert abs(gained - expected) < 0.01


def test_gain_skill_xp_health_penalty():
    """Test that low health reduces XP gain."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 20.0
    state.player.traits.curiosity = 0
    state.player.needs.illness = 100
    state.player.needs.injury = 100  # Very low health

    gained = _gain_skill_xp(state, "cooking", 10.0, current_tick=1)

    # With zero health, penalty is 0.5
    expected = 10.0 * 0.5
    assert abs(gained - expected) < 0.01


def test_gain_skill_xp_increases_aptitude():
    """Test that skill XP gain also increases aptitude."""
    state = new_game()
    initial_aptitude = state.player.aptitudes.body
    state.player.skills_detailed["cooking"].value = 20.0
    state.player.traits.curiosity = 0
    state.player.needs.illness = 0
    state.player.needs.injury = 0

    _gain_skill_xp(state, "cooking", 100.0, current_tick=1)

    # Aptitude should have increased: 100 * 0.002 = 0.2
    expected_aptitude = initial_aptitude + (100.0 * 0.002)
    assert abs(state.player.aptitudes.body - expected_aptitude) < 0.01


def test_apply_trait_drift_increases_traits():
    """Test that habit accumulation increases traits."""
    state = new_game()
    state.player.traits.confidence = 50
    state.player.habit_tracker["confidence"] = 200  # Above threshold

    messages = _apply_trait_drift(state)

    assert state.player.traits.confidence == 51
    assert len(messages) > 0
    assert state.player.habit_tracker["confidence"] == 0  # Reset after drift


def test_apply_trait_drift_no_change_below_threshold():
    """Test that traits don't change below threshold."""
    state = new_game()
    state.player.traits.confidence = 50
    state.player.habit_tracker["confidence"] = 50  # Below threshold

    messages = _apply_trait_drift(state)

    assert state.player.traits.confidence == 50
    assert len(messages) == 0
    assert state.player.habit_tracker["confidence"] == 50


def test_apply_trait_drift_cannot_exceed_100():
    """Test that traits cannot exceed 100."""
    state = new_game()
    state.player.traits.confidence = 100
    state.player.habit_tracker["confidence"] = 200

    _apply_trait_drift(state)

    assert state.player.traits.confidence == 100


def test_calculate_current_tick():
    """Test tick calculation from day and time slice."""
    state = new_game()

    # Day 0, morning (slice 0)
    state.world.day = 0
    state.world.slice = "morning"
    assert _calculate_current_tick(state) == 0

    # Day 0, afternoon (slice 1)
    state.world.slice = "afternoon"
    assert _calculate_current_tick(state) == 1

    # Day 0, evening (slice 2)
    state.world.slice = "evening"
    assert _calculate_current_tick(state) == 2

    # Day 0, night (slice 3)
    state.world.slice = "night"
    assert _calculate_current_tick(state) == 3

    # Day 1, morning (slice 0)
    state.world.day = 1
    state.world.slice = "morning"
    assert _calculate_current_tick(state) == 4

    # Day 2, evening (slice 2)
    state.world.day = 2
    state.world.slice = "evening"
    assert _calculate_current_tick(state) == 10


def test_check_job_requirements_no_requirements():
    """Test job with no requirements is always available."""
    from roomlife.constants import JOBS

    state = new_game()

    # Recycling collector has no requirements
    meets, reason = _check_job_requirements(state, "recycling_collector")
    assert meets is True
    assert reason == ""


def test_check_job_requirements_skill_requirement_met():
    """Test job with skill requirement when requirement is met."""
    state = new_game()
    state.player.skills_detailed["bartending"].value = 30.0

    meets, reason = _check_job_requirements(state, "bartender")
    assert meets is True
    assert reason == ""


def test_check_job_requirements_skill_requirement_not_met():
    """Test job with skill requirement when requirement is not met."""
    state = new_game()
    state.player.skills_detailed["bartending"].value = 5.0  # Below requirement

    meets, reason = _check_job_requirements(state, "bartender")
    assert meets is False
    assert "insufficient" in reason


def test_check_job_requirements_trait_requirement():
    """Test job with trait requirement."""
    state = new_game()
    state.player.traits.charisma = 60  # Set high charisma
    state.player.skills_detailed["bartending"].value = 30.0

    meets, reason = _check_job_requirements(state, "bartender")
    assert meets is True


def test_check_job_requirements_invalid_job():
    """Test checking requirements for invalid job."""
    state = new_game()

    meets, reason = _check_job_requirements(state, "nonexistent_job")
    assert meets is False
    assert reason == "job_not_found"


def test_get_item_effectiveness_pristine():
    """Test item effectiveness for pristine items."""
    item = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=95,
        bulk=1
    )

    effectiveness = _get_item_effectiveness(item)
    # Pristine (>= 90) gets 1.1 * 1.0 = 1.1
    assert effectiveness == 1.1


def test_get_item_effectiveness_used():
    """Test item effectiveness for used items."""
    item = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="used",
        condition_value=75,
        bulk=1
    )

    effectiveness = _get_item_effectiveness(item)
    # Used (70-89) gets 1.0 * 1.0 = 1.0
    assert effectiveness == 1.0


def test_get_item_effectiveness_worn():
    """Test item effectiveness for worn items."""
    item = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="worn",
        condition_value=50,
        bulk=1
    )

    effectiveness = _get_item_effectiveness(item)
    # Worn (40-69) gets 0.8 * 1.0 = 0.8
    assert effectiveness == 0.8


def test_get_item_effectiveness_broken():
    """Test item effectiveness for broken items."""
    item = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="broken",
        condition_value=25,
        bulk=1
    )

    effectiveness = _get_item_effectiveness(item)
    # Broken (20-39) gets 0.5 * 1.0 = 0.5
    assert effectiveness == 0.5


def test_get_item_effectiveness_filthy():
    """Test item effectiveness for filthy items."""
    item = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="filthy",
        condition_value=10,
        bulk=1
    )

    effectiveness = _get_item_effectiveness(item)
    # Filthy (< 20) gets 0.3 * 1.0 = 0.3
    assert effectiveness == 0.3


def test_get_item_effectiveness_with_quality():
    """Test that item quality affects effectiveness."""
    item_premium = Item(
        instance_id="test_001",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.5,  # Premium quality
        condition="pristine",
        condition_value=95,
        bulk=1
    )

    item_standard = Item(
        instance_id="test_002",
        item_id="computer",
        placed_in="room_001",
        container=None,
        slot="floor",
        quality=1.0,  # Standard quality
        condition="pristine",
        condition_value=95,
        bulk=1
    )

    effectiveness_premium = _get_item_effectiveness(item_premium)
    effectiveness_standard = _get_item_effectiveness(item_standard)

    # Premium should be more effective
    assert effectiveness_premium > effectiveness_standard
    # Premium: 1.1 * 1.5 = 1.65
    assert abs(effectiveness_premium - 1.65) < 0.01
    # Standard: 1.1 * 1.0 = 1.1
    assert abs(effectiveness_standard - 1.1) < 0.01


def test_new_game_deterministic_with_seed():
    """Test that new_game with same seed produces identical states."""
    state1 = new_game(seed=42)
    state2 = new_game(seed=42)

    # Check that item instance IDs are the same
    for i in range(len(state1.items)):
        assert state1.items[i].instance_id == state2.items[i].instance_id


def test_new_game_different_seeds_produce_different_states():
    """Test that new_game with different seeds produces different states."""
    state1 = new_game(seed=42)
    state2 = new_game(seed=99)

    # Check that at least some item instance IDs are different
    different_ids = False
    for i in range(min(len(state1.items), len(state2.items))):
        if state1.items[i].instance_id != state2.items[i].instance_id:
            different_ids = True
            break

    assert different_ids
