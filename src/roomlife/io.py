from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict

import yaml

from .constants import SKILL_NAMES
from .models import Aptitudes, Item, Needs, Player, Skill, Space, State, Traits, Utilities, World


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(asdict(state), default_flow_style=False, sort_keys=True), encoding="utf-8"
    )


def _load_skill(raw: dict, skill_name: str) -> Skill:
    """Load a single skill from raw dict (for backward compatibility)."""
    if skill_name in raw:
        return Skill(**raw[skill_name])
    return Skill()


def _load_skills_detailed(raw: dict) -> Dict[str, Skill]:
    """Load all skills from dict (optimized approach)."""
    # Check if new format (skills_detailed dict) exists
    if "skills_detailed" in raw:
        return {name: Skill(**data) for name, data in raw["skills_detailed"].items()}

    # Backward compatibility: load from individual fields
    skills = {}
    for skill_name in SKILL_NAMES:
        skills[skill_name] = _load_skill(raw, skill_name)
    return skills


def load_state(path: Path) -> State:
    """Load state from YAML file (optimized with dict-based skill loading)."""
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
        skills_detailed=_load_skills_detailed(p),
        habit_tracker=dict(p.get("habit_tracker", {})),
    )
    s.utilities = Utilities(**raw["utilities"])
    s.spaces = {k: Space(**v) for k, v in raw["spaces"].items()}
    s.items = [Item(**it) for it in raw["items"]]
    s.event_log = list(raw["event_log"])
    return s
