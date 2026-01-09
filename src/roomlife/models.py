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
