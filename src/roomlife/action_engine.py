"""Data-driven action execution engine.

This module provides the core logic for validating, computing tiers, and applying
outcomes for actions defined in YAML specifications.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import random

from .models import State, Item, generate_instance_id
from .content_specs import ActionSpec, ItemMeta
from .constants import MAX_EVENT_LOG, SKILL_TO_APTITUDE
from .param_resolver import select_item_instance, validate_connected_to_param, validate_parameters


def _log(state: State, event_id: str, **params: Any) -> None:
    """Log an event to the state's event log.

    Args:
        state: Game state
        event_id: Event identifier
        **params: Event parameters
    """
    state.event_log.append({"event_id": event_id, "params": params})
    if len(state.event_log) > MAX_EVENT_LOG:
        del state.event_log[:-MAX_EVENT_LOG]


def _clamp100(x: int) -> int:
    """Clamp a value to 0-100 range.

    Args:
        x: Value to clamp

    Returns:
        Clamped value between 0 and 100
    """
    return max(0, min(100, x))


def _get_skill_value(state: State, skill_name: str) -> float:
    """Get the current value of a skill.

    Args:
        state: Game state
        skill_name: Name of the skill

    Returns:
        Current skill value, or 0.0 if skill doesn't exist
    """
    skill = state.player.skills_detailed.get(skill_name)
    return skill.value if skill else 0.0


def _get_health_penalty(state: State) -> float:
    """Calculate health penalty multiplier for actions.

    Args:
        state: Game state

    Returns:
        Multiplier between 0.5 and 1.0 based on health
    """
    health = state.player.needs.health
    if health < 50:
        return 0.5 + (health / 100.0)
    return 1.0


def _apply_skill_xp(state: State, skill_name: str, xp_gain: float, current_tick: int) -> float:
    """Apply skill XP gain with trait modifiers.

    Args:
        state: Game state
        skill_name: Name of the skill
        xp_gain: Base XP gain
        current_tick: Current game tick

    Returns:
        Actual XP gained after modifiers
    """
    skill = state.player.skills_detailed.get(skill_name)
    if skill is None:
        return 0.0

    # Apply modifiers (curiosity trait and health penalty)
    curiosity_mod = 1.0 + (state.player.traits.curiosity / 100.0) * 0.3
    health_penalty = _get_health_penalty(state)
    actual_gain = xp_gain * curiosity_mod * health_penalty

    # Update skill
    skill.value += actual_gain
    skill.last_tick = current_tick

    # Update aptitude
    aptitude_name = SKILL_TO_APTITUDE[skill_name]
    aptitude = getattr(state.player.aptitudes, aptitude_name)
    aptitude_gain = actual_gain * 0.002
    new_aptitude = aptitude + aptitude_gain
    setattr(state.player.aptitudes, aptitude_name, new_aptitude)

    return actual_gain


def _find_best_item_for_provides(
    state: State,
    item_meta: Dict[str, ItemMeta],
    provides: str,
    location: str,
) -> Optional[Item]:
    """Find the best item that provides a given capability.

    Prefers items with higher condition and quality.

    Args:
        state: Game state
        item_meta: Item metadata registry
        provides: Capability to search for (e.g., "heat_source")
        location: Location to search in

    Returns:
        Best matching item, or None if no match found
    """
    best: Optional[Item] = None
    best_score = -1.0

    candidates = [
        it for it in state.items
        if it.placed_in == location or it.placed_in == "inventory"
    ]
    for it in candidates:
        meta = item_meta.get(it.item_id)
        if not meta:
            continue
        if provides not in meta.provides:
            continue

        # Score by condition and quality
        score = float(getattr(it, "condition_value", 100)) + float(getattr(it, "quality", 1.0)) * 10.0
        if score > best_score:
            best = it
            best_score = score

    return best


def validate_action_spec(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
    params: Dict[str, Any] | None = None,
) -> Tuple[bool, str, List[str]]:
    """Validate if an action can be executed.

    Args:
        state: Current game state
        spec: Action specification
        item_meta: Item metadata registry

    Returns:
        Tuple of (is_valid, reason, missing_requirements)
    """
    missing: List[str] = []
    req = spec.requires or {}
    params = params or {}

    # Money requirement
    money_req = req.get("money_pence")
    if money_req is not None and state.player.money_pence < int(money_req):
        missing.append(f"need {money_req}p (have {state.player.money_pence}p)")

    # Utilities (all_true)
    utils = req.get("utilities", {}).get("all_true", [])
    for u in utils:
        if not getattr(state.utilities, u, False):
            missing.append(f"utility {u}=on")

    # Location requirements
    loc_req = req.get("location", {})
    space = state.spaces.get(state.world.location)
    if space is None:
        missing.append("valid location")
    else:
        # Check space tags
        any_tags = loc_req.get("any_space_tags")
        if any_tags:
            space_tags = getattr(space, "tags", [])
            if not any(t in space_tags for t in any_tags):
                missing.append(f"space tag any_of={any_tags}")

        # Check fixture requirement
        fixture = loc_req.get("requires_fixture")
        if fixture:
            fixtures = getattr(space, "fixtures", [])
            if fixture not in fixtures:
                missing.append(f"fixture {fixture}")

    # Custom param-linked requirements
    if "connected_to_param" in loc_req:
        ok, msg = validate_connected_to_param(state, loc_req["connected_to_param"], params)
        if not ok:
            missing.append(msg)

    # Item requirements
    item_req = req.get("items", {})

    # any_provides: at least one item with any of these capabilities
    any_provides = item_req.get("any_provides", [])
    if any_provides:
        ok = False
        for prov in any_provides:
            if _find_best_item_for_provides(state, item_meta, prov, state.world.location) is not None:
                ok = True
                break
        if not ok:
            missing.append(f"item provides any_of={any_provides}")

    # all_provides: item(s) with all of these capabilities
    all_provides = item_req.get("all_provides", [])
    for prov in all_provides:
        if _find_best_item_for_provides(state, item_meta, prov, state.world.location) is None:
            missing.append(f"item provides {prov}")

    # has_item_ids: specific items must be present
    has_item_ids = item_req.get("has_item_ids", [])
    if has_item_ids:
        owned = {
            it.item_id
            for it in state.items
            if it.placed_in in (state.world.location, "inventory")
        }
        for iid in has_item_ids:
            if iid not in owned:
                missing.append(f"need item {iid}")

    # Skill minimums
    skills_min = req.get("skills_min", {})
    for skill, minv in skills_min.items():
        if _get_skill_value(state, skill) < float(minv):
            missing.append(f"skill {skill}>={minv}")

    params_ok, params_missing = validate_parameters(state, spec, params)
    if not params_ok:
        missing.extend(params_missing)

    if spec.id == "repair_item":
        item_ref = params.get("item_ref")
        item = select_item_instance(state, item_ref) if isinstance(item_ref, dict) else None
        if item is None:
            missing.append("repair item not found")
        elif item.condition_value >= 90:
            missing.append("item already pristine")
        else:
            cost = compute_repair_cost(state, spec, item)
            if state.player.money_pence < cost:
                missing.append(f"need {cost}p (have {state.player.money_pence}p)")

    if missing:
        return False, "Missing requirements", missing

    return True, "", []


def compute_tier(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
    rng_seed: int,
) -> int:
    """Compute the outcome tier for an action.

    Combines primary skill, secondary skills, traits, item effectiveness,
    and a small RNG component to determine tier (0-3).

    Args:
        state: Current game state
        spec: Action specification
        item_meta: Item metadata registry
        rng_seed: Random seed for deterministic outcomes

    Returns:
        Tier from 0 (fail/partial) to 3 (great)
    """
    mods = spec.modifiers or {}
    primary = mods.get("primary_skill")
    base = _get_skill_value(state, primary) if primary else 0.0

    # Add weighted secondary skills
    for s, w in (mods.get("secondary_skills") or {}).items():
        base += _get_skill_value(state, s) * float(w)

    # Add weighted traits (0-100 scale)
    for t, w in (mods.get("traits") or {}).items():
        trait_val = getattr(state.player.traits, t, 0) / 100.0
        base += trait_val * 100.0 * float(w)

    # Add item provides contribution
    weights = mods.get("item_provides_weights") or {}
    item_bonus = 0.0
    for prov, w in weights.items():
        it = _find_best_item_for_provides(state, item_meta, prov, state.world.location)
        if it is None:
            continue
        cond = float(getattr(it, "condition_value", 100)) / 100.0
        qual = float(getattr(it, "quality", 1.0))
        item_bonus += (cond * 70.0 + qual * 10.0) * float(w)
    base += item_bonus

    # Small RNG component (seeded): ± up to ~8 points
    rng = random.Random(rng_seed + state.world.day * 97)
    base += (rng.random() - 0.5) * 16.0

    # Map score to tier thresholds
    if base < 25:
        return 0
    if base < 55:
        return 1
    if base < 85:
        return 2
    return 3


def apply_outcome(
    state: State,
    spec: ActionSpec,
    tier: int,
    item_meta: Dict[str, ItemMeta],
    current_tick: int,
    emit_events: bool = True,
) -> None:
    """Apply the outcome effects for a given tier.

    Args:
        state: Game state to modify
        spec: Action specification
        tier: Outcome tier (0-3)
        item_meta: Item metadata registry
        current_tick: Current game tick for skill rust tracking
    """
    outcome = spec.outcomes.get(tier) or spec.outcomes.get(1) or {}
    deltas = outcome.get("deltas", {})

    # Apply needs changes
    needs = deltas.get("needs", {})
    for k, v in needs.items():
        current = getattr(state.player.needs, k)
        setattr(state.player.needs, k, _clamp100(int(current + int(v))))

    # Apply money changes
    money_delta = deltas.get("money_pence")
    if money_delta is not None:
        state.player.money_pence += int(money_delta)

    # Skill XP gains
    skills_xp = deltas.get("skills_xp", {})
    if skills_xp:
        for s, xp in skills_xp.items():
            actual_gain = _apply_skill_xp(state, s, float(xp), current_tick)
            _log(state, "skill.gain", skill=s, xp=round(actual_gain, 2))

    # Flags (stored in player.habit_tracker for now, or new flags dict)
    flags = deltas.get("flags", {})
    if flags:
        # Create flags storage if it doesn't exist
        if not hasattr(state.player, "flags"):
            state.player.flags = {}  # type: ignore
        store = state.player.flags  # type: ignore
        for k, v in flags.items():
            store[k] = int(store.get(k, 0)) + int(v)

    # Grant items
    grants = outcome.get("grants", {})
    for it in grants.get("items", []) if grants else []:
        item_id = it["item_id"]
        qty = int(it.get("quantity", 1))
        placed_in = it.get("placed_in", state.world.location)

        for _ in range(qty):
            state.items.append(Item(
                instance_id=generate_instance_id(),
                item_id=item_id,
                placed_in=("inventory" if placed_in == "inventory" else placed_in),
                container=None,
                slot="floor",
                quality=1.0,
                condition="pristine",
                condition_value=100,
                bulk=1,
            ))

    # Emit events
    if emit_events:
        for e in outcome.get("events", []):
            _log(state, e["id"], **(e.get("params", {})))


def preview_tier_distribution(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
    rng_seed: int,
    samples: int = 9,
) -> Dict[int, float]:
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for i in range(samples):
        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed + i * 1000)
        counts[tier] += 1
    return {k: v / samples for k, v in counts.items()}


def preview_delta_ranges(spec: ActionSpec) -> Dict[str, Any]:
    needs_keys = set()
    for _, out in spec.outcomes.items():
        needs_keys |= set((out.get("deltas", {}).get("needs", {}) or {}).keys())

    ranges: Dict[str, Any] = {"needs": {}}
    for k in needs_keys:
        vals = []
        for _, out in spec.outcomes.items():
            needs = (out.get("deltas", {}).get("needs", {}) or {})
            if k in needs:
                vals.append(int(needs[k]))
        if vals:
            ranges["needs"][k] = {"min": min(vals), "max": max(vals)}
    return ranges


def build_preview_notes(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
    action_call: Any,
) -> List[str]:
    notes = []
    primary = (spec.modifiers or {}).get("primary_skill")
    if primary:
        notes.append(f"Primary skill: {primary} ({_get_skill_value(state, primary):.1f})")
    weights = (spec.modifiers or {}).get("item_provides_weights") or {}
    for prov in weights:
        if _find_best_item_for_provides(state, item_meta, prov, state.world.location) is None:
            notes.append(f"Optional improvement: item providing '{prov}'")
    if spec.parameters:
        for p in spec.parameters:
            if p.get("required") and p["name"] not in action_call.params:
                notes.append(f"Missing parameter: {p['name']}")
    return notes


def apply_consumes(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
) -> None:
    """Apply resource consumption for an action.

    Args:
        state: Game state to modify
        spec: Action specification
        item_meta: Item metadata registry
    """
    cons = spec.consumes or {}

    # Money consumption
    if "money_pence" in cons:
        state.player.money_pence -= int(cons["money_pence"])

    # Inventory consumption
    inv_cons = cons.get("inventory_items", [])
    if inv_cons:
        for item_cons in inv_cons:
            item_id = item_cons["item_id"]
            quantity = int(item_cons.get("quantity", 1))

            # Remove items from state.items
            removed = 0
            for _ in range(quantity):
                # Find and remove one instance of the item (prefer inventory, then current location)
                for item in state.items:
                    if item.item_id == item_id and (
                        item.placed_in == "inventory" or
                        item.placed_in == state.world.location
                    ):
                        state.items.remove(item)
                        removed += 1
                        break

            # Log consumption
            _log(state, "item.consumed", item_id=item_id, quantity=removed)

    # Item durability degradation
    dur = cons.get("item_durability")
    if dur:
        prov = dur.get("provides")
        amt = int(dur.get("amount", 1))
        it = _find_best_item_for_provides(state, item_meta, prov, state.world.location)
        if it is not None:
            it.condition_value = max(0, int(getattr(it, "condition_value", 100)) - amt)

            # Update condition string based on condition_value
            if it.condition_value <= 0:
                it.condition = "broken"
            elif it.condition_value < 35:
                it.condition = "worn"
            elif it.condition_value < 70:
                it.condition = "used"
            else:
                it.condition = "pristine"


def compute_repair_cost(state: State, spec: ActionSpec, item: Item) -> int:
    formula = (spec.dynamic or {}).get("cost_formula", {})
    base_per_damage = int(formula.get("base_per_damage_pence", 10))
    min_cost = int(formula.get("min_cost_pence", 50))
    discount_per_point = float(formula.get("skill_discount_per_point", 2))
    damage = max(0, 100 - int(item.condition_value))
    base_cost = damage * base_per_damage
    maintenance_skill = _get_skill_value(state, "maintenance")
    discount = maintenance_skill * discount_per_point
    return max(min_cost, int(base_cost - discount))


def compute_repair_restoration(state: State, spec: ActionSpec) -> int:
    formula = (spec.dynamic or {}).get("restoration_formula", {})
    base = float(formula.get("base", 30))
    per_skill = float(formula.get("per_skill_point", 0.5))
    maintenance_skill = _get_skill_value(state, "maintenance")
    return int(base + maintenance_skill * per_skill)
