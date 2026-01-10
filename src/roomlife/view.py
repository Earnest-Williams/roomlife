from __future__ import annotations

from typing import Dict

from .constants import SKILL_NAMES
from .models import State


def build_view_model(state: State) -> Dict:
    """Build view-model from state (optimized with dict-based skill access)."""
    n = state.player.needs
    loc = state.world.location
    space = state.spaces.get(loc)
    p = state.player

    # Build active skills list using dict access (faster than getattr)
    active_skills = []
    for skill_name in SKILL_NAMES:
        skill = p.skills_detailed[skill_name]
        if skill.value > 0:
            active_skills.append({
                "name": skill_name.replace("_", " ").title(),
                "value": round(skill.value, 2),
            })

    # Build actions list with movement options
    actions_hint = [
        {"id": "work", "label": "Work a shift"},
        {"id": "study", "label": "Study"},
        {"id": "sleep", "label": "Sleep"},
        {"id": "eat_charity_rice", "label": "Eat charity rice"},
        {"id": "pay_utilities", "label": "Pay utilities"},
        {"id": "skip_utilities", "label": "Skip utilities"},
        {"id": "shower", "label": "Shower"},
        {"id": "cook_basic_meal", "label": "Cook basic meal"},
        {"id": "clean_room", "label": "Clean room"},
        {"id": "exercise", "label": "Exercise"},
    ]

    # Add movement actions based on current location connections
    if space and space.connections:
        for connected_space_id in space.connections:
            connected_space = state.spaces.get(connected_space_id)
            if connected_space:
                actions_hint.append({
                    "id": f"move_{connected_space_id}",
                    "label": f"Move to {connected_space.name}"
                })

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
                "stress": n.stress,
                "energy": n.energy,
            },
            "skills": dict(state.player.skills),
            "active_skills": active_skills,
            "aptitudes": {
                "logic_systems": round(p.aptitudes.logic_systems, 3),
                "social_grace": round(p.aptitudes.social_grace, 3),
                "domesticity": round(p.aptitudes.domesticity, 3),
                "vitality": round(p.aptitudes.vitality, 3),
            },
            "traits": {
                "discipline": p.traits.discipline,
                "confidence": p.traits.confidence,
                "empathy": p.traits.empathy,
                "fitness": p.traits.fitness,
                "frugality": p.traits.frugality,
                "curiosity": p.traits.curiosity,
                "stoicism": p.traits.stoicism,
                "creativity": p.traits.creativity,
            },
        },
        "utilities": {
            "power": state.utilities.power,
            "heat": state.utilities.heat,
            "water": state.utilities.water,
        },
        "location": {"space_id": loc, "space_name": space.name if space else loc},
        # Use optimized spatial query instead of filtering all items
        "items_here": [
            {"item_id": it.item_id, "condition": it.condition, "slot": it.slot}
            for it in state.get_items_at(loc)
        ],
        "recent_events": state.event_log[-6:],
        "actions_hint": actions_hint,
    }
