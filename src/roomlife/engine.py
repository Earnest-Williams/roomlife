from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict, List, Tuple

from .constants import (
    DOCTOR_ILLNESS_RECOVERY,
    DOCTOR_INJURY_RECOVERY,
    DOCTOR_VISIT_COST,
    HEALTH_DEGRADATION_PER_EXTREME_NEED,
    HEALTH_EXTREME_NEED_THRESHOLD,
    HEALTH_PENALTY_THRESHOLD,
    ILLNESS_RECOVERY_PER_TURN,
    INJURY_RECOVERY_PER_TURN,
    MAX_EVENT_LOG,
    REST_ILLNESS_RECOVERY,
    REST_INJURY_RECOVERY,
    SKILL_NAMES,
    SKILL_TO_APTITUDE,
    TIME_SLICES,
    TRAIT_DRIFT_CONFIGS,
    TRAIT_DRIFT_THRESHOLD,
)
from .models import Item, Skill, Space, State


def _log(state: State, event_id: str, **params: object) -> None:
    state.event_log.append({"event_id": event_id, "params": params})
    # Limit event log size to prevent unbounded growth
    if len(state.event_log) > MAX_EVENT_LOG:
        state.event_log = state.event_log[-MAX_EVENT_LOG:]


def _get_skill(state: State, skill_name: str) -> Skill:
    """Get a skill by name from the player's skill dictionary."""
    return state.player.skills_detailed[skill_name]


def _load_item_tags() -> Dict[str, List[str]]:
    """Load item tags from items.yaml data file."""
    import yaml
    from pathlib import Path

    data_path = Path(__file__).parent.parent.parent / "data" / "items.yaml"
    try:
        with open(data_path, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: items.yaml not found at {data_path}, returning empty tags")
        return {}
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse items.yaml: {e}, returning empty tags")
        return {}
    except Exception as e:
        print(f"Warning: Unexpected error loading items.yaml: {e}, returning empty tags")
        return {}

    item_tags = {}
    try:
        for item_def in data.get("items", []):
            item_tags[item_def["id"]] = item_def.get("tags", [])
    except (KeyError, TypeError) as e:
        print(f"Warning: Malformed items.yaml data structure: {e}, returning partial tags")
    return item_tags


# Cache item tags to avoid reloading YAML repeatedly
_ITEM_TAGS_CACHE = None
_ITEM_METADATA_CACHE = None
_SHOP_CATALOG_CACHE = None


def _get_item_tags(item_id: str) -> List[str]:
    """Get tags for a specific item."""
    global _ITEM_TAGS_CACHE
    if _ITEM_TAGS_CACHE is None:
        _ITEM_TAGS_CACHE = _load_item_tags()
    return _ITEM_TAGS_CACHE.get(item_id, [])


def _load_item_metadata() -> Dict[str, dict]:
    """Load item metadata (price, quality, description) from items.yaml."""
    import yaml
    from pathlib import Path

    data_path = Path(__file__).parent.parent.parent / "data" / "items.yaml"
    try:
        with open(data_path, "r") as f:
            data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError, Exception) as e:
        print(f"Warning: Failed to load items.yaml: {e}")
        return {}

    item_metadata = {}
    try:
        for item_def in data.get("items", []):
            item_id = item_def["id"]
            item_metadata[item_id] = {
                "name": item_def.get("name", item_id),
                "price": item_def.get("price", 0),
                "quality": item_def.get("quality", 1.0),
                "description": item_def.get("description", ""),
                "tags": item_def.get("tags", []),
            }
    except (KeyError, TypeError) as e:
        print(f"Warning: Malformed items.yaml data: {e}")
    return item_metadata


def _get_item_metadata(item_id: str) -> dict:
    """Get metadata for a specific item."""
    global _ITEM_METADATA_CACHE
    if _ITEM_METADATA_CACHE is None:
        _ITEM_METADATA_CACHE = _load_item_metadata()
    return _ITEM_METADATA_CACHE.get(item_id, {
        "name": item_id,
        "price": 0,
        "quality": 1.0,
        "description": "",
        "tags": [],
    })


def _load_shop_catalog() -> dict:
    """Load shop catalog from shop_catalog.yaml."""
    import yaml
    from pathlib import Path

    data_path = Path(__file__).parent.parent.parent / "data" / "shop_catalog.yaml"
    try:
        with open(data_path, "r") as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError, Exception) as e:
        print(f"Warning: Failed to load shop_catalog.yaml: {e}")
        return {}


