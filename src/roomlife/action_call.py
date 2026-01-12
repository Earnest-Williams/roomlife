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
        if action_id.startswith("purchase_"):
            return ActionCall("purchase_item", {"item_id": action_id[len("purchase_"):]})
        if action_id.startswith("sell_"):
            return ActionCall("sell_item", {"item_id": action_id[len("sell_"):]})
        if action_id.startswith("discard_"):
            return ActionCall("discard_item", {"item_id": action_id[len("discard_"):]})
        if action_id.startswith("apply_job_"):
            return ActionCall("apply_job", {"job_id": action_id[len("apply_job_"):]})
        return ActionCall(action_id, {})
