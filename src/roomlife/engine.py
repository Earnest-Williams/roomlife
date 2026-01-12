from __future__ import annotations

import logging
import random
import yaml
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .constants import (
    DOCTOR_ILLNESS_RECOVERY,
    DOCTOR_INJURY_RECOVERY,
    DOCTOR_VISIT_COST,
    HEALTH_DEGRADATION_PER_EXTREME_NEED,
    HEALTH_EXTREME_NEED_THRESHOLD,
    HEALTH_PENALTY_THRESHOLD,
    ILLNESS_RECOVERY_PER_TURN,
    INJURY_RECOVERY_PER_TURN,
    JOBS,
    MAX_EVENT_LOG,
    REST_ILLNESS_RECOVERY,
    REST_INJURY_RECOVERY,
    SKILL_NAMES,
    SKILL_TO_APTITUDE,
    TIME_SLICES,
    TRAIT_DRIFT_CONFIGS,
    TRAIT_DRIFT_THRESHOLD,
)
from .models import Item, NPC, Skill, Space, State, generate_instance_id
from .content_specs import load_spaces, load_actions, load_item_meta
from .action_call import ActionCall
from .action_engine import (
    degrade_item_condition,
    execute_action,
    update_item_condition,
    validate_action_spec,
)
from . import npc_ai
from . import director

# Module-level constants
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
logger = logging.getLogger(__name__)


def _log(state: State, event_id: str, **params: object) -> None:
    """Log an event to the bounded event log (automatically trims via deque maxlen)."""
    state.event_log.append({"event_id": event_id, "params": params})


def _get_skill(state: State, skill_name: str) -> Skill:
    """Get a skill by name from the player's skill dictionary."""
    return state.player.skills_detailed[skill_name]


def _load_item_tags() -> Dict[str, set]:
    """Load item tags from items.yaml data file as sets for O(1) membership tests."""
    data_path = DATA_DIR / "items.yaml"
    try:
        with open(data_path, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"items.yaml not found at {data_path}, returning empty tags")
        return {}
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse items.yaml: {e}, returning empty tags")
        return {}
    except Exception as e:
        logger.warning(f"Unexpected error loading items.yaml: {e}, returning empty tags")
        return {}

    item_tags = {}
    try:
        for item_def in data.get("items", []):
            item_tags[item_def["id"]] = set(item_def.get("tags", []))
    except (KeyError, TypeError) as e:
        logger.warning(f"Malformed items.yaml data structure: {e}, returning partial tags")
    return item_tags


# Cache item tags to avoid reloading YAML repeatedly
_ITEM_TAGS_CACHE = None
_ITEM_METADATA_CACHE = None
_SHOP_CATALOG_CACHE = None

# Data-driven action system caches
_ACTION_SPECS = None
_ITEM_META = None
_SPACE_SPECS = None


def _get_item_tags(item_id: str) -> set:
    """Get tags for a specific item as a set for O(1) membership tests."""
    global _ITEM_TAGS_CACHE
    if _ITEM_TAGS_CACHE is None:
        _ITEM_TAGS_CACHE = _load_item_tags()
    return _ITEM_TAGS_CACHE.get(item_id, set())


def _load_item_metadata() -> Dict[str, dict]:
    """Load item metadata (price, quality, description) from items.yaml."""
    data_path = DATA_DIR / "items.yaml"
    try:
        with open(data_path, "r") as f:
            data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError, Exception) as e:
        logger.warning(f"Failed to load items.yaml: {e}")
        return {}

    item_metadata = {}
    try:
        for item_def in data.get("items", []):
            item_id = item_def["id"]
            item_metadata[item_id] = {
                "name": item_def.get("name", item_id),
                "price": item_def.get("price", 0),
                "quality": item_def.get("quality", 1.0),
                "description": item_def.get("description", ""),
                "tags": set(item_def.get("tags", [])),
            }
    except (KeyError, TypeError) as e:
        logger.warning(f"Malformed items.yaml data: {e}")
    return item_metadata


def _get_item_metadata(item_id: str) -> dict:
    """Get metadata for a specific item."""
    global _ITEM_METADATA_CACHE
    if _ITEM_METADATA_CACHE is None:
        _ITEM_METADATA_CACHE = _load_item_metadata()
    return _ITEM_METADATA_CACHE.get(item_id, {
        "name": item_id,
        "price": 0,
        "quality": 1.0,
        "description": "",
        "tags": set(),
    })


