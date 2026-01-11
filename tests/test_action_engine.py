from dataclasses import asdict
from pathlib import Path

from roomlife import engine
from roomlife.content_specs import load_actions
from roomlife.engine import apply_action, new_game


def _snapshot_state(state):
    return {
        "world": (state.world.day, state.world.slice, state.world.location),
        "player": {
            "money_pence": state.player.money_pence,
            "utilities_paid": state.player.utilities_paid,
            "needs": asdict(state.player.needs),
            "traits": asdict(state.player.traits),
            "aptitudes": asdict(state.player.aptitudes),
            "skills": {
                name: (skill.value, skill.last_tick)
                for name, skill in state.player.skills_detailed.items()
            },
            "habits": dict(state.player.habit_tracker),
        },
        "items": [
            (
                it.instance_id,
                it.item_id,
                it.placed_in,
                it.slot,
                it.condition_value,
                it.quality,
                it.bulk,
            )
            for it in sorted(state.items, key=lambda item: item.instance_id)
        ],
        "event_log": list(state.event_log),
    }


def _prepare_state_for_spec(state, spec):
    if spec.id == "drop_item" and state.items:
        state.items[0].placed_in = "inventory"
        state.items[0].slot = "inventory"


def _build_params(state, spec):
    params = {}
    for param in spec.parameters or []:
        name = param.get("name")
        ptype = param.get("type")
        constraints = param.get("constraints", {})
        if ptype == "space_id":
            current = state.world.location
            space = state.spaces.get(current)
            if space and space.connections:
                params[name] = space.connections[0]
            else:
                params[name] = current
        elif ptype == "item_ref":
            if constraints.get("in_inventory"):
                candidate = next(
                    (it for it in state.items if it.placed_in == "inventory"),
                    None,
                )
            else:
                candidate = next(
                    (it for it in state.items if it.placed_in in (state.world.location, "inventory")),
                    None,
                )
            if candidate:
                params[name] = {"mode": "by_item_id", "item_id": candidate.item_id}
        else:
            candidate = next(
                (it for it in state.items if it.placed_in == state.world.location),
                None,
            )
            if candidate and name:
                params[name] = candidate.item_id
    if spec.id == "repair_item" and state.items:
        candidate = next(
            (it for it in state.items if it.placed_in in (state.world.location, "inventory")),
            None,
        )
        if candidate:
            params.setdefault(
                "item_ref",
                {"mode": "by_item_id", "item_id": candidate.item_id},
            )
    return params


def test_action_engine_loads_all_specs():
    repo_root = Path(__file__).resolve().parents[1]
    action_specs = load_actions(repo_root / "data" / "actions.yaml")

    engine._ensure_specs_loaded()

    assert engine._ACTION_SPECS is not None
    assert set(engine._ACTION_SPECS.keys()) == set(action_specs.keys())


def test_each_action_has_deterministic_outcome_with_seed():
    engine._ensure_specs_loaded()
    assert engine._ACTION_SPECS is not None

    for spec in engine._ACTION_SPECS.values():
        s1 = new_game()
        s2 = new_game()
        _prepare_state_for_spec(s1, spec)
        _prepare_state_for_spec(s2, spec)
        params1 = _build_params(s1, spec)
        params2 = _build_params(s2, spec)
        apply_action(s1, spec.id, rng_seed=42, params=params1)
        apply_action(s2, spec.id, rng_seed=42, params=params2)
        assert _snapshot_state(s1) == _snapshot_state(s2)