def _get_shop_catalog() -> dict:
    """Get the shop catalog (cached)."""
    global _SHOP_CATALOG_CACHE
    if _SHOP_CATALOG_CACHE is None:
        _SHOP_CATALOG_CACHE = _load_shop_catalog()
    return _SHOP_CATALOG_CACHE


def _find_item_with_tag(state: State, tag: str, location: str = None) -> Item | None:
    """Find an item with a specific tag at the current or specified location."""
    if location is None:
        location = state.world.location

    items_here = state.get_items_at(location)
    for item in items_here:
        if tag in _get_item_tags(item.item_id):
            return item
    return None


def _get_item_effectiveness(item: Item) -> float:
    """Calculate item effectiveness multiplier based on condition_value (0-100) and quality."""
    # Base effectiveness from condition
    if item.condition_value >= 90:
        condition_mult = 1.1  # pristine items give bonus
    elif item.condition_value >= 70:
        condition_mult = 1.0  # used items work normally
    elif item.condition_value >= 40:
        condition_mult = 0.8  # worn items less effective
    elif item.condition_value >= 20:
        condition_mult = 0.5  # broken items barely work
    else:
        condition_mult = 0.3  # filthy items very poor

    # Combine condition and quality multipliers
    # Quality ranges from 0.8 (worn desk) to 1.8 (premium computer)
    return condition_mult * item.quality


def _update_item_condition_string(item: Item) -> None:
    """Update the condition string based on condition_value."""
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


def _degrade_item(item: Item, base_degradation: int = 5) -> None:
    """Degrade an item's condition based on use."""
    # Worse condition items degrade faster
    if item.condition_value < 40:
        degradation = int(base_degradation * 1.5)
    else:
        degradation = base_degradation

    item.condition_value = max(0, item.condition_value - degradation)
    _update_item_condition_string(item)


def _calculate_health(state: State) -> None:
    """Calculate overall health based on illness and injury."""
    n = state.player.needs
    health_penalty = (n.illness + n.injury) * 0.5
    n.health = max(0, min(100, int(100 - health_penalty)))


def _get_health_penalty(state: State) -> float:
    """Calculate health penalty multiplier for actions (0.5 to 1.0).

    Returns:
        1.0 if health >= HEALTH_PENALTY_THRESHOLD
        0.5 if health = 0
        Linear interpolation between 0.5 and 1.0 for health below threshold
    """
    _calculate_health(state)  # Ensure health is up-to-date
    health = state.player.needs.health
    if health >= HEALTH_PENALTY_THRESHOLD:
        return 1.0
    # Linear interpolation: health 0 = 0.5, health 50 = 1.0
    return 0.5 + (health / HEALTH_PENALTY_THRESHOLD) * 0.5


def _apply_skill_rust(state: State, current_tick: int) -> None:
    for skill_name in SKILL_NAMES:
        skill = _get_skill(state, skill_name)
        ticks_passed = current_tick - skill.last_tick
        if ticks_passed > 0 and skill.value > 0:
            rust_amount = skill.rust_rate * ticks_passed
            discipline_mod = 1.0 - (state.player.traits.discipline / 100.0) * 0.3
            rust_amount *= discipline_mod
            skill.value = max(0.0, skill.value - rust_amount)
            skill.last_tick = current_tick


def _gain_skill_xp(state: State, skill_name: str, gain: float, current_tick: int) -> float:
    skill = _get_skill(state, skill_name)
    curiosity_mod = 1.0 + (state.player.traits.curiosity / 100.0) * 0.3
    health_penalty = _get_health_penalty(state)  # Apply health penalty to skill gains
    actual_gain = gain * curiosity_mod * health_penalty
    skill.value += actual_gain
    skill.last_tick = current_tick
    aptitude_name = SKILL_TO_APTITUDE[skill_name]
    aptitude = getattr(state.player.aptitudes, aptitude_name)
    aptitude_gain = actual_gain * 0.002
    new_aptitude = aptitude + aptitude_gain
    setattr(state.player.aptitudes, aptitude_name, new_aptitude)
    return actual_gain


def _track_habit(state: State, habit_name: str, amount: int) -> None:
    state.player.habit_tracker[habit_name] = state.player.habit_tracker.get(habit_name, 0) + amount