def _load_shop_catalog() -> dict:
    """Load shop catalog from shop_catalog.yaml."""
    data_path = DATA_DIR / "shop_catalog.yaml"
    try:
        with open(data_path, "r") as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError, Exception) as e:
        logger.warning(f"Failed to load shop_catalog.yaml: {e}")
        return {}


def _get_shop_catalog() -> dict:
    """Get the shop catalog (cached)."""
    global _SHOP_CATALOG_CACHE
    if _SHOP_CATALOG_CACHE is None:
        _SHOP_CATALOG_CACHE = _load_shop_catalog()
    return _SHOP_CATALOG_CACHE


def _find_item_with_tag(state: State, tag: str, location: str = None) -> Item | None:
    """Find an item with a specific tag at the current or specified location."""
    if location is None:
        location = state.world.location

    items_here = state.get_items_at(location)
    for item in items_here:
        if tag in _get_item_tags(item.item_id):
            return item
    return None


def _get_item_effectiveness(item: Item) -> float:
    """Calculate item effectiveness multiplier based on condition_value (0-100) and quality."""
    # Base effectiveness from condition
    if item.condition_value >= 90:
        condition_mult = 1.1  # pristine items give bonus
    elif item.condition_value >= 70:
        condition_mult = 1.0  # used items work normally
    elif item.condition_value >= 40:
        condition_mult = 0.8  # worn items less effective
    elif item.condition_value >= 20:
        condition_mult = 0.5  # broken items barely work
    else:
        condition_mult = 0.3  # filthy items very poor

    # Combine condition and quality multipliers
    # Quality ranges from 0.8 (worn desk) to 1.8 (premium computer)
    return condition_mult * item.quality




def _calculate_health(state: State) -> None:
    """Calculate overall health based on illness and injury."""
    n = state.player.needs
    health_penalty = (n.illness + n.injury) * 0.5
    n.health = max(0, min(100, int(100 - health_penalty)))


def _get_health_penalty(state: State) -> float:
    """Calculate health penalty multiplier for actions (0.5 to 1.0).

    Returns:
        1.0 if health >= HEALTH_PENALTY_THRESHOLD
        0.5 if health = 0
        Linear interpolation between 0.5 and 1.0 for health below threshold
    """
    _calculate_health(state)  # Ensure health is up-to-date
    health = state.player.needs.health
    if health >= HEALTH_PENALTY_THRESHOLD:
        return 1.0
    # Linear interpolation: health 0 = 0.5, health 50 = 1.0
    return 0.5 + (health / HEALTH_PENALTY_THRESHOLD) * 0.5


def _check_job_requirements(state: State, job_id: str) -> Tuple[bool, str]:
    """Check if player meets job requirements.

    Returns:
        Tuple of (meets_requirements, reason_if_failed)
    """
    job_data = JOBS.get(job_id)
    if not job_data:
        return False, "job_not_found"

    requirements = job_data.get("requirements", {})

    # Check if any requirements exist
    if not requirements:
        return True, ""

    require_all = requirements.get("require_all", True)

    # Check skill requirements
    skill_reqs = requirements.get("skills", [])
    skill_met = True
    for skill_req in skill_reqs:
        skill_name = skill_req["name"]
        min_value = skill_req["min"]
        skill = _get_skill(state, skill_name)
        if skill.value < min_value:
            skill_met = False
            if require_all:
                return False, f"insufficient_{skill_name}"

    # Check trait requirements
    trait_reqs = requirements.get("traits", [])
    trait_met = True
    for trait_req in trait_reqs:
        trait_name = trait_req["name"]
        min_value = trait_req["min"]
        trait_value = getattr(state.player.traits, trait_name, 0)
        if trait_value < min_value:
            trait_met = False
            if require_all:
                return False, f"insufficient_{trait_name}"

    # Check item requirements (e.g., certification, laptop)
    item_reqs = requirements.get("items", [])
    item_met = True
    for item_req in item_reqs:
        tag = item_req["tag"]
        has_item = _find_item_with_tag(state, tag) is not None
        if not has_item:
            item_met = False
            if require_all:
                return False, f"missing_{tag}"

    # If require_all is False, check if at least one category is met
    # Only check categories that actually have requirements
    if not require_all:
        met_categories = []
        if len(skill_reqs) > 0:
            met_categories.append(skill_met)
        if len(trait_reqs) > 0:
            met_categories.append(trait_met)
        if len(item_reqs) > 0:
            met_categories.append(item_met)

        if len(met_categories) > 0 and any(met_categories):
            return True, ""
        return False, "insufficient_any_requirement"

    return True, ""


