"""Type definitions for the RoomLife visualization API.

This module defines all request and response types for the API,
making it easy to integrate with various UI/UX engines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionCategory(str, Enum):
    """Categories for grouping actions in UI."""
    WORK = "work"
    SURVIVAL = "survival"
    MAINTENANCE = "maintenance"
    HEALTH = "health"
    MOVEMENT = "movement"
    SOCIAL = "social"
    SHOPPING = "shopping"
    INVENTORY = "inventory"
    OTHER = "other"


@dataclass
class NeedsSnapshot:
    """Current player needs (0-100 scale)."""
    hunger: int
    fatigue: int
    warmth: int
    hygiene: int
    mood: int
    stress: int
    energy: int
    health: int
    illness: int
    injury: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class SkillInfo:
    """Information about a specific skill."""
    name: str
    value: float
    rust_rate: float
    last_tick: int
    aptitude: str
    aptitude_value: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraitsSnapshot:
    """Current player traits (0-100 scale)."""
    discipline: int
    confidence: int
    empathy: int
    fitness: int
    frugality: int
    curiosity: int
    stoicism: int
    creativity: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass
class UtilitiesSnapshot:
    """Current utilities status."""
    power: bool
    heat: bool
    water: bool

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


@dataclass
class LocationInfo:
    """Information about a location/space."""
    space_id: str
    name: str
    kind: str
    base_temperature_c: int
    has_window: bool
    connections: List[str]
    items: List[ItemInfo]

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class ItemInfo:
    """Information about an item."""
    instance_id: str
    item_id: str
    condition: str
    condition_value: int
    placed_in: str
    slot: str
    container: Optional[str] = None
    bulk: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorldInfo:
    """Current world/time state."""
    day: int
    slice: str
    location: str
    current_tick: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventInfo:
    """Information about a logged event."""
    event_id: str
    params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GameStateSnapshot:
    """Complete snapshot of the game state for visualization."""
    world: WorldInfo
    player_money_pence: int
    utilities_paid: bool
    needs: NeedsSnapshot
    traits: TraitsSnapshot
    utilities: UtilitiesSnapshot
    skills: List[SkillInfo]
    aptitudes: Dict[str, float]
    habit_tracker: Dict[str, int]
    current_location: LocationInfo
    all_locations: Dict[str, LocationInfo]
    recent_events: List[EventInfo]
    schema_version: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "world": self.world.to_dict(),
            "player_money_pence": self.player_money_pence,
            "utilities_paid": self.utilities_paid,
            "needs": self.needs.to_dict(),
            "traits": self.traits.to_dict(),
            "utilities": self.utilities.to_dict(),
            "skills": [skill.to_dict() for skill in self.skills],
            "aptitudes": self.aptitudes,
            "habit_tracker": self.habit_tracker,
            "current_location": self.current_location.to_dict(),
            "all_locations": {k: v.to_dict() for k, v in self.all_locations.items()},
            "recent_events": [event.to_dict() for event in self.recent_events],
            "schema_version": self.schema_version,
        }


@dataclass
class ActionMetadata:
    """Metadata about an available action."""
    action_id: str
    display_name: str
    description: str
    category: ActionCategory
    requirements: Dict[str, Any]
    effects: Dict[str, str]
    cost_pence: Optional[int] = None
    requires_location: Optional[str] = None
    requires_utilities: Optional[List[str]] = None
    requires_items: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None
    available: bool = True
    why_locked: Optional[str] = None
    missing_requirements: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionValidation:
    """Result of action validation."""
    valid: bool
    action_id: str
    reason: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)
    preview: Optional["ActionPreview"] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.preview is not None:
            data["preview"] = self.preview.to_dict()
        return data


@dataclass
class ActionPreview:
    """Preview information for action outcomes."""
    tier_distribution: Dict[int, float]
    delta_ranges: Dict[str, Any]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    action_id: str
    new_state: GameStateSnapshot
    events_triggered: List[EventInfo]
    state_changes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "new_state": self.new_state.to_dict(),
            "events_triggered": [event.to_dict() for event in self.events_triggered],
            "state_changes": self.state_changes,
        }


@dataclass
class AvailableActionsResponse:
    """List of currently available actions."""
    actions: List[ActionMetadata]
    location: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "location": self.location,
            "total_count": self.total_count,
        }