def _apply_trait_drift(state: State) -> List[str]:
    """Apply trait changes based on habit accumulation (optimized loop-based approach)."""
    messages = []
    tracker = state.player.habit_tracker
    traits = state.player.traits

    for config in TRAIT_DRIFT_CONFIGS:
        habit_name = config["habit"]
        trait_name = config["trait"]
        if tracker.get(habit_name, 0) > TRAIT_DRIFT_THRESHOLD:
            current_trait = getattr(traits, trait_name)
            setattr(traits, trait_name, min(100, current_trait + 1))
            messages.append(config["message"])
            tracker[habit_name] = 0

    return messages


def _calculate_current_tick(state: State) -> int:
    try:
        slice_index = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # Invalid slice, default to 0 (morning)
        print(f"Warning: Invalid time slice '{state.world.slice}' in _calculate_current_tick, using 0")
        slice_index = 0
    return state.world.day * 4 + slice_index


def new_game() -> State:
    state = State()
    state.spaces = {
        "room_001": Space("room_001", "Tiny room", "room", 14, False, ["hall_001"]),
        "hall_001": Space("hall_001", "Hallway", "shared", 12, False, ["room_001", "bath_001"]),
        "bath_001": Space("bath_001", "Shared bathroom", "shared", 13, False, ["hall_001"]),
    }

    # Create starter items with quality from metadata
    # Items start at ~50% condition (worn) to reflect their degraded state
    starter_items = [
        ("bed_basic", "worn", 50, "room_001", "floor"),
        ("desk_worn", "worn", 45, "room_001", "wall"),
        ("kettle", "worn", 50, "room_001", "surface"),
    ]

    state.items = []
    for item_id, condition, condition_value, placed_in, slot in starter_items:
        metadata = _get_item_metadata(item_id)
        quality = metadata.get("quality", 1.0)
        state.items.append(Item(
            item_id=item_id,
            condition=condition,
            condition_value=condition_value,
            placed_in=placed_in,
            slot=slot,
            quality=quality
        ))

    # Validate that the starting location exists in the world
    if state.world.location not in state.spaces:
        raise ValueError(f"Starting location '{state.world.location}' does not exist in world spaces")
    _log(state, "game.start", day=state.world.day, slice=state.world.slice)
    return state


def _advance_time(state: State) -> None:
    try:
        idx = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # If current slice is invalid, reset to first slice
        print(f"Warning: Invalid time slice '{state.world.slice}', resetting to '{TIME_SLICES[0]}'")
        state.world.slice = TIME_SLICES[0]
        _log(state, "time.advance", day=state.world.day, slice=state.world.slice)
        return

    if idx == len(TIME_SLICES) - 1:
        state.world.day += 1
        state.world.slice = TIME_SLICES[0]
        _log(state, "time.new_day", day=state.world.day)
    else:
        state.world.slice = TIME_SLICES[idx + 1]
    _log(state, "time.advance", day=state.world.day, slice=state.world.slice)