def _apply_skill_rust(state: State, current_tick: int) -> None:
    """Apply skill rust with localized attribute lookups for performance."""
    skills = state.player.skills_detailed
    discipline = state.player.traits.discipline
    discipline_mod_base = (discipline / 100.0) * 0.3

    for skill_name in SKILL_NAMES:
        skill = skills[skill_name]
        ticks_passed = current_tick - skill.last_tick
        if ticks_passed > 0 and skill.value > 0:
            rust_amount = skill.rust_rate * ticks_passed * (1.0 - discipline_mod_base)
            skill.value = max(0.0, skill.value - rust_amount)
            skill.last_tick = current_tick


def _gain_skill_xp(state: State, skill_name: str, gain: float, current_tick: int) -> float:
    """Apply skill XP gain with localized attribute lookups for performance."""
    skill = state.player.skills_detailed[skill_name]
    curiosity = state.player.traits.curiosity
    curiosity_mod = 1.0 + (curiosity / 100.0) * 0.3
    health_penalty = _get_health_penalty(state)  # Apply health penalty to skill gains
    actual_gain = gain * curiosity_mod * health_penalty
    skill.value += actual_gain
    skill.last_tick = current_tick

    # Update aptitude
    aptitude_name = SKILL_TO_APTITUDE[skill_name]
    aptitudes = state.player.aptitudes
    aptitude_gain = actual_gain * 0.002
    new_aptitude = getattr(aptitudes, aptitude_name) + aptitude_gain
    setattr(aptitudes, aptitude_name, new_aptitude)
    return actual_gain


def _apply_trait_drift(state: State) -> List[str]:
    """Apply trait changes based on habit accumulation (optimized loop-based approach)."""
    messages = []
    tracker = state.player.habit_tracker
    traits = state.player.traits

    for config in TRAIT_DRIFT_CONFIGS:
        habit_name = config["habit"]
        trait_name = config["trait"]
        if tracker.get(habit_name, 0) > TRAIT_DRIFT_THRESHOLD:
            current_trait = getattr(traits, trait_name)
            setattr(traits, trait_name, min(100, current_trait + 1))
            messages.append(config["message"])
            tracker[habit_name] = 0

    return messages


def _calculate_current_tick(state: State) -> int:
    try:
        slice_index = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # Invalid slice, default to 0 (morning)
        logger.warning(f"Invalid time slice '{state.world.slice}' in _calculate_current_tick, using 0")
        slice_index = 0
    return state.world.day * 4 + slice_index


def _ensure_specs_loaded() -> None:
    """Ensure action specs and item metadata are loaded from YAML.

    This function loads base content from data/ directory, then merges
    optional content packs from data/packs/<pack_id>/ in deterministic order.

    Pack merge rules:
    - Packs are loaded in sorted order by pack directory name
    - Actions with same id override base actions (later packs override earlier packs)
    - This allows packs to provide variants or extensions of base actions
    """
    global _ACTION_SPECS, _ITEM_META, _SPACE_SPECS

    # Find data directory relative to this file
    data_dir = Path(__file__).parent.parent.parent / "data"

    if _ACTION_SPECS is None:
        # Load base actions
        actions_path = data_dir / "actions.yaml"
        if actions_path.exists():
            try:
                _ACTION_SPECS = load_actions(actions_path)
            except ValueError as exc:
                logger.warning(f"Failed to load actions.yaml: {exc}")
                _ACTION_SPECS = {}
        else:
            _ACTION_SPECS = {}

        # Load content packs (deterministic order by sorted directory name)
        packs_dir = data_dir / "packs"
        if packs_dir.exists() and packs_dir.is_dir():
            pack_dirs = sorted([d for d in packs_dir.iterdir() if d.is_dir()])
            for pack_dir in pack_dirs:
                pack_actions_path = pack_dir / "actions.yaml"
                if pack_actions_path.exists():
                    try:
                        pack_actions = load_actions(pack_actions_path)
                        # Merge pack actions (override if id matches)
                        _ACTION_SPECS.update(pack_actions)
                        logger.info(f"Loaded content pack: {pack_dir.name} ({len(pack_actions)} actions)")
                    except ValueError as exc:
                        logger.warning(f"Failed to load pack {pack_dir.name}/actions.yaml: {exc}")

    if _ITEM_META is None:
        items_path = data_dir / "items_meta.yaml"
        if items_path.exists():
            try:
                _ITEM_META = load_item_meta(items_path)
            except ValueError as exc:
                logger.warning(f"Failed to load items_meta.yaml: {exc}")
                _ITEM_META = {}
        else:
            _ITEM_META = {}

    if _SPACE_SPECS is None:
        spaces_path = data_dir / "spaces.yaml"
        if spaces_path.exists():
            try:
                _SPACE_SPECS = load_spaces(spaces_path)
            except ValueError as exc:
                logger.warning(f"Failed to load spaces.yaml: {exc}")
                _SPACE_SPECS = {}
        else:
            _SPACE_SPECS = {}


