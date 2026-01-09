from __future__ import annotations

import random
from dataclasses import asdict
from typing import Dict

from .models import Item, Space, State

TIME_SLICES = ["morning", "afternoon", "evening", "night"]


def _log(state: State, event_id: str, **params: object) -> None:
    state.event_log.append({"event_id": event_id, "params": params})


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
    if not state.player.utilities_paid:
        state.utilities.power = False
        state.utilities.heat = False
    else:
        state.utilities.power = True
        state.utilities.heat = True

    n = state.player.needs
    n.hunger = min(100, n.hunger + 8)
    n.fatigue = min(100, n.fatigue + 6)
    n.hygiene = max(0, n.hygiene - 4)

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

    if action_id == "work":
        state.player.money_pence += 3500
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + 15)
        state.player.needs.mood = max(0, state.player.needs.mood - 2)
        state.player.skills["general"] = state.player.skills.get("general", 0) + 1
        _log(state, "action.work", earned_pence=3500)

    elif action_id == "study":
        state.player.needs.fatigue = min(100, state.player.needs.fatigue + 10)
        state.player.needs.mood = min(100, state.player.needs.mood + 1)
        state.player.skills["general"] = state.player.skills.get("general", 0) + 2
        _log(state, "action.study", gained_skill=2)

    elif action_id == "sleep":
        state.player.needs.fatigue = max(0, state.player.needs.fatigue - 35)
        state.player.needs.mood = min(100, state.player.needs.mood + 3)
        _log(state, "action.sleep")

    elif action_id == "eat_charity_rice":
        state.player.needs.hunger = max(0, state.player.needs.hunger - 25)
        state.player.needs.mood = max(0, state.player.needs.mood - 1)
        _log(state, "food.eat", meal_id="charity_rice")

    elif action_id == "pay_utilities":
        cost = 2000
        if state.player.money_pence >= cost:
            state.player.money_pence -= cost
            state.player.utilities_paid = True
            _log(state, "bills.paid", cost_pence=cost)
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
