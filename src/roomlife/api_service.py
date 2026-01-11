"""Main API service for RoomLife simulation.

This service provides a clean interface for visualization engines
to interact with the simulation, including state queries, action execution,
validation, and event streaming.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .api_types import (
    ActionCategory,
    ActionMetadata,
    ActionPreview,
    ActionResult,
    ActionValidation,
    AvailableActionsResponse,
    EventInfo,
    GameStateSnapshot,
    ItemInfo,
    LocationInfo,
    NeedsSnapshot,
    SkillInfo,
    TraitsSnapshot,
    UtilitiesSnapshot,
    WorldInfo,
)
from .constants import SKILL_NAMES, SKILL_TO_APTITUDE, TIME_SLICES
from .engine import apply_action
from .models import State
from .content_specs import load_actions, load_item_meta
from .action_engine import (
    build_preview_notes,
    preview_delta_ranges,
    preview_tier_distribution,
    validate_action_spec,
)
from .action_call import ActionCall
from .catalog import ActionCatalog


class RoomLifeAPI:
    """Main API for interacting with RoomLife simulation.

    This class provides a comprehensive interface for visualization engines,
    supporting both synchronous queries and event streaming.
    """

    def __init__(self, state: State):
        """Initialize the API with a game state.

        Args:
            state: The current game state
        """
        self.state = state
        self._event_listeners: List[Callable[[EventInfo], None]] = []
        self._state_change_listeners: List[Callable[[GameStateSnapshot], None]] = []

        # Load data-driven action specs
        data_dir = Path(__file__).parent.parent.parent / "data"
        actions_path = data_dir / "actions.yaml"
        items_meta_path = data_dir / "items_meta.yaml"

        self._action_specs = load_actions(actions_path) if actions_path.exists() else {}
        self._item_meta = load_item_meta(items_meta_path) if items_meta_path.exists() else {}

    def get_state_snapshot(self) -> GameStateSnapshot:
        """Get a complete snapshot of the current game state.

        Returns:
            GameStateSnapshot with all relevant game data
        """
        # Build current tick (handle invalid time slice gracefully)
        try:
            slice_index = TIME_SLICES.index(self.state.world.slice)
        except ValueError:
            # Invalid slice, default to 0 (morning)
            print(f"Warning: Invalid time slice '{self.state.world.slice}', using 0")
            slice_index = 0
        current_tick = self.state.world.day * 4 + slice_index

        # Build world info
        world = WorldInfo(
            day=self.state.world.day,
            slice=self.state.world.slice,
            location=self.state.world.location,
            current_tick=current_tick,
        )

        # Build needs
        needs = NeedsSnapshot(
            hunger=self.state.player.needs.hunger,
            fatigue=self.state.player.needs.fatigue,
            warmth=self.state.player.needs.warmth,
            hygiene=self.state.player.needs.hygiene,
            mood=self.state.player.needs.mood,
            stress=self.state.player.needs.stress,
            energy=self.state.player.needs.energy,
            health=self.state.player.needs.health,
            illness=self.state.player.needs.illness,
            injury=self.state.player.needs.injury,
        )

        # Build traits
        traits = TraitsSnapshot(
            discipline=self.state.player.traits.discipline,
            confidence=self.state.player.traits.confidence,
            empathy=self.state.player.traits.empathy,
            fitness=self.state.player.traits.fitness,
            frugality=self.state.player.traits.frugality,
            curiosity=self.state.player.traits.curiosity,
            stoicism=self.state.player.traits.stoicism,
            creativity=self.state.player.traits.creativity,
        )

        # Build utilities
        utilities = UtilitiesSnapshot(
            power=self.state.utilities.power,
            heat=self.state.utilities.heat,
            water=self.state.utilities.water,
        )

        # Build skills list (all skills for completeness)
        skills = []
        for skill_name in SKILL_NAMES:
            skill = self.state.player.skills_detailed[skill_name]
            aptitude_name = SKILL_TO_APTITUDE[skill_name]
            aptitude_value = getattr(self.state.player.aptitudes, aptitude_name)
            skills.append(SkillInfo(
                name=skill_name,
                value=skill.value,
                rust_rate=skill.rust_rate,
                last_tick=skill.last_tick,
                aptitude=aptitude_name,
                aptitude_value=aptitude_value,
            ))

        # Build aptitudes dict
        aptitudes = {
            "logic_systems": self.state.player.aptitudes.logic_systems,
            "social_grace": self.state.player.aptitudes.social_grace,
            "domesticity": self.state.player.aptitudes.domesticity,
            "vitality": self.state.player.aptitudes.vitality,
        }

        # Build current location with items
        if self.state.world.location not in self.state.spaces:
            raise ValueError(f"Invalid location: {self.state.world.location} not found in spaces")
        current_space = self.state.spaces[self.state.world.location]
        current_items = self.state.get_items_at(self.state.world.location)
        current_location = LocationInfo(
            space_id=current_space.space_id,
            name=current_space.name,
            kind=current_space.kind,
            base_temperature_c=current_space.base_temperature_c,
            has_window=current_space.has_window,
            connections=current_space.connections,
            items=[ItemInfo(
                instance_id=item.instance_id,
                item_id=item.item_id,
                condition=item.condition,
                condition_value=item.condition_value,
                placed_in=item.placed_in,
                slot=item.slot,
                container=item.container,
                bulk=item.bulk,
            ) for item in current_items],
        )

        # Build all locations
        all_locations = {}
        for space_id, space in self.state.spaces.items():
            space_items = self.state.get_items_at(space_id)
            all_locations[space_id] = LocationInfo(
                space_id=space.space_id,
                name=space.name,
                kind=space.kind,
                base_temperature_c=space.base_temperature_c,
                has_window=space.has_window,
                connections=space.connections,
                items=[ItemInfo(
                    instance_id=item.instance_id,
                    item_id=item.item_id,
                    condition=item.condition,
                    condition_value=item.condition_value,
                    placed_in=item.placed_in,
                    slot=item.slot,
                    container=item.container,
                    bulk=item.bulk,
                ) for item in space_items],
            )

        # Get recent events (last 10)
        recent_events = [
            EventInfo(event_id=event["event_id"], params=event.get("params", {}))
            for event in self.state.event_log[-10:]
        ]

        return GameStateSnapshot(
            world=world,
            player_money_pence=self.state.player.money_pence,
            utilities_paid=self.state.player.utilities_paid,
            needs=needs,
            traits=traits,
            utilities=utilities,
            skills=skills,
            aptitudes=aptitudes,
            habit_tracker=dict(self.state.player.habit_tracker),
            current_location=current_location,
            all_locations=all_locations,
            recent_events=recent_events,
            schema_version=self.state.schema_version,
        )

    def get_available_actions(self) -> AvailableActionsResponse:
        """Get all currently available actions with metadata.

        Returns:
            AvailableActionsResponse with action metadata
        """
        actions = [action for action in self._get_action_metadata_list() if action.available]

        return AvailableActionsResponse(
            actions=actions,
            location=self.state.world.location,
            total_count=len(actions),
        )

    def get_all_actions_metadata(self) -> List[ActionMetadata]:
        """Get metadata for all possible actions (even if not currently valid).

        Returns:
            List of ActionMetadata for all actions
        """
        return self._get_action_metadata_list()

    def validate_action(self, action_id: str, params: Optional[Dict[str, Any]] = None) -> ActionValidation:
        """Validate if an action can be executed in the current state.

        Args:
            action_id: The action to validate

        Returns:
            ActionValidation with validation result
        """
        action_call = ActionCall.from_legacy(action_id) if params is None else ActionCall(action_id, params)
        spec = self._action_specs.get(action_call.action_id)
        if spec is not None:
            ok, reason, missing = validate_action_spec(self.state, spec, self._item_meta, action_call.params)
            preview = None
            if ok:
                preview = ActionPreview(
                    tier_distribution=preview_tier_distribution(
                        self.state,
                        spec,
                        self._item_meta,
                        rng_seed=1,
                        samples=9,
                    ),
                    delta_ranges=preview_delta_ranges(spec),
                    notes=build_preview_notes(self.state, spec, self._item_meta, action_call),
                )
            return ActionValidation(
                valid=ok,
                action_id=action_id,
                reason=reason if not ok else "",
                missing_requirements=missing if not ok else None,
                preview=preview,
            )

        # Legacy hardcoded validation (fallback)
        from .engine import _find_item_with_tag
        missing = []

        # Handle movement actions
        if action_id.startswith("move_"):
            target_location = action_id[5:]
            current_location = self.state.world.location

            if current_location not in self.state.spaces:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Current location is invalid",
                )

            if target_location == current_location:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Already at this location",
                )

            if target_location not in self.state.spaces:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Location does not exist",
                )

            if target_location not in self.state.spaces[current_location].connections:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Location not accessible from here",
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle repair actions
        if action_id.startswith("repair_"):
            item_id = action_id[7:]
            items_here = self.state.get_items_at(self.state.world.location)
            item_to_repair = None
            for item in items_here:
                if item.item_id == item_id:
                    item_to_repair = item
                    break

            if item_to_repair is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item not found at current location",
                )

            if item_to_repair.condition_value >= 90:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item is already in pristine condition",
                )

            # Calculate cost
            damage = 100 - item_to_repair.condition_value
            base_cost = int(damage * 10)
            maintenance_skill = self.state.player.skills_detailed["maintenance"].value
            discount = maintenance_skill * 2
            cost = max(50, int(base_cost - discount))

            if self.state.player.money_pence < cost:
                missing.append(f"need {cost}p (have {self.state.player.money_pence}p)")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Insufficient funds",
                    missing_requirements=missing,
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle purchase actions
        if action_id.startswith("purchase_"):
            item_id = action_id[9:]  # Remove "purchase_" prefix
            from .engine import _get_item_metadata

            metadata = _get_item_metadata(item_id)
            price = metadata.get("price", 0)

            if price <= 0:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item not available for purchase",
                )

            if self.state.player.money_pence < price:
                missing.append(f"need {price}p (have {self.state.player.money_pence}p)")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Insufficient funds",
                    missing_requirements=missing,
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle sell actions
        if action_id.startswith("sell_"):
            item_id = action_id[5:]  # Remove "sell_" prefix

            # Find the item at current location
            item_to_sell = None
            for item in self.state.items:
                if item.item_id == item_id and item.placed_in == self.state.world.location:
                    item_to_sell = item
                    break

            if item_to_sell is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item not found at current location",
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle discard actions
        if action_id.startswith("discard_"):
            item_id = action_id[8:]  # Remove "discard_" prefix

            # Find the item at current location
            item_to_discard = None
            for item in self.state.items:
                if item.item_id == item_id and item.placed_in == self.state.world.location:
                    item_to_discard = item
                    break

            if item_to_discard is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item not found at current location",
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle job application actions
        if action_id.startswith("apply_job_"):
            job_id = action_id[10:]  # Remove "apply_job_" prefix
            from .constants import JOBS

            if job_id not in JOBS:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Job not found",
                )

            # Check if already have this job
            if self.state.player.current_job == job_id:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Already employed in this position",
                )

            # Check if player meets job requirements
            from .engine import _check_job_requirements
            meets_requirements, reason = _check_job_requirements(self.state, job_id)
            if not meets_requirements:
                missing.append(f"requirements not met: {reason}")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason=f"Requirements not met: {reason}",
                    missing_requirements=missing,
                )

            return ActionValidation(valid=True, action_id=action_id)

        # List of known non-movement actions
        known_actions = {
            "work", "study", "sleep", "eat_charity_rice", "cook_basic_meal",
            "shower", "pay_utilities", "skip_utilities", "clean_room", "exercise",
            "rest", "visit_doctor"
        }

        # Check if action is known
        if action_id not in known_actions:
            return ActionValidation(
                valid=False,
                action_id=action_id,
                reason="Unknown action",
            )

        # Check specific action requirements
        if action_id == "shower":
            if not self.state.utilities.water:
                missing.append("water utility")
            if self.state.world.location != "bath_001":
                missing.append("must be in bathroom")

            if missing:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Missing requirements",
                    missing_requirements=missing,
                )

        elif action_id == "pay_utilities":
            # Calculate cost
            base_cost = 2000
            resource_mgmt_discount = self.state.player.skills_detailed["resource_management"].value * 10
            frugality_discount = self.state.player.traits.frugality / 100.0 * 200
            cost = max(0, int(base_cost - resource_mgmt_discount - frugality_discount))

            if self.state.player.money_pence < cost:
                missing.append(f"need {cost}p (have {self.state.player.money_pence}p)")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Insufficient funds",
                    missing_requirements=missing,
                )

        elif action_id == "cook_basic_meal":
            cost = 300
            if self.state.player.money_pence < cost:
                missing.append(f"need {cost}p")

            # Check for cooking item using tag system
            cooking_item = _find_item_with_tag(self.state, "cook")
            if cooking_item is None:
                missing.append("cooking item (kettle/stove)")

            if missing:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Missing requirements",
                    missing_requirements=missing,
                )

        elif action_id == "work":
            # Check for desk/workspace
            desk = _find_item_with_tag(self.state, "work")
            if desk is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Need workspace (desk)",
                    missing_requirements=["desk with work capability"],
                )

        elif action_id == "study":
            # Check for desk/study area
            desk = _find_item_with_tag(self.state, "study")
            if desk is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Need study area (desk)",
                    missing_requirements=["desk with study capability"],
                )

        elif action_id == "sleep":
            # Check for bed
            bed = _find_item_with_tag(self.state, "sleep")
            if bed is None:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Need bed to sleep",
                    missing_requirements=["bed"],
                )

        elif action_id == "visit_doctor":
            # Check if player has enough money
            from .constants import DOCTOR_VISIT_COST
            if self.state.player.money_pence < DOCTOR_VISIT_COST:
                missing.append(f"need {DOCTOR_VISIT_COST}p (have {self.state.player.money_pence}p)")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Insufficient funds",
                    missing_requirements=missing,
                )

        return ActionValidation(valid=True, action_id=action_id)

    def execute_action(
        self,
        action_id: str,
        rng_seed: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute an action and return the result.

        Args:
            action_id: The action to execute
            rng_seed: Optional random seed for determinism

        Returns:
            ActionResult with execution result and new state
        """
        # Get snapshot before action
        old_snapshot = self.get_state_snapshot()
        old_event_count = len(self.state.event_log)

        # Apply action
        if rng_seed is None:
            rng_seed = 1
        apply_action(self.state, action_id, rng_seed, params=params)

        # Get snapshot after action
        new_snapshot = self.get_state_snapshot()

        # Get new events
        new_events = [
            EventInfo(event_id=event["event_id"], params=event.get("params", {}))
            for event in self.state.event_log[old_event_count:]
        ]

        # Calculate state changes
        state_changes = self._calculate_state_changes(old_snapshot, new_snapshot)

        # Check if action succeeded (look for failure events)
        failure_events = {"action.failed", "action.unknown", "bills.unpaid"}
        success = not any(event.event_id in failure_events for event in new_events)

        # Notify listeners
        for event in new_events:
            self._notify_event_listeners(event)
        self._notify_state_change_listeners(new_snapshot)

        return ActionResult(
            success=success,
            action_id=action_id,
            new_state=new_snapshot,
            events_triggered=new_events,
            state_changes=state_changes,
        )

    def subscribe_to_events(self, callback: Callable[[EventInfo], None]) -> None:
        """Subscribe to game events.

        Args:
            callback: Function to call when events occur
        """
        self._event_listeners.append(callback)

    def subscribe_to_state_changes(self, callback: Callable[[GameStateSnapshot], None]) -> None:
        """Subscribe to state changes.

        Args:
            callback: Function to call when state changes
        """
        self._state_change_listeners.append(callback)

    def unsubscribe_from_events(self, callback: Callable[[EventInfo], None]) -> None:
        """Unsubscribe from game events.

        Args:
            callback: The callback to remove
        """
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def unsubscribe_from_state_changes(self, callback: Callable[[GameStateSnapshot], None]) -> None:
        """Unsubscribe from state changes.

        Args:
            callback: The callback to remove
        """
        if callback in self._state_change_listeners:
            self._state_change_listeners.remove(callback)

    def _notify_event_listeners(self, event: EventInfo) -> None:
        """Notify all event listeners of a new event."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                # Log but don't crash if listener fails
                print(f"Event listener error: {e}")

    def _notify_state_change_listeners(self, state: GameStateSnapshot) -> None:
        """Notify all state change listeners."""
        for listener in self._state_change_listeners:
            try:
                listener(state)
            except Exception as e:
                print(f"State change listener error: {e}")

    def _calculate_state_changes(
        self, old_state: GameStateSnapshot, new_state: GameStateSnapshot
    ) -> Dict[str, Any]:
        """Calculate differences between two states."""
        changes: Dict[str, Any] = {}

        # Check needs changes
        old_needs = old_state.needs.to_dict()
        new_needs = new_state.needs.to_dict()
        needs_changes = {k: new_needs[k] - old_needs[k] for k in old_needs if new_needs[k] != old_needs[k]}
        if needs_changes:
            changes["needs"] = needs_changes

        # Check money change
        if old_state.player_money_pence != new_state.player_money_pence:
            changes["money_pence"] = new_state.player_money_pence - old_state.player_money_pence

        # Check location change
        if old_state.world.location != new_state.world.location:
            changes["location"] = {
                "from": old_state.world.location,
                "to": new_state.world.location,
            }

        # Check time change
        if old_state.world.day != new_state.world.day or old_state.world.slice != new_state.world.slice:
            changes["time"] = {
                "day": new_state.world.day,
                "slice": new_state.world.slice,
            }

        return changes

    def _get_action_metadata_list(self) -> List[ActionMetadata]:
        """Get metadata for all possible actions."""
        catalog_actions = self._get_catalog_action_metadata_list()
        legacy_actions = self._get_legacy_action_metadata_list()
        legacy_actions = [
            action
            for action in legacy_actions
            if ActionCall.from_legacy(action.action_id).action_id not in self._action_specs
        ]
        self._apply_availability_metadata(legacy_actions)
        return catalog_actions + legacy_actions

    def _apply_availability_metadata(self, actions: List[ActionMetadata]) -> None:
        for action in actions:
            validation = self.validate_action(action.action_id, params=action.params)
            action.available = validation.valid
            action.why_locked = None if validation.valid else validation.reason
            action.missing_requirements = validation.missing_requirements if not validation.valid else []

    def _get_catalog_action_metadata_list(self) -> List[ActionMetadata]:
        catalog = ActionCatalog(self._action_specs, self._item_meta)
        cards = catalog.list_available(self.state)
        actions: List[ActionMetadata] = []
        for card in cards:
            spec = self._action_specs.get(card.call.action_id)
            category = ActionCategory.OTHER
            if spec is not None:
                category = self._get_action_category(spec.category)
            actions.append(ActionMetadata(
                action_id=card.call.action_id,
                display_name=card.display_name,
                description=card.description,
                category=category,
                requirements=dict(spec.requires) if spec and spec.requires else {},
                effects={},
                params=card.call.params or None,
                available=card.available,
                why_locked=card.why_locked,
                missing_requirements=card.missing_requirements,
            ))
        return actions

    def _get_action_category(self, value: Optional[str]) -> ActionCategory:
        if value is None:
            return ActionCategory.OTHER
        normalized = value.strip().lower()
        for category in ActionCategory:
            if category.value == normalized:
                return category
        return ActionCategory.OTHER

    def _get_legacy_action_metadata_list(self) -> List[ActionMetadata]:
        """Get metadata for all possible legacy actions."""
        from .constants import JOBS

        # Get current job info for work action
        current_job_id = self.state.player.current_job
        current_job = JOBS.get(current_job_id, JOBS["recycling_collector"])
        job_pay = current_job["base_pay"]
        job_name = current_job["name"]
        job_fatigue = current_job["fatigue_cost"]

        actions = [
            ActionMetadata(
                action_id="work",
                display_name=f"Work ({job_name})",
                description=f"Work your current job: {current_job['description']}",
                category=ActionCategory.WORK,
                requirements={},
                effects={
                    "money": f"+{job_pay}p (confidence adjusted)",
                    "fatigue": f"+{job_fatigue} (discipline/fitness adjusted)",
                    "mood": "-2",
                    "skills": "varies by job",
                },
            ),
            ActionMetadata(
                action_id="study",
                display_name="Study",
                description="Study to improve focus skill",
                category=ActionCategory.WORK,
                requirements={},
                effects={
                    "fatigue": "+10 (ergonomics adjusted)",
                    "mood": "+1",
                    "skill": "focus +3.0",
                },
            ),
            ActionMetadata(
                action_id="sleep",
                display_name="Sleep",
                description="Rest to recover fatigue",
                category=ActionCategory.SURVIVAL,
                requirements={},
                effects={
                    "fatigue": "-35 (fitness adjusted)",
                    "mood": "+3",
                    "stress": "reduced by introspection",
                },
            ),
            ActionMetadata(
                action_id="eat_charity_rice",
                display_name="Eat Charity Rice",
                description="Eat free rice to reduce hunger",
                category=ActionCategory.SURVIVAL,
                requirements={},
                effects={
                    "hunger": "-25 (nutrition adjusted)",
                    "mood": "-1",
                },
            ),
            ActionMetadata(
                action_id="cook_basic_meal",
                display_name="Cook Basic Meal",
                description="Cook a meal to reduce hunger",
                category=ActionCategory.SURVIVAL,
                requirements={"money": 300, "items": ["kettle or stove"]},
                effects={
                    "hunger": "-35 (creativity bonus)",
                    "mood": "+3",
                    "skill": "nutrition +1.5",
                },
                cost_pence=300,
                requires_items=["kettle", "stove"],
            ),
            ActionMetadata(
                action_id="shower",
                display_name="Shower",
                description="Take a shower to improve hygiene",
                category=ActionCategory.SURVIVAL,
                requirements={"location": "bathroom", "utilities": ["water"]},
                effects={
                    "hygiene": "-40",
                    "mood": "+5",
                    "warmth": "-10 (if no heat)",
                },
                requires_location="bath_001",
                requires_utilities=["water"],
            ),
            ActionMetadata(
                action_id="pay_utilities",
                display_name="Pay Utilities",
                description="Pay utilities bill to keep services active",
                category=ActionCategory.MAINTENANCE,
                requirements={"money": "~2000p (adjusted)"},
                effects={
                    "money": "-2000p (resource_management and frugality adjusted)",
                    "utilities_paid": "true",
                    "skill": "resource_management +1.0",
                },
                cost_pence=2000,
            ),
            ActionMetadata(
                action_id="skip_utilities",
                display_name="Skip Utilities",
                description="Skip paying utilities (services will be cut)",
                category=ActionCategory.MAINTENANCE,
                requirements={},
                effects={
                    "utilities_paid": "false",
                },
            ),
            ActionMetadata(
                action_id="clean_room",
                display_name="Clean Room",
                description="Clean your room to improve mood",
                category=ActionCategory.MAINTENANCE,
                requirements={},
                effects={
                    "hygiene": "-5",
                    "mood": "+8",
                    "stress": "-3",
                    "skill": "maintenance +2.0",
                },
            ),
            ActionMetadata(
                action_id="exercise",
                display_name="Exercise",
                description="Exercise to improve mood and reduce stress",
                category=ActionCategory.HEALTH,
                requirements={},
                effects={
                    "fatigue": "+20 (fitness adjusted)",
                    "hunger": "+5",
                    "mood": "+10",
                    "stress": "-5",
                    "skill": "reflexivity +2.5",
                },
            ),
            ActionMetadata(
                action_id="rest",
                display_name="Rest and Recover",
                description="Rest to recover from illness and injury",
                category=ActionCategory.HEALTH,
                requirements={},
                effects={
                    "illness": "-10",
                    "injury": "-5",
                    "fatigue": "-10",
                    "stress": "-5 (stoicism adjusted)",
                    "mood": "+3",
                },
            ),
            ActionMetadata(
                action_id="visit_doctor",
                display_name="Visit Doctor",
                description="Visit the doctor for professional medical treatment",
                category=ActionCategory.HEALTH,
                requirements={"money": 5000},
                effects={
                    "illness": "-40",
                    "injury": "-20",
                    "fatigue": "+5",
                    "mood": "+5",
                    "money": "-5000p",
                },
                cost_pence=5000,
            ),
        ]

        # Add movement actions dynamically
        current_location = self.state.world.location
        if current_location in self.state.spaces:
            current_space = self.state.spaces[current_location]
            for connection_id in current_space.connections:
                if connection_id in self.state.spaces:
                    target_space = self.state.spaces[connection_id]
                    actions.append(ActionMetadata(
                        action_id=f"move_{connection_id}",
                        display_name=f"Move to {target_space.name}",
                        description=f"Move from {current_space.name} to {target_space.name}",
                        category=ActionCategory.MOVEMENT,
                        requirements={},
                        effects={
                            "location": target_space.name,
                            "fatigue": "+2",
                        },
                    ))

        # Add repair actions for items at current location
        items_at_location = self.state.get_items_at(current_location)
        for item in items_at_location:
            # Only add repair action if item is not pristine
            if item.condition_value < 90:
                # Calculate repair cost
                damage = 100 - item.condition_value
                base_cost = int(damage * 10)
                maintenance_skill = self.state.player.skills_detailed["maintenance"].value
                discount = maintenance_skill * 2
                cost = max(50, int(base_cost - discount))

                item_display_name = item.item_id.replace('_', ' ').title()
                actions.append(ActionMetadata(
                    action_id=f"repair_{item.item_id}",
                    display_name=f"Repair {item_display_name}",
                    description=f"Repair {item_display_name} ({item.condition} → better)",
                    category=ActionCategory.MAINTENANCE,
                    requirements={"money": f"{cost}p"},
                    effects={
                        "money": f"-{cost}p",
                        "item_condition": "+30 (maintenance adjusted)",
                        "skill": "maintenance +2.0",
                    },
                    cost_pence=cost,
                ))

        # Add shopping actions based on shop catalog
        from .engine import _get_shop_catalog, _get_item_metadata
        catalog = _get_shop_catalog()
        categories = catalog.get("categories", [])

        for category in categories:
            category_items = category.get("items", [])

            for item_id in category_items:
                metadata = _get_item_metadata(item_id)
                if metadata and metadata["price"] > 0:
                    price = metadata["price"]
                    quality = metadata["quality"]
                    item_name = metadata["name"]
                    description = metadata.get("description", "")

                    # Check if player already owns this item
                    # (You can still buy duplicates, but show ownership info)
                    owned_count = sum(1 for item in self.state.items if item.item_id == item_id)
                    ownership_note = f" (owned: {owned_count})" if owned_count > 0 else ""

                    actions.append(ActionMetadata(
                        action_id=f"purchase_{item_id}",
                        display_name=f"Buy {item_name}",
                        description=f"{description} [Quality: {quality}x]{ownership_note}",
                        category=ActionCategory.SHOPPING,
                        requirements={"money": f"{price}p"},
                        effects={
                            "money": f"-{price}p",
                            "item_acquired": item_name,
                            "quality": f"{quality}x",
                            "skill": "resource_management +0.5",
                        },
                        cost_pence=price,
                    ))

        # Add sell actions for items at current location
        for item in items_at_location:
            metadata = _get_item_metadata(item.item_id)
            base_price = metadata.get("price", 0)

            # Calculate sell price
            if base_price > 0:
                condition_multiplier = item.condition_value / 100.0
                sell_price = int(base_price * 0.4 * condition_multiplier)
                sell_price = max(100, sell_price)

                item_display_name = metadata.get("name", item.item_id.replace('_', ' ').title())
                actions.append(ActionMetadata(
                    action_id=f"sell_{item.item_id}",
                    display_name=f"Sell {item_display_name}",
                    description=f"Sell {item_display_name} ({item.condition}) for {sell_price}p (40% of base price)",
                    category=ActionCategory.SHOPPING,
                    requirements={},
                    effects={
                        "money": f"+{sell_price}p",
                        "item_removed": item_display_name,
                        "skill": "resource_management +0.3",
                    },
                    cost_pence=-sell_price,  # Negative cost means gain
                ))

        # Add discard actions for all items at current location
        for item in items_at_location:
            metadata = _get_item_metadata(item.item_id)
            item_display_name = metadata.get("name", item.item_id.replace('_', ' ').title())

            actions.append(ActionMetadata(
                action_id=f"discard_{item.item_id}",
                display_name=f"Discard {item_display_name}",
                description=f"Permanently discard {item_display_name} ({item.condition}) without selling",
                category=ActionCategory.SHOPPING,
                requirements={},
                effects={
                    "item_removed": item_display_name,
                    "habit": "minimalism +2",
                },
                cost_pence=0,
            ))

        # Add job application actions
        from .engine import _check_job_requirements
        for job_id, job_data in JOBS.items():
            # Skip current job
            if job_id == current_job_id:
                continue

            # Check requirements
            meets_requirements, reason = _check_job_requirements(self.state, job_id)

            # Build requirements description
            req_list = []
            requirements = job_data.get("requirements", {})
            if requirements:
                for skill_req in requirements.get("skills", []):
                    skill_name = skill_req["name"].replace('_', ' ').title()
                    min_value = skill_req["min"]
                    current_value = self.state.player.skills_detailed[skill_req["name"]].value
                    met = "✓" if current_value >= min_value else "✗"
                    req_list.append(f"{met} {skill_name}: {int(current_value)}/{min_value}")

                for trait_req in requirements.get("traits", []):
                    trait_name = trait_req["name"].replace('_', ' ').title()
                    min_value = trait_req["min"]
                    current_value = getattr(self.state.player.traits, trait_req["name"], 0)
                    met = "✓" if current_value >= min_value else "✗"
                    req_list.append(f"{met} {trait_name}: {current_value}/{min_value}")

                for item_req in requirements.get("items", []):
                    tag = item_req["tag"]
                    from .engine import _find_item_with_tag
                    has_item = _find_item_with_tag(self.state, tag) is not None
                    met = "✓" if has_item else "✗"
                    req_list.append(f"{met} Requires: {tag.replace('_', ' ').title()}")

            req_desc = "; ".join(req_list) if req_list else "No requirements"
            status = "✓ Eligible" if meets_requirements else f"✗ Not eligible ({reason})"

            actions.append(ActionMetadata(
                action_id=f"apply_job_{job_id}",
                display_name=f"Apply: {job_data['name']}",
                description=f"{job_data['description']} Pay: {job_data['base_pay']}p. {status}. {req_desc}",
                category=ActionCategory.WORK,
                requirements={"status": status},
                effects={
                    "job": job_data['name'] if meets_requirements else "Application rejected",
                    "pay": f"{job_data['base_pay']}p" if meets_requirements else "N/A",
                    "skill": "presence +1.0" if meets_requirements else "N/A",
                },
                cost_pence=0,
            ))

        return actions
