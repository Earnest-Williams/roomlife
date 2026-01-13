from pathlib import Path

from roomlife import engine
from roomlife.content_specs import load_actions
from roomlife.engine import new_game


def test_action_engine_loads_all_specs():
    repo_root = Path(__file__).resolve().parents[1]
    action_specs = load_actions(repo_root / "data" / "actions.yaml")

    engine._ensure_specs_loaded()

    assert engine._ACTION_SPECS is not None
    assert set(engine._ACTION_SPECS.keys()) == set(action_specs.keys())


def test_consume_error_raised_when_money_insufficient():
    """Test that ConsumeError is raised when consuming money but funds are insufficient."""
    import pytest
    from roomlife.action_engine import apply_consumes, ConsumeError
    from roomlife.content_specs import ActionSpec

    state = new_game(seed=42)
    state.player.money_pence = 100

    spec = ActionSpec(
        id="test_action",
        display_name="Test",
        description="Test",
        category="test",
        time_minutes=10,
        requires={},
        modifiers={},
        outcomes={1: {}},
        consumes={"money_pence": 200},
    )

    with pytest.raises(ConsumeError, match="Insufficient funds"):
        apply_consumes(state, spec, engine._ITEM_META or {})


def test_consume_error_raised_when_required_durability_provider_missing():
    """Test that ConsumeError is raised when consuming durability from a required capability."""
    import pytest
    from roomlife.action_engine import apply_consumes, ConsumeError
    from roomlife.content_specs import ActionSpec

    state = new_game(seed=42)

    # Action requires and consumes heat_source
    spec = ActionSpec(
        id="test_action",
        display_name="Test",
        description="Test",
        category="test",
        time_minutes=10,
        requires={"items": {"any_provides": ["heat_source"]}},
        modifiers={},
        outcomes={1: {}},
        consumes={"item_durability": {"provides": "heat_source", "amount": 5}},
    )

    # No heat_source item exists
    with pytest.raises(ConsumeError, match="Durability consume missing provider 'heat_source'"):
        apply_consumes(state, spec, engine._ITEM_META or {})


def test_missing_tier_outcome_raises_error():
    """Test that apply_outcome raises KeyError when tier is not defined."""
    import pytest
    from roomlife.action_engine import apply_outcome
    from roomlife.content_specs import ActionSpec

    state = new_game(seed=42)

    spec = ActionSpec(
        id="test_action",
        display_name="Test",
        description="Test",
        category="test",
        time_minutes=10,
        requires={},
        modifiers={},
        outcomes={1: {}, 2: {}, 3: {}},  # No tier 0
    )

    with pytest.raises(KeyError, match="does not define outcome for tier 0"):
        apply_outcome(state, spec, tier=0, item_meta={}, current_tick=0)


def test_tier_floor_clamps_computed_tier():
    """Test that tier_floor properly clamps computed tier values."""
    from roomlife.action_engine import clamp_tier
    from roomlife.content_specs import ActionSpec

    # Default tier_floor is 1
    spec_default = ActionSpec(
        id="test",
        display_name="Test",
        description="Test",
        category="test",
        time_minutes=10,
        requires={},
        modifiers={},
        outcomes={},
    )
    assert clamp_tier(spec_default, 0) == 1
    assert clamp_tier(spec_default, 1) == 1
    assert clamp_tier(spec_default, 2) == 2

    # Explicit tier_floor of 0 allows tier 0
    spec_zero = ActionSpec(
        id="test",
        display_name="Test",
        description="Test",
        category="test",
        time_minutes=10,
        requires={},
        modifiers={"tier_floor": 0},
        outcomes={},
    )
    assert clamp_tier(spec_zero, 0) == 0
    assert clamp_tier(spec_zero, 1) == 1