def _apply_environment(state: State, rng: random.Random) -> None:
    current_tick = _calculate_current_tick(state)
    _apply_skill_rust(state, current_tick)
    trait_messages = _apply_trait_drift(state)
    for msg in trait_messages:
        _log(state, "trait.drift", message=msg)

    if not state.player.utilities_paid:
        state.utilities.power = False
        state.utilities.heat = False
        state.utilities.water = False
    else:
        state.utilities.power = True
        state.utilities.heat = True
        state.utilities.water = True

    n = state.player.needs
    n.hunger = min(100, n.hunger + 8)
    n.fatigue = min(100, n.fatigue + 6)
    if state.utilities.water:
        n.hygiene = max(0, n.hygiene - 4)
    else:
        n.hygiene = max(0, n.hygiene - 8)
        n.mood = max(0, n.mood - 2)
        _log(state, "utility.no_water")

    if state.utilities.heat:
        n.warmth = min(100, n.warmth + 4)
    else:
        n.warmth = max(0, n.warmth - 10)
        n.mood = max(0, n.mood - 3)
        _log(state, "utility.no_heat")

    if not state.utilities.power:
        n.mood = max(0, n.mood - 2)
        _log(state, "utility.no_power")

    # Calculate energy based on fatigue and fitness trait
    # Energy is inversely proportional to fatigue
    base_energy = 100 - n.fatigue
    # Fitness trait provides a bonus/penalty (fitness 50 = neutral, above = bonus, below = penalty)
    fitness_modifier = (state.player.traits.fitness - 50) * 0.2
    n.energy = max(0, min(100, int(base_energy + fitness_modifier)))

    # Health degradation from extreme needs
    extreme_needs = []
    if n.hunger > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("hunger")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.fatigue > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("fatigue")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.hygiene > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("hygiene")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.stress > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("stress")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED * 0.5)  # Stress contributes less
    if n.warmth < 20:  # Cold causes illness
        extreme_needs.append("cold")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)

    # Natural recovery from illness and injury
    if n.illness > 0:
        stoicism_bonus = state.player.traits.stoicism / 100.0 * 0.5  # Stoicism helps recovery
        recovery = ILLNESS_RECOVERY_PER_TURN * (1.0 + stoicism_bonus)
        n.illness = max(0, n.illness - recovery)
    if n.injury > 0:
        fitness_bonus = state.player.traits.fitness / 100.0 * 0.3  # Fitness helps injury recovery
        recovery = INJURY_RECOVERY_PER_TURN * (1.0 + fitness_bonus)
        n.injury = max(0, n.injury - recovery)

    # Calculate overall health based on illness and injury
    _calculate_health(state)

    # Log health warnings
    if extreme_needs:
        _log(state, "health.degradation", extreme_needs=extreme_needs, illness=int(n.illness), injury=int(n.injury))
    if n.health < 30:
        _log(state, "health.critical", health=n.health)
    elif n.health < 50:
        _log(state, "health.warning", health=n.health)

    # Random events
    if rng.random() < 0.05:
        _log(state, "building.noise", severity="low")

    # Small chance of minor injury from accidents
    if rng.random() < 0.02:
        injury_amount = rng.randint(5, 15)
        n.injury = min(100, n.injury + injury_amount)
        # Recalculate health to reflect the new injury immediately
        _calculate_health(state)
        _log(state, "health.injury", injury_amount=injury_amount, source="accident")
        # Log additional warning if injury pushed health below thresholds
        if n.health < 30:
            _log(state, "health.critical", health=n.health)
        elif n.health < 50:
            _log(state, "health.warning", health=n.health)


