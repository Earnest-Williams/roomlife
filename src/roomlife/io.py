from __future__ import annotations

import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict

import yaml

from .constants import MAX_EVENT_LOG, SKILL_NAMES
from .content_specs import load_spaces
from .models import (
    Aptitudes,
    EventLog,
    Item,
    Needs,
    NPC,
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
    """Save game state to YAML file, excluding non-serializable fields."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert state to dict and handle non-serializable fields
    state_dict = asdict(state)

    # Remove RNG instance (non-serializable)
    if "world" in state_dict and "rng" in state_dict["world"]:
        del state_dict["world"]["rng"]

    # Convert deque to list for serialization
    if "event_log" in state_dict:
        state_dict["event_log"] = list(state_dict["event_log"])

    path.write_text(
        yaml.safe_dump(state_dict, default_flow_style=False, sort_keys=True), encoding="utf-8"
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

    # Load World and recreate RNG from seed
    world_data = raw["world"]
    s.world = World(**world_data)
    s.world.rng = random.Random(s.world.rng_seed)
    p = raw["player"]
    s.player = Player(
        money_pence=p["money_pence"],
        utilities_paid=p["utilities_paid"],
        current_job=p.get("current_job", "recycling_collector"),
        carry_capacity=p.get("carry_capacity", 12),
        needs=Needs(**p["needs"]),
        skills=dict(p["skills"]),
        relationships=dict(p["relationships"]),
        aptitudes=Aptitudes(**p.get("aptitudes", {})),
        traits=Traits(**p.get("traits", {})),
        skills_detailed=_load_skills_detailed(p),
        habit_tracker=dict(p.get("habit_tracker", {})),
        flags=dict(p.get("flags", {})),
        memory=list(p.get("memory", [])),
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

    # Load event_log as bounded deque (maintains maxlen behavior from State definition)
    s.event_log = EventLog(raw["event_log"], maxlen=MAX_EVENT_LOG)

    s.npcs = {}
    for npc_id, npc_data in (raw.get("npcs") or {}).items():
        s.npcs[npc_id] = NPC(
            id=npc_data.get("id", npc_id),
            display_name=npc_data.get("display_name", npc_id),
            role=npc_data.get("role", "neighbor"),
            skills_detailed=_load_skills_detailed(npc_data),
            aptitudes=Aptitudes(**npc_data.get("aptitudes", {})),
            traits=Traits(**npc_data.get("traits", {})),
            relationships=dict(npc_data.get("relationships", {})),
            memory=list(npc_data.get("memory", [])),
            flags=dict(npc_data.get("flags", {})),
        )
    return s
