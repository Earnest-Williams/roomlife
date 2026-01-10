from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Utilities:
    power: bool = True
    heat: bool = True
    water: bool = True


@dataclass
class Needs:
    hunger: int = 40     # 0..100 (higher = more hungry)
    fatigue: int = 20    # 0..100
    warmth: int = 70     # 0..100
    hygiene: int = 60    # 0..100
    mood: int = 60       # 0..100
    stress: int = 0      # 0..100 (higher = more stressed)
    energy: int = 80     # 0..100 (affected by Fitness trait)


@dataclass
class Skill:
    value: float = 0.0
    rust_rate: float = 0.5
    last_tick: int = 0


@dataclass
class Aptitudes:
    logic_systems: float = 1.0
    social_grace: float = 1.0
    domesticity: float = 1.0
    vitality: float = 1.0


@dataclass
class Traits:
    discipline: int = 50      # 0..100
    confidence: int = 50
    empathy: int = 50
    fitness: int = 50
    frugality: int = 50
    curiosity: int = 50
    stoicism: int = 50
    creativity: int = 50


@dataclass
class Item:
    item_id: str
    condition: str = "used"     # pristine/used/worn/broken/filthy
    placed_in: str = "room_001"
    slot: str = "floor"         # logical slot, not coordinates


@dataclass
class Space:
    space_id: str
    name: str
    kind: str
    base_temperature_c: int
    has_window: bool
    connections: List[str] = field(default_factory=list)


@dataclass
class Player:
    money_pence: int = 5000
    utilities_paid: bool = True
    needs: Needs = field(default_factory=Needs)
    skills: Dict[str, int] = field(default_factory=lambda: {"general": 0})
    relationships: Dict[str, int] = field(default_factory=dict)
    aptitudes: Aptitudes = field(default_factory=Aptitudes)
    traits: Traits = field(default_factory=Traits)
    technical_literacy: Skill = field(default_factory=Skill)
    analysis: Skill = field(default_factory=Skill)
    resource_management: Skill = field(default_factory=Skill)
    presence: Skill = field(default_factory=Skill)
    articulation: Skill = field(default_factory=Skill)
    persuasion: Skill = field(default_factory=Skill)
    nutrition: Skill = field(default_factory=Skill)
    maintenance: Skill = field(default_factory=Skill)
    ergonomics: Skill = field(default_factory=Skill)
    reflexivity: Skill = field(default_factory=Skill)
    introspection: Skill = field(default_factory=Skill)
    focus: Skill = field(default_factory=Skill)
    habit_tracker: Dict[str, int] = field(default_factory=dict)


@dataclass
class World:
    day: int = 1
    slice: str = "morning"       # morning/afternoon/evening/night
    location: str = "room_001"


@dataclass
class State:
    schema_version: int = 1
    world: World = field(default_factory=World)
    player: Player = field(default_factory=Player)
    utilities: Utilities = field(default_factory=Utilities)
    spaces: Dict[str, Space] = field(default_factory=dict)
    items: List[Item] = field(default_factory=list)
    event_log: List[dict] = field(default_factory=list)
