from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from .models import Item, Needs, Player, Space, State, Utilities, World


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(asdict(state), default_flow_style=False, sort_keys=True), encoding="utf-8"
    )


def load_state(path: Path) -> State:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

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
