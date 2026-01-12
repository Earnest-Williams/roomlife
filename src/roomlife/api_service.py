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

        # No YAML spec found - action is unknown
        return ActionValidation(
            valid=False,
            action_id=action_id,
            reason="Unknown action (no spec found)",
        )

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
        return self._get_catalog_action_metadata_list()

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

            # Generate preview for better player clarity
            preview = None
            if spec is not None:
                # Cheap + deterministic previews
                tier_dist = preview_tier_distribution(
                    self.state, spec, self._item_meta, rng_seed=1, samples=9
                )
                delta_ranges = preview_delta_ranges(spec)
                notes = build_preview_notes(self.state, spec, self._item_meta, card.call)
                preview = ActionPreview(
                    tier_distribution=tier_dist,
                    delta_ranges=delta_ranges,
                    notes=notes,
                )

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
                preview=preview,
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
