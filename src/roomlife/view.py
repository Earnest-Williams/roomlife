from __future__ import annotations

from pathlib import Path
from typing import Dict

from .action_call import ActionCall
from .catalog import ActionCatalog
from .constants import SKILL_NAMES
from .content_specs import load_actions, load_item_meta
from .models import State

# Global cache for specs (loaded once)
_ACTION_SPECS = None
_ITEM_META = None


def _ensure_specs_loaded():
    """Lazy load action specs and item metadata."""
    global _ACTION_SPECS, _ITEM_META
    data_dir = Path(__file__).parent.parent.parent / "data"

    if _ACTION_SPECS is None:
        actions_path = data_dir / "actions.yaml"
        if actions_path.exists():
            _ACTION_SPECS = load_actions(actions_path)
        else:
            _ACTION_SPECS = {}
    if _ITEM_META is None:
        items_path = data_dir / "items_meta.yaml"
        if items_path.exists():
            _ITEM_META = load_item_meta(items_path)
        else:
            _ITEM_META = {}


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

    # Build actions list from ActionCatalog
    _ensure_specs_loaded()
    catalog = ActionCatalog(_ACTION_SPECS, _ITEM_META)
    action_cards = catalog.list_available(state)

    # Convert ActionCards to hint format
    actions_hint = []
    for card in action_cards:
        # Convert ActionCall to legacy format for backwards compatibility
        if card.call.action_id == "move" and "target_space" in card.call.params:
            # Legacy format for move actions
            action_id = f"move_{card.call.params['target_space']}"
        elif card.call.params:
            # For parameterized actions, we need to serialize them somehow
            # For now, skip showing them as simple hints (they'll be in the full action list)
            continue
        else:
            action_id = card.call.action_id

        actions_hint.append({
            "id": action_id,
            "label": card.display_name,
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
                "health": n.health,
                "illness": n.illness,
                "injury": n.injury,
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