def new_game(seed: Optional[int] = None) -> State:
    """Create a new game state.

    Args:
        seed: Optional seed for deterministic instance ID generation.
              If provided, the same seed will generate the same item instance IDs.

    Returns:
        A new game state.
    """
    state = State()

    # Store simulation seed for deterministic NPC/director behavior
    state.world.rng_seed = seed if seed is not None else 0

    # Initialize and store reusable RNG instance
    state.world.rng = random.Random(seed)

    # Create RNG for deterministic ID generation if seed provided
    rng = state.world.rng if seed is not None else None

    # Load spaces from YAML
    _ensure_specs_loaded()
    if _SPACE_SPECS:
        # Convert SpaceSpec to Space model
        state.spaces = {}
        for spec in _SPACE_SPECS.values():
            state.spaces[spec.id] = Space(
                space_id=spec.id,
                name=spec.name,
                kind=spec.kind,
                base_temperature_c=spec.base_temperature_c,
                has_window=spec.has_window,
                connections=spec.connections,
                tags=spec.tags,
                fixtures=spec.fixtures,
                utilities_available=spec.utilities_available,
            )
    else:
        # Fallback to hardcoded spaces if YAML not available
        state.spaces = {
            "room_001": Space(
                "room_001",
                "Tiny room",
                "room",
                14,
                False,
                ["hall_001"],
                tags=["room", "sleep_area"],
                fixtures=["bed_spot", "desk_spot"],
                utilities_available=["power", "heat"],
            ),
            "hall_001": Space(
                "hall_001",
                "Hallway",
                "shared",
                12,
                False,
                ["room_001", "bath_001", "kitchen_001"],
                tags=["hallway", "transit"],
                fixtures=[],
                utilities_available=["power"],
            ),
            "bath_001": Space(
                "bath_001",
                "Shared bathroom",
                "shared",
                13,
                False,
                ["hall_001"],
                tags=["bathroom"],
                fixtures=["shower", "sink", "toilet"],
                utilities_available=["water", "heat", "power"],
            ),
            "kitchen_001": Space(
                "kitchen_001",
                "Shared kitchen",
                "shared",
                16,
                False,
                ["hall_001"],
                tags=["kitchen"],
                fixtures=["sink", "stove_spot"],
                utilities_available=["power", "heat", "water"],
            ),
        }

    # Create starter items with quality from metadata
    # Items start at ~50% condition (worn) to reflect their degraded state
    starter_items = [
        ("bed_basic", "worn", 50, "room_001", "floor"),
        ("desk_worn", "worn", 45, "room_001", "wall"),
        ("kettle", "worn", 50, "kitchen_001", "counter"),
    ]

    state.items = []
    for item_id, condition, condition_value, placed_in, slot in starter_items:
        metadata = _get_item_metadata(item_id)
        quality = metadata.get("quality", 1.0)
        state.items.append(Item(
            instance_id=generate_instance_id(rng),
            item_id=item_id,
            placed_in=placed_in,
            container=None,
            slot=slot,
            quality=quality,
            condition=condition,
            condition_value=condition_value,
            bulk=metadata.get("bulk", 1),
        ))

    # Seed building NPCs (2-3 contacts: neighbor, landlord, maintenance)
    state.npcs = {
        "npc_neighbor_nina": NPC(
            id="npc_neighbor_nina",
            display_name="Nina",
            role="neighbor",
        ),
        "npc_landlord_park": NPC(
            id="npc_landlord_park",
            display_name="Mr. Park",
            role="landlord",
        ),
        "npc_maint_lee": NPC(
            id="npc_maint_lee",
            display_name="Lee",
            role="maintenance",
        ),
    }

    # Initialize NPC relationships to neutral (0)
    for npc_id in state.npcs:
        state.npcs[npc_id].relationships["player"] = 0
        state.player.relationships[npc_id] = 0

    # Validate that the starting location exists in the world
    if state.world.location not in state.spaces:
        raise ValueError(f"Starting location '{state.world.location}' does not exist in world spaces")
    _log(state, "game.start", day=state.world.day, slice=state.world.slice)
    return state


