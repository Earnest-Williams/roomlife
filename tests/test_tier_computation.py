"""Tests for tier computation and related functions in action_engine.py."""

from roomlife.action_engine import (
    compute_tier,
    preview_tier_distribution,
    preview_delta_ranges,
    build_preview_notes,
    degrade_item_condition,
    update_item_condition,
)
from roomlife.content_specs import ActionSpec, ItemMeta
from roomlife.engine import new_game
from roomlife.models import Item, generate_instance_id


def test_compute_tier_with_high_skill():
    """Test that high skill values produce higher tiers."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 90.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier = compute_tier(state, spec, {}, rng_seed=42)
    # With cooking skill at 90, should get tier 2 or 3
    assert tier >= 2


def test_compute_tier_with_low_skill():
    """Test that low skill values produce lower tiers."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 10.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier = compute_tier(state, spec, {}, rng_seed=42)
    # With cooking skill at 10, should get tier 0 or 1
    assert tier <= 1


def test_compute_tier_with_secondary_skills():
    """Test that secondary skills contribute to tier."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 30.0
    state.player.skills_detailed["creativity"].value = 40.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "secondary_skills": {"creativity": 0.5}
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    # With secondary skill, tier should be higher than without
    tier_with_secondary = compute_tier(state, spec, {}, rng_seed=42)

    # Compare to spec without secondary skill
    spec_no_secondary = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier_without_secondary = compute_tier(state, spec_no_secondary, {}, rng_seed=42)
    assert tier_with_secondary >= tier_without_secondary


def test_compute_tier_with_traits():
    """Test that traits influence tier computation."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 40.0
    state.player.traits.creativity = 80  # High creativity trait

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "traits": {"creativity": 0.3}
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier = compute_tier(state, spec, {}, rng_seed=42)
    # High trait should improve tier
    assert tier >= 1


def test_compute_tier_with_item_provides():
    """Test that items providing capabilities improve tier."""
    state = new_game()
    state.world.location = "kitchen_001"
    state.player.skills_detailed["cooking"].value = 30.0

    # Add a high-quality stove
    state.items.append(Item(
        instance_id="stove_001",
        item_id="stove",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.5,
        condition="pristine",
        condition_value=100,
        bulk=1
    ))

    item_meta = {
        "stove": ItemMeta(
            id="stove",
            name="Stove",
            tags=["heat_source"],
            provides=["heat_source"],
            requires_utilities=["power"],
            durability={"max": 100, "degrade_per_use_default": 1}
        )
    }

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "item_provides_weights": {"heat_source": 0.5}
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier_with_item = compute_tier(state, spec, item_meta, rng_seed=42)
    tier_without_item = compute_tier(state, spec, {}, rng_seed=42)

    # Having the item should improve tier
    assert tier_with_item >= tier_without_item


def test_compute_tier_respects_tier_floor():
    """Test that tier floor prevents failures even with low skill."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 0.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "tier_floor": 2  # Cannot fail below tier 2
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier = compute_tier(state, spec, {}, rng_seed=42)
    # Even with 0 skill, tier should be at least 2
    assert tier >= 2


def test_compute_tier_deterministic_with_same_seed():
    """Test that tier computation is deterministic for same seed."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 50.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier1 = compute_tier(state, spec, {}, rng_seed=42)
    tier2 = compute_tier(state, spec, {}, rng_seed=42)
    assert tier1 == tier2


def test_compute_tier_varies_with_different_seed():
    """Test that tier computation varies with different seeds (RNG component)."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 50.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    # Run multiple times with different seeds
    tiers = [compute_tier(state, spec, {}, rng_seed=i) for i in range(10)]

    # There should be some variation due to RNG
    # (though with skill at 50, tiers should be in 1-2 range mostly)
    assert len(set(tiers)) > 1  # Not all the same


def test_preview_tier_distribution():
    """Test that tier distribution preview works."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 50.0

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={"primary_skill": "cooking"},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    distribution = preview_tier_distribution(state, spec, {}, rng_seed=42, samples=9)

    # Distribution should have all tier keys
    assert 0 in distribution
    assert 1 in distribution
    assert 2 in distribution
    assert 3 in distribution

    # Probabilities should sum to 1.0
    assert abs(sum(distribution.values()) - 1.0) < 0.01


