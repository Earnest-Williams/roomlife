from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict

import yaml

from .constants import SKILL_NAMES
from .content_specs import load_spaces
from .models import (
    Aptitudes,
    Item,
    Needs,
    Player,
    Skill,
    Space,
    State,
    Traits,
    Utilities,
    World,
    generate_instance_id,
)


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
        # Initialize all skills with defaults first
        skills = {skill_name: Skill() for skill_name in SKILL_NAMES}
        # Then update with loaded values (this ensures all skills exist)
        for name, data in raw["skills_detailed"].items():
            if name in SKILL_NAMES:  # Only load known skills
                skills[name] = Skill(**data)
        return skills

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
        carry_capacity=p.get("carry_capacity", 12),
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
    data_dir = Path(__file__).parent.parent.parent / "data"
    spaces_path = data_dir / "spaces.yaml"
    if spaces_path.exists():
        try:
            specs = load_spaces(spaces_path)
        except ValueError as exc:
            print(f"Warning: Failed to load spaces.yaml while loading state: {exc}")
            specs = {}
        for space_id, spec in specs.items():
            space = s.spaces.get(space_id)
            if space is None:
                continue
            if not space.tags:
                space.tags = list(spec.tags)
            if not space.fixtures:
                space.fixtures = list(spec.fixtures)
            if not space.utilities_available:
                space.utilities_available = list(spec.utilities_available)
    items = []
    for it in raw["items"]:
        item_data = dict(it)
        item_data.setdefault("instance_id", generate_instance_id())
        item_data.setdefault("container", None)
        item_data.setdefault("bulk", 1)
        item_data.setdefault("quality", 1.0)
        item_data.setdefault("slot", "floor")
        items.append(Item(**item_data))
    s.items = items
    s.event_log = list(raw["event_log"])
    return s
