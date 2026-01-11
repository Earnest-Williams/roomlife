from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class ActionCall:
    action_id: str
    params: Dict[str, Any]

    @staticmethod
    def from_legacy(action_id: str) -> "ActionCall":
        if action_id.startswith("move_"):
            return ActionCall("move", {"target_space": action_id[len("move_"):]})
        if action_id.startswith("repair_"):
            return ActionCall(
                "repair_item",
                {"item_ref": {"mode": "by_item_id", "item_id": action_id[len("repair_"):]}},
            )
        return ActionCall(action_id, {})
