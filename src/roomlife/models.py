from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional
from uuid import uuid4

from .constants import MAX_EVENT_LOG, SKILL_NAMES


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
    health: int = 100    # 0..100 (higher = healthier)
    illness: int = 0     # 0..100 (higher = more ill)
    injury: int = 0      # 0..100 (higher = more injured)


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
    instance_id: str
    item_id: str
    placed_in: str
    container: Optional[str]
    slot: str
    quality: float
    condition: str = "used"     # pristine/used/worn/broken/filthy
    condition_value: int = 80   # 0-100 numeric condition
    bulk: int = 1               # how “big” it is to carry


@dataclass
class Space:
    space_id: str
    name: str
    kind: str
    base_temperature_c: int
    has_window: bool
    connections: List[str] = field(default_factory=list)
    # Extended fields for data-driven action system
    tags: List[str] = field(default_factory=list)
    fixtures: List[str] = field(default_factory=list)
    utilities_available: List[str] = field(default_factory=list)


def _default_skills_detailed() -> Dict[str, Skill]:
    """Create default skills dictionary."""
    return {skill_name: Skill() for skill_name in SKILL_NAMES}


@dataclass
class NPC:
    """Building NPC contact (neighbor/landlord/maintenance, NOT roommates).

    NPCs are off-screen contacts that interact with the player via hallway/door/building events.
    They are "player-shaped enough" for tier computation to work, but have minimal inventory/economy.
    """
    id: str
    display_name: str
    role: str  # "neighbor", "landlord", "maintenance"

    # Skills/traits needed for tier computation when NPC is the actor
    skills_detailed: Dict[str, Skill] = field(default_factory=_default_skills_detailed)
    aptitudes: Aptitudes = field(default_factory=Aptitudes)
    traits: Traits = field(default_factory=Traits)

    # Social state
    relationships: Dict[str, int] = field(default_factory=dict)  # {target_id: -100 to +100}
    memory: List[Dict[str, Any]] = field(default_factory=list)  # Bounded list of interactions
    flags: Dict[str, Any] = field(default_factory=dict)  # Cooldowns, schedule, etc.


@dataclass
class Player:
    money_pence: int = 5000
    utilities_paid: bool = True
    current_job: str = "recycling_collector"  # Job system - start with worst job
    carry_capacity: int = 12
    needs: Needs = field(default_factory=Needs)
    skills: Dict[str, int] = field(default_factory=lambda: {"general": 0})
    relationships: Dict[str, int] = field(default_factory=dict)
    aptitudes: Aptitudes = field(default_factory=Aptitudes)
    traits: Traits = field(default_factory=Traits)
    skills_detailed: Dict[str, Skill] = field(default_factory=_default_skills_detailed)
    habit_tracker: Dict[str, int] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)
    memory: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class World:
    day: int = 1
    slice: str = "morning"       # morning/afternoon/evening/night
    location: str = "room_001"
    rng_seed: int = 0            # Simulation seed for deterministic NPCs/director
    rng: random.Random = field(default_factory=random.Random)  # Reusable RNG instance


@dataclass
class State:
    schema_version: int = 2  # Bumped for NPC + flags + memory support
    world: World = field(default_factory=World)
    player: Player = field(default_factory=Player)
    utilities: Utilities = field(default_factory=Utilities)
    spaces: Dict[str, Space] = field(default_factory=dict)
    items: List[Item] = field(default_factory=list)
    event_log: Deque[dict] = field(default_factory=lambda: deque(maxlen=MAX_EVENT_LOG))
    npcs: Dict[str, NPC] = field(default_factory=dict)  # Building NPCs by id

    def get_items_at(self, location: str) -> List[Item]:
        """Get all items at a specific location (optimized spatial query)."""
        return [item for item in self.items if item.placed_in == location]


def generate_instance_id(rng: Optional[random.Random] = None) -> str:
    """Generate a unique instance ID for an item.

    Args:
        rng: Optional random number generator for deterministic ID generation.
             If None, uses uuid4() for true randomness.

    Returns:
        A unique instance ID string.
    """
    if rng is not None:
        # Use deterministic random hex string
        hex_str = ''.join(rng.choice('0123456789abcdef') for _ in range(8))
        return f"it_{hex_str}"
    else:
        return f"it_{uuid4().hex[:8]}"


def inventory_bulk(state: State) -> int:
    return sum(it.bulk for it in state.items if it.placed_in == "inventory")


def can_carry(state: State, added_bulk: int) -> bool:
    return inventory_bulk(state) + added_bulk <= state.player.carry_capacity
