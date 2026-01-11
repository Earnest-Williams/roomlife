"""Content specification loaders for data-driven action system.

This module provides data structures and loaders for:
- ActionSpec: Defines actions with requirements, modifiers, outcomes, and consumption
- SpaceSpec: Extended space definitions with tags, fixtures, and utilities
- ItemMeta: Item capability metadata (provides, requires, durability)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass(frozen=True)
class ActionSpec:
    """Specification for a data-driven action.

    Attributes:
        id: Unique action identifier
        display_name: Human-readable action name
        description: Action description for UI
        category: Action category (survival, maintenance, other)
        time_minutes: Duration in minutes (informational)
        requires: Hard requirements dict (must be met to execute)
        modifiers: Soft modifiers dict (affect tier computation)
        outcomes: Dict mapping tier (0-3) to outcome effects
        consumes: Optional resource consumption spec
        parameters: Optional list of action parameters
        dynamic: Optional dynamic calculation formulas
    """
    id: str
    display_name: str
    description: str
    category: str
    time_minutes: int
    requires: Dict[str, Any]
    modifiers: Dict[str, Any]
    outcomes: Dict[int, Dict[str, Any]]
    consumes: Dict[str, Any] | None = None
    parameters: List[Dict[str, Any]] | None = None
    dynamic: Dict[str, Any] | None = None


@dataclass(frozen=True)
class SpaceSpec:
    """Extended specification for a game space/location.

    Attributes:
        id: Unique space identifier
        name: Display name
        kind: Space type (room, shared, bathroom, etc.)
        base_temperature_c: Base temperature in Celsius
        has_window: Whether space has a window
        connections: List of connected space IDs
        tags: Semantic tags for action validation (room, kitchen, bathroom, etc.)
        fixtures: Fixed features of the space (shower, sink, bed_spot, etc.)
        utilities_available: Which utilities are available (power, water, heat)
    """
    id: str
    name: str
    kind: str
    base_temperature_c: int
    has_window: bool
    connections: List[str]
    tags: List[str]
    fixtures: List[str]
    utilities_available: List[str]


@dataclass(frozen=True)
class ItemMeta:
    """Metadata defining item capabilities and properties.

    Attributes:
        id: Unique item identifier
        name: Display name
        tags: Legacy tags for backward compatibility
        provides: Capability list (heat_source, workspace, cleaning_kit, etc.)
        requires_utilities: Utilities needed to function (power, water, heat)
        durability: Optional durability spec with max and degrade_per_use_default
    """
    id: str
    name: str
    tags: List[str]
    provides: List[str]
    requires_utilities: List[str]
    durability: Dict[str, Any] | None = None


def load_actions(path: str | Path) -> Dict[str, ActionSpec]:
    """Load action specifications from YAML file.

    Args:
        path: Path to actions.yaml file

    Returns:
        Dict mapping action_id to ActionSpec

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is malformed
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    out: Dict[str, ActionSpec] = {}

    for a in raw.get("actions", []):
        out[a["id"]] = ActionSpec(
            id=a["id"],
            display_name=a.get("display_name", a["id"]),
            description=a.get("description", ""),
            category=a.get("category", "other"),
            time_minutes=int(a.get("time_minutes", 0)),
            requires=a.get("requires", {}),
            modifiers=a.get("modifiers", {}),
            outcomes={int(k): v for k, v in a.get("outcomes", {}).items()},
            consumes=a.get("consumes"),
            parameters=a.get("parameters"),
            dynamic=a.get("dynamic"),
        )

    return out


def load_spaces(path: str | Path) -> Dict[str, SpaceSpec]:
    """Load space specifications from YAML file.

    Args:
        path: Path to spaces.yaml file

    Returns:
        Dict mapping space_id to SpaceSpec

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is malformed
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    out: Dict[str, SpaceSpec] = {}

    for s in raw.get("spaces", []):
        out[s["id"]] = SpaceSpec(
            id=s["id"],
            name=s["name"],
            kind=s["kind"],
            base_temperature_c=s["base_temperature_c"],
            has_window=s["has_window"],
            connections=s.get("connections", []),
            tags=s.get("tags", []),
            fixtures=s.get("fixtures", []),
            utilities_available=s.get("utilities_available", []),
        )

    return out


def load_item_meta(path: str | Path) -> Dict[str, ItemMeta]:
    """Load item metadata from YAML file.

    Args:
        path: Path to items_meta.yaml file

    Returns:
        Dict mapping item_id to ItemMeta

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is malformed
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    out: Dict[str, ItemMeta] = {}

    for it in raw.get("items", []):
        out[it["id"]] = ItemMeta(
            id=it["id"],
            name=it.get("name", it["id"]),
            tags=it.get("tags", []),
            provides=it.get("provides", []),
            requires_utilities=it.get("requires_utilities", []),
            durability=it.get("durability"),
        )

    return out
