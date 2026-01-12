"""Data-driven action execution engine.

This module provides the core logic for validating, computing tiers, and applying
outcomes for actions defined in YAML specifications.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import random

from .models import State, Item, generate_instance_id
from .action_call import ActionCall
from .content_specs import ActionSpec, ItemMeta
from .constants import MAX_EVENT_LOG, SKILL_TO_APTITUDE
from .param_resolver import (
    apply_drop,
    apply_pickup,
    select_item_instance,
    validate_connected_to_param,
    validate_parameters,
)


def _log(state: State, event_id: str, **params: Any) -> None:
    """Log an event to the state's event log.

    Args:
        state: Game state
        event_id: Event identifier
        **params: Event parameters
    """
    state.event_log.append({"event_id": event_id, "params": params})
    if len(state.event_log) > MAX_EVENT_LOG:
        state.event_log = state.event_log[-MAX_EVENT_LOG:]


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


def _get_skill_value_with_aptitude(state: State, skill_name: str, aptitude_weight: float = 1.0) -> float:
    """Get a skill value adjusted by its governing aptitude.

    Args:
        state: Game state
        skill_name: Name of the skill
        aptitude_weight: Weight applied to the aptitude modifier (0.0-1.0)

    Returns:
        Skill value scaled by aptitude.
    """
    base = _get_skill_value(state, skill_name)
    if not skill_name or aptitude_weight <= 0.0:
        return base
    aptitude_name = SKILL_TO_APTITUDE.get(skill_name)
    if not aptitude_name:
        return base
    aptitude_value = getattr(state.player.aptitudes, aptitude_name, 1.0)
    return base * (1.0 + (aptitude_value - 1.0) * aptitude_weight)


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


def _track_habit(state: State, habit_name: str, amount: int) -> None:
    """Track habit points for trait drift.

    Args:
        state: Game state
        habit_name: Name of the habit to track
        amount: Amount of habit points to add
    """
    state.player.habit_tracker[habit_name] = state.player.habit_tracker.get(habit_name, 0) + amount


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
        if provides not in meta.provides and provides not in meta.tags:
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
    aptitude_weight = float(mods.get("aptitude_weight", 1.0))
    base = _get_skill_value_with_aptitude(state, primary, aptitude_weight) if primary else 0.0

    # Add weighted secondary skills
    for s, w in (mods.get("secondary_skills") or {}).items():
        base += _get_skill_value_with_aptitude(state, s, aptitude_weight) * float(w)

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
        amt = dur.get("amount")
        it = _find_best_item_for_provides(state, item_meta, prov, state.world.location)
        if it is None:
            _log(state, "item.durability_missing", provides=prov)
            return

        if amt is None:
            meta = item_meta.get(it.item_id)
            default_amt = None
            if meta and meta.durability:
                default_amt = meta.durability.get("degrade_per_use_default")
            amt = int(default_amt or 1)

        degrade_item_condition(it, base_degradation=int(amt))


def update_item_condition(item: Item) -> None:
    """Update item condition string from condition value."""
    if item.condition_value >= 90:
        item.condition = "pristine"
    elif item.condition_value >= 70:
        item.condition = "used"
    elif item.condition_value >= 40:
        item.condition = "worn"
    elif item.condition_value >= 20:
        item.condition = "broken"
    else:
        item.condition = "filthy"


def degrade_item_condition(item: Item, base_degradation: int = 5) -> None:
    """Degrade an item's condition, scaling with poor condition."""
    degradation = base_degradation
    if item.condition_value < 40:
        degradation = int(base_degradation * 1.5)
    item.condition_value = max(0, item.condition_value - degradation)
    update_item_condition(item)


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


