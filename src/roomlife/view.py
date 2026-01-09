from __future__ import annotations

from typing import Dict

from .models import State


def build_view_model(state: State) -> Dict:
    n = state.player.needs
    loc = state.world.location
    space = state.spaces.get(loc)

    return {
        "time": {"day": state.world.day, "slice": state.world.slice},
        "player": {
            "money_pence": state.player.money_pence,
            "utilities_paid": state.player.utilities_paid,
            "needs": {
                "hunger": n.hunger,
                "fatigue": n.fatigue,
                "warmth": n.warmth,
                "hygiene": n.hygiene,
                "mood": n.mood,
            },
            "skills": dict(state.player.skills),
        },
        "utilities": {
            "power": state.utilities.power,
            "heat": state.utilities.heat,
            "water": state.utilities.water,
        },
        "location": {"space_id": loc, "space_name": space.name if space else loc},
        "items_here": [
            {"item_id": it.item_id, "condition": it.condition, "slot": it.slot}
            for it in state.items
            if it.placed_in == loc
        ],
        "recent_events": state.event_log[-6:],
        "actions_hint": [
            {"id": "work", "label": "Work a shift"},
            {"id": "study", "label": "Study"},
            {"id": "sleep", "label": "Sleep"},
            {"id": "eat_charity_rice", "label": "Eat charity rice"},
            {"id": "pay_utilities", "label": "Pay utilities"},
            {"id": "skip_utilities", "label": "Skip utilities"},
        ],
    }