def apply_action(state: State, action_id: str, rng_seed: int = 1) -> None:
    try:
        time_slice_index = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # If current slice is invalid, use 0 as fallback
        print(f"Warning: Invalid time slice '{state.world.slice}' in apply_action, using 0")
        time_slice_index = 0

    rng = random.Random(rng_seed + state.world.day * 97 + time_slice_index)
    current_tick = _calculate_current_tick(state)

    if action_id == "work":
        # Check for desk/workspace
        desk = _find_item_with_tag(state, "work")
        if desk is None:
            _log(state, "action.failed", action_id="work", reason="no_workspace")
        else:
            # Item effectiveness affects productivity and fatigue
            item_effectiveness = _get_item_effectiveness(desk)
            health_penalty = _get_health_penalty(state)
            base_earnings = 3500
            earnings = int(base_earnings * item_effectiveness * health_penalty)  # Poor health reduces productivity

            state.player.money_pence += earnings
            fatigue_cost = 15
            discipline_mod = 1.0 - (state.player.traits.discipline / 100.0) * 0.2
            # Better desk reduces fatigue, poor health increases fatigue
            fatigue_cost = int(fatigue_cost * discipline_mod * (2.0 - item_effectiveness) * (2.0 - health_penalty))
            state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)
            state.player.needs.mood = max(0, state.player.needs.mood - 2)
            state.player.skills["general"] = state.player.skills.get("general", 0) + 1
            gain = _gain_skill_xp(state, "technical_literacy", 2.0, current_tick)
            _track_habit(state, "discipline", 10)
            _track_habit(state, "confidence", 8)

            # Degrade desk with use
            _degrade_item(desk, base_degradation=3)

            _log(state, "action.work", earned_pence=earnings, skill_gain=round(gain, 2),
                 item_condition=desk.condition, item_effectiveness=round(item_effectiveness, 2))

    elif action_id == "study":
        # Check for desk/study area
        desk = _find_item_with_tag(state, "study")
        if desk is None:
            _log(state, "action.failed", action_id="study", reason="no_study_area")
        else:
            # Item effectiveness affects learning
            item_effectiveness = _get_item_effectiveness(desk)
            fatigue_base = 10
            ergonomics_bonus = _get_skill(state, "ergonomics").value * 0.1
            # Better desk reduces fatigue
            fatigue_cost = int(fatigue_base * (1.0 - ergonomics_bonus) * (2.0 - item_effectiveness))
            state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)
            state.player.needs.mood = min(100, state.player.needs.mood + 1)
            state.player.skills["general"] = state.player.skills.get("general", 0) + 2
            # Better desk improves learning
            gain = _gain_skill_xp(state, "focus", 3.0 * item_effectiveness, current_tick)
            _track_habit(state, "discipline", 15)

            # Degrade desk with use
            _degrade_item(desk, base_degradation=2)

            _log(state, "action.study", skill_gain=round(gain, 2),
                 item_condition=desk.condition, item_effectiveness=round(item_effectiveness, 2))

    elif action_id == "sleep":
        # Check for bed
        bed = _find_item_with_tag(state, "sleep")
        if bed is None:
            _log(state, "action.failed", action_id="sleep", reason="no_bed")
        else:
            # Calculate recovery with item effectiveness
            item_effectiveness = _get_item_effectiveness(bed)
            base_recovery = 35
            fitness_bonus = state.player.traits.fitness / 100.0 * 10
            total_recovery = int((base_recovery + fitness_bonus) * item_effectiveness)

            state.player.needs.fatigue = max(0, state.player.needs.fatigue - total_recovery)
            state.player.needs.mood = min(100, state.player.needs.mood + 3)
            introspection_stress_reduction = _get_skill(state, "introspection").value * 0.5
            state.player.needs.stress = max(0, int(state.player.needs.stress - introspection_stress_reduction))

            # Degrade bed with use
            _degrade_item(bed, base_degradation=2)

            _log(state, "action.sleep", fatigue_recovered=total_recovery,
                 item_condition=bed.condition, item_effectiveness=round(item_effectiveness, 2))

    elif action_id == "eat_charity_rice":
        base_hunger_reduction = 25
        nutrition_bonus = _get_skill(state, "nutrition").value * 0.2
        total_reduction = int(base_hunger_reduction + nutrition_bonus)
        state.player.needs.hunger = max(0, state.player.needs.hunger - total_reduction)
        state.player.needs.mood = max(0, state.player.needs.mood - 1)
        _log(state, "food.eat", meal_id="charity_rice", hunger_reduced=total_reduction)

    elif action_id == "pay_utilities":
        base_cost = 2000
        resource_mgmt_discount = _get_skill(state, "resource_management").value * 10
        frugality_discount = state.player.traits.frugality / 100.0 * 200
        cost = max(0, int(base_cost - resource_mgmt_discount - frugality_discount))
        if state.player.money_pence >= cost:
            state.player.money_pence -= cost
            state.player.utilities_paid = True
            gain = _gain_skill_xp(state, "resource_management", 1.0, current_tick)
            _track_habit(state, "frugality", 5)
            _log(state, "bills.paid", cost_pence=cost, skill_gain=round(gain, 2))
        else:
            state.player.utilities_paid = False
            _log(state, "bills.unpaid", cost_pence=cost)

    elif action_id == "skip_utilities":
        state.player.utilities_paid = False
        _log(state, "bills.skipped")

    elif action_id == "shower":
        # Check if water is available
        if not state.utilities.water:
            _log(state, "action.failed", action_id="shower", reason="no_water")
        # Check if in bathroom
        elif state.world.location != "bath_001":
            _log(state, "action.failed", action_id="shower", reason="wrong_location")
        else:
            # Apply hygiene and mood improvements
            state.player.needs.hygiene = max(0, state.player.needs.hygiene - 40)
            state.player.needs.mood = min(100, state.player.needs.mood + 5)

            # Apply warmth penalty if no heat
            if not state.utilities.heat:
                state.player.needs.warmth = max(0, state.player.needs.warmth - 10)

            _log(state, "action.shower", hygiene_improved=40)

    elif action_id == "cook_basic_meal":
        # Check if player has enough money
        cost = 300
        if state.player.money_pence < cost:
            _log(state, "action.failed", action_id="cook_basic_meal", reason="insufficient_funds")
        else:
            # Check for cooking item using tag system
            cooking_item = _find_item_with_tag(state, "cook")

            if cooking_item is None:
                _log(state, "action.failed", action_id="cook_basic_meal", reason="no_cooking_item")
            else:
                # Item effectiveness affects cooking quality
                item_effectiveness = _get_item_effectiveness(cooking_item)

                # Deduct cost
                state.player.money_pence -= cost

                # Base hunger reduction
                base_hunger_reduction = 35

                # Creativity trait bonus: +10% hunger reduction if creativity >= 75
                if state.player.traits.creativity >= 75:
                    base_hunger_reduction = int(base_hunger_reduction * 1.1)

                # Item effectiveness affects meal quality
                hunger_reduction = int(base_hunger_reduction * item_effectiveness)

                # Apply effects
                state.player.needs.hunger = max(0, state.player.needs.hunger - hunger_reduction)
                state.player.needs.mood = min(100, state.player.needs.mood + 3)

                # Gain nutrition skill
                gain = _gain_skill_xp(state, "nutrition", 1.5, current_tick)

                # Degrade cooking item with use
                _degrade_item(cooking_item, base_degradation=4)

                _log(state, "action.cook_basic_meal", cost_pence=cost, hunger_reduced=hunger_reduction,
                     skill_gain=round(gain, 2), item_condition=cooking_item.condition,
                     item_effectiveness=round(item_effectiveness, 2))

    elif action_id == "clean_room":
        # Apply effects
        state.player.needs.hygiene = max(0, state.player.needs.hygiene - 5)
        state.player.needs.mood = min(100, state.player.needs.mood + 8)
        state.player.needs.stress = max(0, state.player.needs.stress - 3)

        # Gain maintenance skill
        gain = _gain_skill_xp(state, "maintenance", 2.0, current_tick)

        # Track discipline habit
        _track_habit(state, "discipline", 10)

        _log(state, "action.clean_room", skill_gain=round(gain, 2))

    elif action_id == "exercise":
        # Base fatigue cost
        fatigue_cost = 20
        health_penalty = _get_health_penalty(state)

        # Fitness trait bonus: -20% fatigue cost if fitness >= 75
        if state.player.traits.fitness >= 75:
            fatigue_cost = int(fatigue_cost * 0.8)

        # Poor health increases fatigue cost
        fatigue_cost = int(fatigue_cost * (2.0 - health_penalty))

        # Apply effects
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)
        state.player.needs.hunger = min(100, state.player.needs.hunger + 5)
        state.player.needs.mood = min(100, state.player.needs.mood + 10)
        state.player.needs.stress = max(0, state.player.needs.stress - 5)
        # Energy will be recalculated in _apply_environment based on fatigue and fitness

        # Gain reflexivity skill
        gain = _gain_skill_xp(state, "reflexivity", 2.5, current_tick)

        _log(state, "action.exercise", fatigue_cost=fatigue_cost, skill_gain=round(gain, 2))

    elif action_id == "visit_doctor":
        # Check if player has enough money
        if state.player.money_pence < DOCTOR_VISIT_COST:
            _log(state, "action.failed", action_id="visit_doctor", reason="insufficient_funds")
        else:
            # Deduct cost
            state.player.money_pence -= DOCTOR_VISIT_COST

            # Record initial values for logging
            initial_illness = state.player.needs.illness
            initial_injury = state.player.needs.injury

            # Apply treatment
            state.player.needs.illness = max(0, state.player.needs.illness - DOCTOR_ILLNESS_RECOVERY)
            state.player.needs.injury = max(0, state.player.needs.injury - DOCTOR_INJURY_RECOVERY)

            # Small fatigue from travel and waiting
            state.player.needs.fatigue = min(100, state.player.needs.fatigue + 5)

            # Mood improvement from getting treatment
            state.player.needs.mood = min(100, state.player.needs.mood + 5)

            _log(state, "action.visit_doctor", cost_pence=DOCTOR_VISIT_COST,
                 illness_before=int(initial_illness), illness_after=int(state.player.needs.illness),
                 injury_before=int(initial_injury), injury_after=int(state.player.needs.injury))

    elif action_id == "rest":
        # Rest action for minor recovery - free but takes time
        initial_illness = state.player.needs.illness
        initial_injury = state.player.needs.injury

        # Apply recovery
        stoicism_bonus = state.player.traits.stoicism / 100.0 * 5  # Stoicism helps mental rest
        state.player.needs.illness = max(0, state.player.needs.illness - REST_ILLNESS_RECOVERY)
        state.player.needs.injury = max(0, state.player.needs.injury - REST_INJURY_RECOVERY)

        # Reduce fatigue slightly
        state.player.needs.fatigue = max(0, state.player.needs.fatigue - 10)

        # Reduce stress
        state.player.needs.stress = max(0, int(state.player.needs.stress - (5 + stoicism_bonus)))

        # Small mood improvement
        state.player.needs.mood = min(100, state.player.needs.mood + 3)

        _log(state, "action.rest", illness_before=int(initial_illness), illness_after=int(state.player.needs.illness),
             injury_before=int(initial_injury), injury_after=int(state.player.needs.injury))

    elif action_id.startswith("repair_"):
        # Extract item_id from action_id (e.g., "repair_bed_basic" -> "bed_basic")
        item_id = action_id[7:]  # Remove "repair_" prefix

        # Find the item at current location
        items_here = state.get_items_at(state.world.location)
        item_to_repair = None
        for item in items_here:
            if item.item_id == item_id:
                item_to_repair = item
                break

        if item_to_repair is None:
            _log(state, "action.failed", action_id=action_id, reason="item_not_found")
        elif item_to_repair.condition_value >= 90:
            _log(state, "action.failed", action_id=action_id, reason="item_already_pristine")
        else:
            # Calculate repair cost based on damage
            damage = 100 - item_to_repair.condition_value
            base_cost = int(damage * 10)  # 10 pence per condition point

            # Maintenance skill reduces cost
            maintenance_skill = _get_skill(state, "maintenance").value
            discount = maintenance_skill * 2
            cost = max(50, int(base_cost - discount))  # Minimum 50p

            if state.player.money_pence < cost:
                _log(state, "action.failed", action_id=action_id, reason="insufficient_funds")
            else:
                # Deduct cost
                state.player.money_pence -= cost

                # Calculate restoration based on maintenance skill
                base_restoration = 30
                skill_bonus = maintenance_skill * 0.5
                total_restoration = int(base_restoration + skill_bonus)

                # Restore item condition
                old_condition = item_to_repair.condition
                item_to_repair.condition_value = min(100, item_to_repair.condition_value + total_restoration)
                _update_item_condition_string(item_to_repair)

                # Gain maintenance skill
                gain = _gain_skill_xp(state, "maintenance", 2.0, current_tick)

                # Track frugality habit
                _track_habit(state, "frugality", 5)

                _log(state, "action.repair_item", item_id=item_id, cost_pence=cost,
                     restoration=total_restoration, old_condition=old_condition,
                     new_condition=item_to_repair.condition, skill_gain=round(gain, 2))

    elif action_id.startswith("move_"):
        # Extract target location from action_id (e.g., "move_hall_001" -> "hall_001")
        target_location = action_id[5:]  # Remove "move_" prefix
        current_location = state.world.location

        # Validate current location exists (safety check for corrupted state)
        if current_location not in state.spaces:
            _log(state, "action.failed", action_id=action_id, reason="current_location_invalid")
        # Validate not moving to same location (check this first for better error message)
        elif target_location == current_location:
            _log(state, "action.failed", action_id=action_id, reason="already_here")
        # Validate target location exists
        elif target_location not in state.spaces:
            _log(state, "action.failed", action_id=action_id, reason="location_not_found")
        # Validate target is connected to current location
        elif target_location not in state.spaces[current_location].connections:
            _log(state, "action.failed", action_id=action_id, reason="location_not_connected")
        else:
            # Move to new location
            from_space = state.spaces[current_location]
            to_space = state.spaces[target_location]
            state.world.location = target_location

            # Small fatigue cost for movement
            fatigue_cost = 2
            state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)

            _log(state, "action.move", from_location=from_space.name, to_location=to_space.name,
                 from_id=current_location, to_id=target_location)

    elif action_id.startswith("purchase_"):
        # Extract item_id from action_id (e.g., "purchase_bed_standard" -> "bed_standard")
        item_id = action_id[9:]  # Remove "purchase_" prefix

        # Load item metadata
        metadata = _get_item_metadata(item_id)
        price = metadata.get("price", 0)
        if not metadata or price <= 0:
            _log(state, "action.failed", action_id=action_id, reason="item_not_for_sale")
        else:
            quality = metadata.get("quality", 1.0)
            item_name = metadata.get("name", item_id)

            # Check if player has enough money
            if state.player.money_pence < price:
                _log(state, "action.failed", action_id=action_id, reason="insufficient_funds",
                     required_pence=price, current_pence=state.player.money_pence)
            else:
                # Deduct money
                state.player.money_pence -= price

                # Create new item with pristine condition and quality from metadata
                new_item = Item(
                    item_id=item_id,
                    condition="pristine",
                    condition_value=100,
                    placed_in=state.world.location,
                    slot="floor",  # Default slot
                    quality=quality
                )
                state.items.append(new_item)

                # Gain resource management skill
                gain = _gain_skill_xp(state, "resource_management", 0.5, current_tick)

                # Track confidence habit (making purchases builds confidence)
                _track_habit(state, "confidence", 3)

                _log(state, "shopping.purchase", item_id=item_id, item_name=item_name,
                     cost_pence=price, quality=quality, skill_gain=round(gain, 2))

    elif action_id.startswith("sell_"):
        # Extract item_id from action_id (e.g., "sell_bed_basic" -> "bed_basic")
        item_id = action_id[5:]  # Remove "sell_" prefix

        # Find the item in player's inventory at current location
        item_to_sell = None
        for item in state.items:
            if item.item_id == item_id and item.placed_in == state.world.location:
                item_to_sell = item
                break

        if item_to_sell is None:
            _log(state, "action.failed", action_id=action_id, reason="item_not_found")
        else:
            # Get item metadata to determine base price
            metadata = _get_item_metadata(item_id)
            base_price = metadata.get("price", 0)

            # Items with non-positive price cannot be sold
            if base_price <= 0:
                _log(state, "action.failed", action_id=action_id, reason="item_not_sellable")
            else:
                # Calculate sell price: 40% of base price, adjusted by condition
                condition_multiplier = item_to_sell.condition_value / 100.0
                sell_price = int(base_price * 0.4 * condition_multiplier)

                # Minimum sell price
                sell_price = max(100, sell_price)

                # Add money to player
                state.player.money_pence += sell_price

                # Remove item from state
                state.items.remove(item_to_sell)

                # Gain resource management skill
                gain = _gain_skill_xp(state, "resource_management", 0.3, current_tick)

                # Track frugality habit
                _track_habit(state, "frugality", 5)

                sold_item_id = item_to_sell.item_id
                item_name = metadata.get("name", sold_item_id) if metadata else sold_item_id

                _log(
                    state,
                    "shopping.sell",
                    item_id=sold_item_id,
                    item_name=item_name,
                    earned_pence=sell_price,
                    condition=item_to_sell.condition,
                    skill_gain=round(gain, 2),
                )

    elif action_id.startswith("discard_"):
        # Extract item_id from action_id (e.g., "discard_bed_basic" -> "bed_basic")
        item_id = action_id[8:]  # Remove "discard_" prefix

        # Find the item in player's inventory at current location
        item_to_discard = None
        for item in state.items:
            if item.item_id == item_id and item.placed_in == state.world.location:
                item_to_discard = item
                break

        if item_to_discard is None:
            _log(state, "action.failed", action_id=action_id, reason="item_not_found")
        else:
            # Get item metadata for display name
            metadata = _get_item_metadata(item_id)
            item_name = metadata.get("name", item_id) if metadata else item_id

            # Remove item from state (no money given)
            state.items.remove(item_to_discard)

            # Track minimalism habit (decluttering)
            _track_habit(state, "minimalism", 2)

            _log(
                state,
                "shopping.discard",
                item_id=item_id,
                item_name=item_name,
                condition=item_to_discard.condition,
            )

    else:
        _log(state, "action.unknown", action_id=action_id)

    _advance_time(state)
    _apply_environment(state, rng)


def to_debug_dict(state: State) -> Dict:
    return asdict(state)


def generate_skill_recap(state: State) -> List[Dict]:
    recap = []
    for skill_name in SKILL_NAMES:
        skill = _get_skill(state, skill_name)
        if skill.value > 0:
            aptitude_name = SKILL_TO_APTITUDE[skill_name]
            aptitude_value = getattr(state.player.aptitudes, aptitude_name)
            recap.append({
                "skill": skill_name.replace("_", " ").title(),
                "value": round(skill.value, 2),
                "aptitude": aptitude_name.replace("_", " ").title(),
                "aptitude_value": round(aptitude_value, 3),
            })
    return recap
