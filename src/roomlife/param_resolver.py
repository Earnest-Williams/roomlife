from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import Item, State, can_carry, inventory_bulk


def resolve_param_space_id(state: State, value: Any) -> Tuple[bool, str]:
    if not isinstance(value, str):
        return False, "target_space must be a string"
    if value not in state.spaces:
        return False, f"unknown space_id: {value}"
    return True, ""


def _find_item_candidates(state: State, item_ref: Dict[str, Any]) -> List[Item]:
    mode = item_ref.get("mode")
    if mode == "instance_id":
        iid = item_ref.get("instance_id")
        if not isinstance(iid, str):
            return []
        return [it for it in state.items if getattr(it, "instance_id", None) == iid]
    if mode == "by_item_id":
        item_id = item_ref.get("item_id")
        if not isinstance(item_id, str):
            return []
        return [it for it in state.items if it.item_id == item_id]
    return []


def resolve_param_item_ref(state: State, value: Any) -> Tuple[bool, str]:
    if not isinstance(value, dict):
        return False, "item_ref must be an object"

    mode = value.get("mode")
    if mode == "instance_id":
        iid = value.get("instance_id")
        if not isinstance(iid, str):
            return False, "instance_id must be string"
        if not any(getattr(it, "instance_id", None) == iid for it in state.items):
            return False, f"unknown instance_id: {iid}"
        return True, ""

    if mode == "by_item_id":
        item_id = value.get("item_id")
        if not isinstance(item_id, str):
            return False, "item_id must be string"
        if not any(it.item_id == item_id for it in state.items):
            return False, f"no such item_id in world: {item_id}"
        return True, ""

    return False, "item_ref.mode must be instance_id or by_item_id"


def is_item_reachable(state: State, it: Item) -> bool:
    return it.placed_in == "inventory" or it.placed_in == state.world.location


def _validate_item_constraints(
    state: State,
    item_ref: Dict[str, Any],
    constraints: Dict[str, Any],
) -> List[str]:
    issues: List[str] = []
    candidates = _find_item_candidates(state, item_ref)

    if constraints.get("reachable"):
        if not any(is_item_reachable(state, it) for it in candidates):
            issues.append("item_ref must reference a reachable item")

    if constraints.get("in_inventory"):
        if not any(it.placed_in == "inventory" for it in candidates):
            issues.append("item_ref must reference an inventory item")

    return issues


def validate_parameters(
    state: State,
    spec: Any,
    params: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    missing: List[str] = []

    # Supported parameter types
    SUPPORTED_TYPES = {"space_id", "item_ref", "string"}

    for p in spec.parameters or []:
        name = p["name"]
        if p.get("required") and name not in params:
            missing.append(f"missing param: {name}")
            continue
        if name not in params:
            continue
        ptype = p["type"]
        if ptype == "space_id":
            ok, msg = resolve_param_space_id(state, params[name])
            if not ok:
                missing.append(msg)
        elif ptype == "item_ref":
            ok, msg = resolve_param_item_ref(state, params[name])
            if not ok:
                missing.append(msg)
                continue
            constraints = p.get("constraints", {})
            missing.extend(_validate_item_constraints(state, params[name], constraints))
        elif ptype == "string":
            # String parameters just need to be present and be a string
            if not isinstance(params[name], str):
                missing.append(f"{name} must be a string")
        else:
            # Fail hard on unknown types to prevent spec drift
            missing.append(f"{name} (unknown parameter type: {ptype})")

    return (len(missing) == 0), missing


def validate_connected_to_param(
    state: State,
    param_name: str,
    params: Dict[str, Any],
) -> Tuple[bool, str]:
    target = params.get(param_name)
    if not isinstance(target, str):
        return False, f"{param_name} must be a space_id"
    current = state.world.location
    space = state.spaces.get(current)
    if not space:
        return False, "invalid current location"
    if target not in space.connections:
        return False, f"{target} not connected to {current}"
    return True, ""


def select_item_instance(state: State, item_ref: Dict[str, Any]) -> Optional[Item]:
    mode = item_ref.get("mode")
    if mode == "instance_id":
        iid = item_ref.get("instance_id")
        if not isinstance(iid, str):
            return None
        return next((it for it in state.items if it.instance_id == iid), None)
    if mode == "by_item_id":
        item_id = item_ref.get("item_id")
        if not isinstance(item_id, str):
            return None
        candidates = [
            it for it in state.items
            if it.item_id == item_id and is_item_reachable(state, it)
        ]
        candidates.sort(key=lambda it: it.condition_value, reverse=True)
        return candidates[0] if candidates else None
    return None


def apply_pickup(state: State, it: Item) -> Tuple[bool, str]:
    if it.placed_in != state.world.location:
        return False, "item not at current location"
    if not can_carry(state, it.bulk):
        return False, f"inventory full ({inventory_bulk(state)}/{state.player.carry_capacity})"
    it.placed_in = "inventory"
    it.slot = "inventory"
    return True, ""


def apply_drop(state: State, it: Item) -> Tuple[bool, str]:
    if it.placed_in != "inventory":
        return False, "item not in inventory"
    it.placed_in = state.world.location
    it.slot = "floor"
    return True, ""