def execute_action(
    state: State,
    spec: ActionSpec,
    item_meta: Dict[str, ItemMeta],
    action_call: ActionCall,
    rng_seed: int,
    current_tick: int,
) -> None:
    """Execute a validated action spec, applying effects and logging events."""
    if spec.id == "move":
        target = action_call.params.get("target_space")
        current_location = state.world.location
        if isinstance(target, str) and target in state.spaces:
            from_space = state.spaces.get(current_location)
            to_space = state.spaces.get(target)
            state.world.location = target
            tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
            apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)
            _log(
                state,
                "action.move",
                from_id=current_location,
                to_id=target,
                from_location=getattr(from_space, "name", current_location),
                to_location=getattr(to_space, "name", target),
            )
        else:
            _log(state, "action.failed", action_id=spec.id, reason="invalid_target")
        return

    if spec.id == "repair_item":
        item_ref = action_call.params.get("item_ref")
        item = select_item_instance(state, item_ref) if isinstance(item_ref, dict) else None
        if item is None:
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item")
            return
        if item.condition_value >= 90:
            _log(state, "action.failed", action_id=spec.id, reason="item_already_pristine")
            return
        cost = compute_repair_cost(state, spec, item)
        if state.player.money_pence < cost:
            _log(state, "action.failed", action_id=spec.id, reason="insufficient_funds")
            return
        state.player.money_pence -= cost
        restoration = compute_repair_restoration(state, spec)
        item.condition_value = min(100, item.condition_value + restoration)
        update_item_condition(item)
        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)
        outcome = spec.outcomes.get(tier) or spec.outcomes.get(1) or {}
        outcome_params = (outcome.get("events", [{}])[0].get("params", {}) or {})
        _log(
            state,
            "action.repair_item",
            instance_id=item.instance_id,
            item_id=item.item_id,
            cost_pence=cost,
            restoration=restoration,
            **outcome_params,
        )
        return

    if spec.id == "pick_up_item":
        item_ref = action_call.params.get("item_ref")
        item = select_item_instance(state, item_ref) if isinstance(item_ref, dict) else None
        if item is None:
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item")
            return
        ok_pickup, msg = apply_pickup(state, item)
        if not ok_pickup:
            _log(state, "action.failed", action_id=spec.id, reason=msg)
            return
        _log(state, "action.pick_up_item", instance_id=item.instance_id, item_id=item.item_id)
        return

    if spec.id == "drop_item":
        item_ref = action_call.params.get("item_ref")
        item = select_item_instance(state, item_ref) if isinstance(item_ref, dict) else None
        if item is None:
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item")
            return
        ok_drop, msg = apply_drop(state, item)
        if not ok_drop:
            _log(state, "action.failed", action_id=spec.id, reason=msg)
            return
        _log(state, "action.drop_item", instance_id=item.instance_id, item_id=item.item_id)
        return

    if spec.id == "work":
        from .constants import JOBS
        # Get current job details
        current_job = state.player.current_job
        job_data = JOBS.get(current_job, JOBS["recycling_collector"])

        # Calculate tier for work quality
        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)

        # Apply resource consumption
        apply_consumes(state, spec, item_meta)

        # Calculate earnings with modifiers
        base_earnings = job_data["base_pay"]
        confidence_mod = 1.0 + (state.player.traits.confidence / 100.0) * 0.2
        tier_mod = 1.0 + (tier * 0.05)  # 0%, 5%, 10%, 15% bonus for tiers 0-3
        earnings = int(base_earnings * confidence_mod * tier_mod)

        state.player.money_pence += earnings

        # Calculate and apply fatigue
        fatigue_cost = job_data["fatigue_cost"]
        discipline_mod = 1.0 - (state.player.traits.discipline / 100.0) * 0.2
        fitness_mod = 1.0 - (state.player.traits.fitness / 100.0) * 0.15
        health_penalty = _get_health_penalty(state)
        fatigue_cost = int(fatigue_cost * discipline_mod * fitness_mod * (2.0 - health_penalty) * (1.0 - tier * 0.05))
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)

        # Apply base outcome (mood changes, etc.)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)

        # Apply job-specific skill gains
        skill_gains_log = {}
        for skill_name, xp_gain in job_data.get("skill_gains", {}).items():
            if skill_name == "fitness":
                # Fitness is a trait, not a skill
                _track_habit(state, "fitness", int(xp_gain * 10))
            else:
                gain = _apply_skill_xp(state, skill_name, xp_gain * (1.0 + tier * 0.2), current_tick)
                skill_gains_log[skill_name] = round(gain, 2)

        # Track habits
        _track_habit(state, "discipline", 10)
        _track_habit(state, "confidence", 8)

        # Log the work action
        _log(state, "action.work",
             earned_pence=earnings,
             job=job_data["name"],
             skill_gains=skill_gains_log,
             tier=tier)
        return

    if spec.id == "pay_utilities":
        # Calculate cost with discounts
        base_cost = 2000
        resource_mgmt_discount = state.player.skills_detailed["resource_management"].value * 10
        frugality_discount = state.player.traits.frugality / 100.0 * 200

        # Check for utilities_discount_pence flag from negotiate_utilities
        discount_flag = getattr(state.player, "flags", {}).get("utilities_discount_pence", 0)

        cost = max(0, int(base_cost - resource_mgmt_discount - frugality_discount - discount_flag))

        if state.player.money_pence < cost:
            _log(state, "action.failed", action_id=spec.id, reason="insufficient_funds")
            return

        state.player.money_pence -= cost
        state.player.utilities_paid = True

        # Clear the discount flag after use
        if hasattr(state.player, "flags") and "utilities_discount_pence" in state.player.flags:
            del state.player.flags["utilities_discount_pence"]

        # Track frugality habit
        _track_habit(state, "frugality", 5)

        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)

        _log(state, "bills.paid", cost_pence=cost, tier=tier)
        return

    if spec.id == "skip_utilities":
        # This action is intentionally handled outside the standard compute_tier/apply_outcome
        # flow: it has no YAML-defined tiered outcomes and simply flips a flag plus logging.
        state.player.utilities_paid = False
        _log(state, "bills.skipped")
        return

    if spec.id == "shower":
        # Standard tier computation and outcome application
        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_consumes(state, spec, item_meta)
        apply_outcome(state, spec, tier, item_meta, current_tick)

        # Apply warmth penalty if no heat (legacy behavior)
        if not state.utilities.heat:
            state.player.needs.warmth = max(0, state.player.needs.warmth - 10)
        return

    if spec.id == "clean_room":
        # Standard tier computation and outcome application
        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_consumes(state, spec, item_meta)
        apply_outcome(state, spec, tier, item_meta, current_tick)

        # Track discipline habit (legacy behavior)
        _track_habit(state, "discipline", 10)
        return

    if spec.id == "purchase_item":
        from .engine import _get_item_metadata

        item_id = action_call.params.get("item_id")
        if not item_id or not isinstance(item_id, str):
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item_id")
            return

        # Get item metadata from items.yaml (legacy format)
        metadata = _get_item_metadata(item_id)
        price = metadata.get("price", 0)
        quality = metadata.get("quality", 1.0)
        item_name = metadata.get("name", item_id)

        if price <= 0:
            _log(state, "action.failed", action_id=spec.id, reason="item_not_for_sale")
            return

        # Check if player has enough money
        if state.player.money_pence < price:
            _log(state, "action.failed", action_id=spec.id, reason="insufficient_funds",
                 required_pence=price, current_pence=state.player.money_pence)
            return

        # Deduct money
        state.player.money_pence -= price

        # Create new item with deterministic instance ID
        rng = random.Random(rng_seed + state.world.day * 97)
        new_item = Item(
            instance_id=generate_instance_id(rng),
            item_id=item_id,
            placed_in=state.world.location,
            container=None,
            slot="floor",
            quality=quality,
            condition="pristine",
            condition_value=100,
            bulk=metadata.get("bulk", 1),
        )
        state.items.append(new_item)

        # Track confidence habit
        _track_habit(state, "confidence", 3)

        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)

        _log(state, "shopping.purchase", item_id=item_id, item_name=item_name,
             cost_pence=price, quality=quality, tier=tier)
        return

    if spec.id == "sell_item":
        from .engine import _get_item_metadata

        item_id = action_call.params.get("item_id")
        if not item_id or not isinstance(item_id, str):
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item_id")
            return

        # Find the item at current location
        item_to_sell = None
        for item in state.items:
            if item.item_id == item_id and item.placed_in == state.world.location:
                item_to_sell = item
                break

        if item_to_sell is None:
            _log(state, "action.failed", action_id=spec.id, reason="item_not_found")
            return

        # Get item metadata from items.yaml (legacy format)
        metadata = _get_item_metadata(item_id)
        base_price = metadata.get("price", 0)
        item_name = metadata.get("name", item_id)

        if base_price <= 0:
            _log(state, "action.failed", action_id=spec.id, reason="item_not_sellable")
            return

        # Calculate sell price: 40% of base price, adjusted by condition
        condition_multiplier = item_to_sell.condition_value / 100.0
        sell_price = int(base_price * 0.4 * condition_multiplier)
        sell_price = max(100, sell_price)  # Minimum sell price

        # Add money
        state.player.money_pence += sell_price

        # Remove item
        state.items.remove(item_to_sell)

        # Track frugality habit
        _track_habit(state, "frugality", 5)

        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)

        _log(state, "shopping.sell", item_id=item_id, item_name=item_name,
             earned_pence=sell_price, condition=item_to_sell.condition, tier=tier)
        return

    if spec.id == "discard_item":
        from .engine import _get_item_metadata

        item_id = action_call.params.get("item_id")
        if not item_id or not isinstance(item_id, str):
            _log(state, "action.failed", action_id=spec.id, reason="invalid_item_id")
            return

        # Find the item at current location
        item_to_discard = None
        for item in state.items:
            if item.item_id == item_id and item.placed_in == state.world.location:
                item_to_discard = item
                break

        if item_to_discard is None:
            _log(state, "action.failed", action_id=spec.id, reason="item_not_found")
            return

        # Get item metadata for display name
        metadata = _get_item_metadata(item_id)
        item_name = metadata.get("name", item_id)

        # Remove item
        state.items.remove(item_to_discard)

        # Track minimalism habit
        _track_habit(state, "minimalism", 2)

        _log(state, "shopping.discard", item_id=item_id, item_name=item_name,
             condition=item_to_discard.condition)
        return

    if spec.id == "apply_job":
        from .constants import JOBS
        from .engine import _check_job_requirements

        job_id = action_call.params.get("job_id")
        if not job_id or not isinstance(job_id, str):
            _log(state, "action.failed", action_id=spec.id, reason="invalid_job_id")
            return

        if job_id not in JOBS:
            _log(state, "action.failed", action_id=spec.id, reason="job_not_found")
            return

        job_data = JOBS[job_id]

        # Check if already have this job
        if state.player.current_job == job_id:
            _log(state, "action.failed", action_id=spec.id, reason="already_employed")
            return

        # Check requirements
        meets_requirements, reason = _check_job_requirements(state, job_id)

        if not meets_requirements:
            _log(state, "job.application_rejected",
                 job_id=job_id,
                 job_name=job_data["name"],
                 reason=reason)
            return

        # Application successful
        old_job = state.player.current_job
        state.player.current_job = job_id

        tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
        apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=False)

        # Track confidence habit (restored to legacy value of 20 points)
        _track_habit(state, "confidence", 20)

        old_job_name = JOBS[old_job]["name"] if old_job in JOBS else "Unemployed"
        _log(state, "job.application_accepted",
             job_id=job_id,
             job_name=job_data["name"],
             old_job=old_job_name,
             tier=tier)
        return

    tier = compute_tier(state, spec, item_meta, rng_seed=rng_seed)
    apply_consumes(state, spec, item_meta)
    apply_outcome(state, spec, tier, item_meta, current_tick)
