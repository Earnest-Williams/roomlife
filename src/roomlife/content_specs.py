"""Content specification loaders for data-driven action system.

This module provides data structures and loaders for:
- ActionSpec: Defines actions with requirements, modifiers, outcomes, and consumption
- SpaceSpec: Extended space definitions with tags, fixtures, and utilities
- ItemMeta: Item capability metadata (provides, requires, durability)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


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

    text = file_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    out: Dict[str, ActionSpec] = {}

    actions = raw.get("actions", [])
    line_map, index_lines = _action_line_map(text)
    if not isinstance(actions, list):
        raise ValueError(f"{file_path}: actions must be a list")

    for idx, a in enumerate(actions):
        line = _get_action_line(a, line_map, index_lines, idx)
        _validate_action_dict(a, file_path, line)
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


def _action_line_map(text: str) -> tuple[Dict[str, int], List[int]]:
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return {}, []
    if not isinstance(root, MappingNode):
        return {}, []

    actions_node = None
    for key_node, value_node in root.value:
        if isinstance(key_node, ScalarNode) and key_node.value == "actions":
            actions_node = value_node
            break

    if not isinstance(actions_node, SequenceNode):
        return {}, []

    line_map: Dict[str, int] = {}
    index_lines: List[int] = []
    for idx, action_node in enumerate(actions_node.value):
        line = action_node.start_mark.line + 1
        index_lines.append(line)
        if isinstance(action_node, MappingNode):
            for key_node, value_node in action_node.value:
                if isinstance(key_node, ScalarNode) and key_node.value == "id":
                    line_map[str(value_node.value)] = value_node.start_mark.line + 1
                    break
        else:
            line_map[f"__index_{idx}"] = line

    return line_map, index_lines


def _get_action_line(
    action: Any,
    line_map: Dict[str, int],
    index_lines: List[int],
    index: int,
) -> int | None:
    if isinstance(action, dict):
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id in line_map:
            return line_map[action_id]
    if index < len(index_lines):
        return index_lines[index]
    return None


def _validate_action_dict(action: Any, file_path: Path, line: int | None) -> None:
    if not isinstance(action, dict):
        raise ValueError(_format_action_error(file_path, line, "action must be a mapping"))
    action_id = action.get("id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError(_format_action_error(file_path, line, "action id must be a string"))

    outcomes = action.get("outcomes", {})
    if not isinstance(outcomes, dict):
        raise ValueError(_format_action_error(file_path, line, f"{action_id}: outcomes must be a mapping"))

    for tier, outcome in outcomes.items():
        if not isinstance(outcome, dict):
            raise ValueError(_format_action_error(
                file_path,
                line,
                f"{action_id}: outcome for tier {tier} must be a mapping",
            ))
        deltas = outcome.get("deltas", {})
        if deltas is not None and not isinstance(deltas, dict):
            raise ValueError(_format_action_error(
                file_path,
                line,
                f"{action_id}: deltas for tier {tier} must be a mapping",
            ))
        skills_xp = deltas.get("skills_xp", {}) if deltas else {}
        if skills_xp is not None and not isinstance(skills_xp, dict):
            raise ValueError(_format_action_error(
                file_path,
                line,
                f"{action_id}: skills_xp for tier {tier} must be a mapping",
            ))
        if isinstance(skills_xp, dict):
            for skill_name, xp_value in skills_xp.items():
                if not isinstance(xp_value, (int, float)):
                    raise ValueError(_format_action_error(
                        file_path,
                        line,
                        f"{action_id}: skills_xp.{skill_name} must be numeric",
                    ))


def _format_action_error(file_path: Path, line: int | None, message: str) -> str:
    if line is not None:
        return f"{file_path}:{line}: {message}"
    return f"{file_path}: {message}"


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
