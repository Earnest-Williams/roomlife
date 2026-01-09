from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Item, Needs, Player, Space, State, Utilities, World


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


def load_state(path: Path) -> State:
    raw = json.loads(path.read_text(encoding="utf-8"))

    s = State(schema_version=raw["schema_version"])
    s.world = World(**raw["world"])
    s.player = Player(
        money_pence=raw["player"]["money_pence"],
        utilities_paid=raw["player"]["utilities_paid"],
        needs=Needs(**raw["player"]["needs"]),
        skills=dict(raw["player"]["skills"]),
        relationships=dict(raw["player"]["relationships"]),
    )
    s.utilities = Utilities(**raw["utilities"])
    s.spaces = {k: Space(**v) for k, v in raw["spaces"].items()}
    s.items = [Item(**it) for it in raw["items"]]
    s.event_log = list(raw["event_log"])
    return s
