from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict, List, Tuple

from .constants import (
    MAX_EVENT_LOG,
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
    actual_gain = gain * curiosity_mod
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
    return state.world.day * 4 + TIME_SLICES.index(state.world.slice)


def new_game() -> State:
    state = State()
    state.spaces = {
        "room_001": Space("room_001", "Tiny room", "room", 14, False, ["hall_001"]),
        "hall_001": Space("hall_001", "Hallway", "shared", 12, False, ["room_001", "bath_001"]),
        "bath_001": Space("bath_001", "Shared bathroom", "shared", 13, False, ["hall_001"]),
    }
    state.items = [
        Item("bed_basic", condition="used", placed_in="room_001", slot="floor"),
        Item("desk_worn", condition="worn", placed_in="room_001", slot="wall"),
        Item("kettle", condition="used", placed_in="room_001", slot="surface"),
    ]
    _log(state, "game.start", day=state.world.day, slice=state.world.slice)
    return state


def _advance_time(state: State) -> None:
    idx = TIME_SLICES.index(state.world.slice)
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

    if rng.random() < 0.05:
        _log(state, "building.noise", severity="low")


def apply_action(state: State, action_id: str, rng_seed: int = 1) -> None:
    rng = random.Random(rng_seed + state.world.day * 97 + TIME_SLICES.index(state.world.slice))
    current_tick = _calculate_current_tick(state)

    if action_id == "work":
        state.player.money_pence += 3500
        fatigue_cost = 15
        discipline_mod = 1.0 - (state.player.traits.discipline / 100.0) * 0.2
        fatigue_cost = int(fatigue_cost * discipline_mod)
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)
        state.player.needs.mood = max(0, state.player.needs.mood - 2)
        state.player.skills["general"] = state.player.skills.get("general", 0) + 1
        gain = _gain_skill_xp(state, "technical_literacy", 2.0, current_tick)
        _track_habit(state, "discipline", 10)
        _log(state, "action.work", earned_pence=3500, skill_gain=round(gain, 2))

    elif action_id == "study":
        fatigue_base = 10
        ergonomics_bonus = _get_skill(state, "ergonomics").value * 0.1
        fatigue_cost = int(fatigue_base * (1.0 - ergonomics_bonus))
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + fatigue_cost)
        state.player.needs.mood = min(100, state.player.needs.mood + 1)
        state.player.skills["general"] = state.player.skills.get("general", 0) + 2
        gain = _gain_skill_xp(state, "focus", 3.0, current_tick)
        _track_habit(state, "discipline", 15)
        _log(state, "action.study", skill_gain=round(gain, 2))

    elif action_id == "sleep":
        base_recovery = 35
        fitness_bonus = state.player.traits.fitness / 100.0 * 10
        total_recovery = int(base_recovery + fitness_bonus)
        state.player.needs.fatigue = max(0, state.player.needs.fatigue - total_recovery)
        state.player.needs.mood = min(100, state.player.needs.mood + 3)
        introspection_stress_reduction = _get_skill(state, "introspection").value * 0.5
        state.player.needs.stress = max(0, int(state.player.needs.stress - introspection_stress_reduction))
        _log(state, "action.sleep", fatigue_recovered=total_recovery)

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
