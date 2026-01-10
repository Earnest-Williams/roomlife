from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from .models import Aptitudes, Item, Needs, Player, Skill, Space, State, Traits, Utilities, World


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(asdict(state), default_flow_style=False, sort_keys=True), encoding="utf-8"
    )


def _load_skill(raw: dict, skill_name: str) -> Skill:
    if skill_name in raw:
        return Skill(**raw[skill_name])
    return Skill()


def load_state(path: Path) -> State:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    s = State(schema_version=raw["schema_version"])
    s.world = World(**raw["world"])
    p = raw["player"]
    s.player = Player(
        money_pence=p["money_pence"],
        utilities_paid=p["utilities_paid"],
        needs=Needs(**p["needs"]),
        skills=dict(p["skills"]),
        relationships=dict(p["relationships"]),
        aptitudes=Aptitudes(**p.get("aptitudes", {})),
        traits=Traits(**p.get("traits", {})),
        technical_literacy=_load_skill(p, "technical_literacy"),
        analysis=_load_skill(p, "analysis"),
        resource_management=_load_skill(p, "resource_management"),
        presence=_load_skill(p, "presence"),
        articulation=_load_skill(p, "articulation"),
        persuasion=_load_skill(p, "persuasion"),
        nutrition=_load_skill(p, "nutrition"),
        maintenance=_load_skill(p, "maintenance"),
        ergonomics=_load_skill(p, "ergonomics"),
        reflexivity=_load_skill(p, "reflexivity"),
        introspection=_load_skill(p, "introspection"),
        focus=_load_skill(p, "focus"),
        habit_tracker=dict(p.get("habit_tracker", {})),
    )
    s.utilities = Utilities(**raw["utilities"])
    s.spaces = {k: Space(**v) for k, v in raw["spaces"].items()}
    s.items = [Item(**it) for it in raw["items"]]
    s.event_log = list(raw["event_log"])
    return s