def _advance_time(state: State) -> None:
    try:
        idx = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # If current slice is invalid, reset to first slice
        logger.warning(f"Invalid time slice '{state.world.slice}', resetting to '{TIME_SLICES[0]}'")
        state.world.slice = TIME_SLICES[0]
        _log(state, "time.advance", day=state.world.day, slice=state.world.slice)
        return

    new_day = False
    if idx == len(TIME_SLICES) - 1:
        state.world.day += 1
        state.world.slice = TIME_SLICES[0]
        new_day = True
        _log(state, "time.new_day", day=state.world.day)
    else:
        state.world.slice = TIME_SLICES[idx + 1]
    _log(state, "time.advance", day=state.world.day, slice=state.world.slice)

    # Trigger daily systems on day rollover
    if new_day:
        _ensure_specs_loaded()
        current_tick = _calculate_current_tick(state)
        # Seed daily goals
        director.seed_daily_goals(state, _ACTION_SPECS, _ITEM_META)
        # Trigger NPC building event
        npc_ai.maybe_trigger_daily_building_event(state, _ACTION_SPECS, _ITEM_META, current_tick)


def _apply_environment(state: State, rng: random.Random) -> None:
    current_tick = _calculate_current_tick(state)
    _apply_skill_rust(state, current_tick)
    trait_messages = _apply_trait_drift(state)
    for msg in trait_messages:
        _log(state, "trait.drift", message=msg)

    if not state.player.utilities_paid:
        state.utilities.power = False
        state.utilities.heat = False
        state.utilities.water = False
    else:
        state.utilities.power = True
        state.utilities.heat = True
        state.utilities.water = True

    # Pacing system: adjust needs decay rates and mishap frequency
    pacing = state.player.flags.get("pacing", "normal")
    if pacing == "relaxed":
        needs_multiplier = 0.7  # Slower needs decay
        mishap_multiplier = 0.5  # Fewer mishaps
    elif pacing == "hard":
        needs_multiplier = 1.5  # Faster needs decay
        mishap_multiplier = 2.0  # More mishaps
    else:  # "normal"
        needs_multiplier = 1.0
        mishap_multiplier = 1.0

    n = state.player.needs
    n.hunger = min(100, n.hunger + round(8 * needs_multiplier))
    n.fatigue = min(100, n.fatigue + round(6 * needs_multiplier))
    if state.utilities.water:
        n.hygiene = max(0, n.hygiene - round(4 * needs_multiplier))
    else:
        n.hygiene = max(0, n.hygiene - round(8 * needs_multiplier))
        n.mood = max(0, n.mood - 2)
        _log(state, "utility.no_water")

    if state.utilities.heat:
        n.warmth = min(100, n.warmth + 4)
    else:
        n.warmth = max(0, n.warmth - 10)
        n.mood = max(0, n.mood - 3)
        _log(state, "utility.no_heat")

    if not state.utilities.power:
        n.mood = max(0, n.mood - 2)
        _log(state, "utility.no_power")

    # Calculate energy based on fatigue and fitness trait
    # Energy is inversely proportional to fatigue
    base_energy = 100 - n.fatigue
    # Fitness trait provides a bonus/penalty (fitness 50 = neutral, above = bonus, below = penalty)
    fitness_modifier = (state.player.traits.fitness - 50) * 0.2
    n.energy = max(0, min(100, int(base_energy + fitness_modifier)))

    # Health degradation from extreme needs
    extreme_needs = []
    if n.hunger > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("hunger")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.fatigue > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("fatigue")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.hygiene > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("hygiene")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)
    if n.stress > HEALTH_EXTREME_NEED_THRESHOLD:
        extreme_needs.append("stress")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED * 0.5)  # Stress contributes less
    if n.warmth < 20:  # Cold causes illness
        extreme_needs.append("cold")
        n.illness = min(100, n.illness + HEALTH_DEGRADATION_PER_EXTREME_NEED)

    # Natural recovery from illness and injury
    if n.illness > 0:
        stoicism_bonus = state.player.traits.stoicism / 100.0 * 0.5  # Stoicism helps recovery
        recovery = ILLNESS_RECOVERY_PER_TURN * (1.0 + stoicism_bonus)
        n.illness = max(0, n.illness - recovery)
    if n.injury > 0:
        fitness_bonus = state.player.traits.fitness / 100.0 * 0.3  # Fitness helps injury recovery
        recovery = INJURY_RECOVERY_PER_TURN * (1.0 + fitness_bonus)
        n.injury = max(0, n.injury - recovery)

    # Calculate overall health based on illness and injury
    _calculate_health(state)

    # Log health warnings
    if extreme_needs:
        _log(state, "health.degradation", extreme_needs=extreme_needs, illness=int(n.illness), injury=int(n.injury))
    if n.health < 30:
        _log(state, "health.critical", health=n.health)
    elif n.health < 50:
        _log(state, "health.warning", health=n.health)

    # Random events (adjusted by pacing mishap multiplier)
    if rng.random() < (0.05 * mishap_multiplier):
        _log(state, "building.noise", severity="low")

    # Small chance of minor injury from accidents (adjusted by pacing)
    if rng.random() < (0.02 * mishap_multiplier):
        injury_amount = rng.randint(5, 15)
        n.injury = min(100, n.injury + injury_amount)
        # Recalculate health to reflect the new injury immediately
        _calculate_health(state)
        _log(state, "health.injury", injury_amount=injury_amount, source="accident")
        # Log additional warning if injury pushed health below thresholds
        if n.health < 30:
            _log(state, "health.critical", health=n.health)
        elif n.health < 50:
            _log(state, "health.warning", health=n.health)


