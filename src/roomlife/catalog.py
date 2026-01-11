from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .action_call import ActionCall
from .action_engine import validate_action_spec
from .content_specs import ActionSpec, ItemMeta
from .models import State


@dataclass
class ActionCard:
    call: ActionCall
    display_name: str
    description: str
    available: bool
    why_locked: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)


class ActionCatalog:
    def __init__(self, specs: Dict[str, ActionSpec], item_meta: Dict[str, ItemMeta]):
        self.specs = specs
        self.item_meta = item_meta

    def list_available(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []

        for action_id, spec in self.specs.items():
            if not self._is_listing_safe(spec):
                continue
            call = ActionCall(action_id, {})
            ok, reason, missing = self._validate_call(state, call)
            cards.append(
                ActionCard(
                    call=call,
                    display_name=spec.display_name,
                    description=spec.description,
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        cards.extend(self._list_move_actions(state))
        cards.extend(self._list_repair_actions(state))

        return cards

    def _is_listing_safe(self, spec: ActionSpec) -> bool:
        params = spec.parameters or []
        return not any(p.get("required") for p in params)

    def _list_move_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("move")
        if spec is None:
            return cards

        current = state.world.location
        if current not in state.spaces:
            return cards

        current_space = state.spaces[current]
        for nxt in current_space.connections:
            name = state.spaces[nxt].name if nxt in state.spaces else nxt
            call = ActionCall("move", {"target_space": nxt})
            ok, reason, missing = self._validate_call(state, call)
            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Move to {name}",
                    description=spec.description,
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )
        return cards

    def _list_repair_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("repair_item")
        if spec is None:
            return cards

        items_here = state.get_items_at(state.world.location)
        for item in items_here:
            call = ActionCall(
                "repair_item",
                {"item_ref": {"mode": "instance_id", "instance_id": item.instance_id}},
            )
            ok, reason, missing = self._validate_call(state, call)
            item_display_name = item.item_id.replace("_", " ").title()
            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Repair {item_display_name}",
                    description=spec.description,
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )
        return cards

    def _validate_call(
        self,
        state: State,
        call: ActionCall,
    ) -> Tuple[bool, str, List[str]]:
        spec = self.specs.get(call.action_id)
        if spec is None:
            return False, "Unknown action", ["unknown action"]
        return validate_action_spec(state, spec, self.item_meta, call.params)