def test_preview_delta_ranges():
    """Test that delta ranges are extracted correctly."""
    spec = ActionSpec(
        id="test_action",
        display_name="Test",
        description="Test action",
        category="other",
        time_minutes=30,
        requires={},
        modifiers={},
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5, "fatigue": 10}}},
            1: {"deltas": {"needs": {"hunger": -10, "fatigue": 5}}},
            2: {"deltas": {"needs": {"hunger": -15, "fatigue": 0}}},
            3: {"deltas": {"needs": {"hunger": -20, "fatigue": -5}}},
        }
    )

    ranges = preview_delta_ranges(spec)

    assert "needs" in ranges
    assert "hunger" in ranges["needs"]
    assert ranges["needs"]["hunger"]["min"] == -20
    assert ranges["needs"]["hunger"]["max"] == -5
    assert "fatigue" in ranges["needs"]
    assert ranges["needs"]["fatigue"]["min"] == -5
    assert ranges["needs"]["fatigue"]["max"] == 10


def test_build_preview_notes():
    """Test that preview notes are generated."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 42.5

    spec = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "item_provides_weights": {"heat_source": 0.5}
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    class MockActionCall:
        params = {}

    notes = build_preview_notes(state, spec, {}, MockActionCall())

    # Should mention primary skill
    assert any("Primary skill" in note and "cooking" in note for note in notes)

    # Should mention missing item
    assert any("heat_source" in note for note in notes)


def test_degrade_item_condition_normal():
    """Test normal item condition degradation."""
    item = Item(
        instance_id="test_001",
        item_id="stove",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )

    degrade_item_condition(item, base_degradation=5)

    assert item.condition_value == 95
    assert item.condition == "pristine"


def test_degrade_item_condition_accelerated_when_poor():
    """Test that poor condition items degrade faster."""
    item = Item(
        instance_id="test_001",
        item_id="stove",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="worn",
        condition_value=35,  # Below 40 threshold
        bulk=1
    )

    degrade_item_condition(item, base_degradation=5)

    # Should degrade by 5 * 1.5 = 7-8 points (rounded)
    assert item.condition_value <= 28


def test_degrade_item_condition_cannot_go_negative():
    """Test that condition value doesn't go below 0."""
    item = Item(
        instance_id="test_001",
        item_id="stove",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="filthy",
        condition_value=2,
        bulk=1
    )

    degrade_item_condition(item, base_degradation=10)

    assert item.condition_value == 0


def test_update_item_condition_categories():
    """Test that condition string is updated correctly."""
    item = Item(
        instance_id="test_001",
        item_id="stove",
        placed_in="kitchen_001",
        container=None,
        slot="floor",
        quality=1.0,
        condition="pristine",
        condition_value=100,
        bulk=1
    )

    # Test pristine (90-100)
    item.condition_value = 95
    update_item_condition(item)
    assert item.condition == "pristine"

    # Test used (70-89)
    item.condition_value = 80
    update_item_condition(item)
    assert item.condition == "used"

    # Test worn (40-69)
    item.condition_value = 50
    update_item_condition(item)
    assert item.condition == "worn"

    # Test broken (20-39)
    item.condition_value = 30
    update_item_condition(item)
    assert item.condition == "broken"

    # Test filthy (0-19)
    item.condition_value = 10
    update_item_condition(item)
    assert item.condition == "filthy"


def test_compute_tier_with_aptitude_weight():
    """Test that aptitude_weight modifier affects tier computation."""
    state = new_game()
    state.player.skills_detailed["cooking"].value = 50.0
    state.player.aptitudes.body = 1.5  # High body aptitude

    # Spec with full aptitude weight
    spec_with_apt = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "aptitude_weight": 1.0
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    # Spec without aptitude weight
    spec_no_apt = ActionSpec(
        id="test_cook",
        display_name="Cook",
        description="Test cooking",
        category="survival",
        time_minutes=30,
        requires={},
        modifiers={
            "primary_skill": "cooking",
            "aptitude_weight": 0.0
        },
        outcomes={
            0: {"deltas": {"needs": {"hunger": -5}}},
            1: {"deltas": {"needs": {"hunger": -10}}},
            2: {"deltas": {"needs": {"hunger": -15}}},
            3: {"deltas": {"needs": {"hunger": -20}}},
        }
    )

    tier_with_apt = compute_tier(state, spec_with_apt, {}, rng_seed=42)
    tier_no_apt = compute_tier(state, spec_no_apt, {}, rng_seed=42)

    # With higher aptitude, tier should be higher
    assert tier_with_apt >= tier_no_apt