def apply_action(
    state: State,
    action_id: str,
    rng_seed: int = 1,
    params: Optional[Dict[str, object]] = None,
) -> None:
    try:
        time_slice_index = TIME_SLICES.index(state.world.slice)
    except ValueError:
        # If current slice is invalid, use 0 as fallback
        logger.warning(f"Invalid time slice '{state.world.slice}' in apply_action, using 0")
        time_slice_index = 0

    # Reuse stored RNG instance with deterministic seeding for this action
    rng = state.world.rng
    rng.seed(rng_seed + state.world.day * 97 + time_slice_index)
    current_tick = _calculate_current_tick(state)

    # Data-driven action system: Check if action has a YAML spec first
    _ensure_specs_loaded()
    action_call = ActionCall.from_legacy(action_id) if params is None else ActionCall(action_id, params or {})
    spec = _ACTION_SPECS.get(action_call.action_id) if _ACTION_SPECS else None
    if spec is not None:
        # Capture location before action for encounter detection
        before_location = state.world.location

        # Validate action
        ok, reason, missing = validate_action_spec(state, spec, _ITEM_META, action_call.params)
        if not ok:
            _log(state, "action.failed", action_id=action_id, reason=reason, missing=missing)
        else:
            execute_action(state, spec, _ITEM_META, action_call, rng_seed, current_tick)

            # Check for NPC encounter if player moved to a new location
            after_location = state.world.location
            if after_location != before_location:
                npc_ai.on_player_entered_space(
                    state, before_location, after_location, _ACTION_SPECS, _ITEM_META, current_tick
                )

        # Always advance time and apply environment
        _advance_time(state)
        _apply_environment(state, rng)
        return

    # No YAML spec found - unknown action
    _log(state, "action.unknown", action_id=action_id)
    _advance_time(state)
    _apply_environment(state, rng)


def to_debug_dict(state: State) -> Dict:
    return asdict(state)


def generate_skill_recap(state: State) -> List[Dict]:
    recap = []
    for skill_name in SKILL_NAMES:
        skill = _get_skill(state, skill_name)
        if skill.value > 0:
            aptitude_name = SKILL_TO_APTITUDE[skill_name]
            aptitude_value = getattr(state.player.aptitudes, aptitude_name)
            recap.append({
                "skill": skill_name.replace("_", " ").title(),
                "value": round(skill.value, 2),
                "aptitude": aptitude_name.replace("_", " ").title(),
                "aptitude_value": round(aptitude_value, 3),
            })
    return recap
