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
        cards.extend(self._list_pickup_actions(state))
        cards.extend(self._list_drop_actions(state))
        cards.extend(self._list_purchase_actions(state))
        cards.extend(self._list_sell_actions(state))
        cards.extend(self._list_discard_actions(state))
        cards.extend(self._list_apply_job_actions(state))

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

    def _list_pickup_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("pick_up_item")
        if spec is None:
            return cards

        here = state.world.location
        for item in state.items:
            if item.placed_in != here:
                continue

            call = ActionCall(
                "pick_up_item",
                {"item_ref": {"mode": "instance_id", "instance_id": item.instance_id}},
            )
            ok, reason, missing = self._validate_call(state, call)

            # Use item_meta for nicer names if available
            meta = self.item_meta.get(item.item_id)
            item_name = meta.name if meta else item.item_id.replace("_", " ").title()

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Pick up {item_name}",
                    description=spec.description,
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        return cards

    def _list_drop_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("drop_item")
        if spec is None:
            return cards

        for item in state.items:
            if item.placed_in != "inventory":
                continue

            call = ActionCall(
                "drop_item",
                {"item_ref": {"mode": "instance_id", "instance_id": item.instance_id}},
            )
            ok, reason, missing = self._validate_call(state, call)

            # Use item_meta for nicer names if available
            meta = self.item_meta.get(item.item_id)
            item_name = meta.name if meta else item.item_id.replace("_", " ").title()

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Drop {item_name}",
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

    def _list_purchase_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("purchase_item")
        if spec is None:
            return cards

        # List all purchasable items (items with price > 0)
        for item_id, meta in self.item_meta.items():
            if meta.price <= 0:
                continue

            call = ActionCall("purchase_item", {"item_id": item_id})
            ok, reason, missing = self._validate_call(state, call)

            # Check if player has enough money
            if state.player.money_pence < meta.price:
                ok = False
                missing.append(f"need {meta.price}p (have {state.player.money_pence}p)")

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Purchase {meta.name}",
                    description=f"{meta.description or ''} (Cost: {meta.price}p)",
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        return cards

    def _list_sell_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("sell_item")
        if spec is None:
            return cards

        # List items at current location that can be sold
        items_here = state.get_items_at(state.world.location)
        seen_item_ids = set()

        for item in items_here:
            # Only list each item_id once
            if item.item_id in seen_item_ids:
                continue

            meta = self.item_meta.get(item.item_id)
            if not meta or meta.price <= 0:
                continue

            seen_item_ids.add(item.item_id)

            # Calculate sell price
            condition_multiplier = item.condition_value / 100.0
            sell_price = int(meta.price * 0.4 * condition_multiplier)
            sell_price = max(100, sell_price)

            call = ActionCall("sell_item", {"item_id": item.item_id})
            ok, reason, missing = self._validate_call(state, call)

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Sell {meta.name}",
                    description=f"Sell for ~{sell_price}p (condition: {item.condition})",
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        return cards

    def _list_discard_actions(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []
        spec = self.specs.get("discard_item")
        if spec is None:
            return cards

        # List items at current location
        items_here = state.get_items_at(state.world.location)
        seen_item_ids = set()

        for item in items_here:
            # Only list each item_id once
            if item.item_id in seen_item_ids:
                continue

            seen_item_ids.add(item.item_id)

            meta = self.item_meta.get(item.item_id)
            item_name = meta.name if meta else item.item_id.replace("_", " ").title()

            call = ActionCall("discard_item", {"item_id": item.item_id})
            ok, reason, missing = self._validate_call(state, call)

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Discard {item_name}",
                    description="Throw away this item permanently",
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        return cards

    def _list_apply_job_actions(self, state: State) -> List[ActionCard]:
        from .constants import JOBS

        cards: List[ActionCard] = []
        spec = self.specs.get("apply_job")
        if spec is None:
            return cards

        for job_id, job_data in JOBS.items():
            # Don't show current job
            if state.player.current_job == job_id:
                continue

            call = ActionCall("apply_job", {"job_id": job_id})
            ok, reason, missing = self._validate_call(state, call)

            # Check job requirements
            from .engine import _check_job_requirements
            meets_req, req_reason = _check_job_requirements(state, job_id)
            if not meets_req:
                ok = False
                missing.append(req_reason)

            cards.append(
                ActionCard(
                    call=call,
                    display_name=f"Apply for {job_data['name']}",
                    description=f"{job_data['description']} (Pay: {job_data['base_pay']}p)",
                    available=ok,
                    why_locked=None if ok else reason,
                    missing_requirements=missing,
                )
            )

        return cards
