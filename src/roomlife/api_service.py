"""Main API service for RoomLife simulation.

This service provides a clean interface for visualization engines
to interact with the simulation, including state queries, action execution,
validation, and event streaming.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from .api_types import (
    ActionCategory,
    ActionMetadata,
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
                item_id=item.item_id,
                condition=item.condition,
                condition_value=item.condition_value,
                placed_in=item.placed_in,
                slot=item.slot,
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
                    item_id=item.item_id,
                    condition=item.condition,
                    condition_value=item.condition_value,
                    placed_in=item.placed_in,
                    slot=item.slot,
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
        actions = self._get_action_metadata_list()

        # Filter to only valid actions
        valid_actions = []
        for action in actions:
            validation = self.validate_action(action.action_id)
            if validation.valid:
                valid_actions.append(action)

        return AvailableActionsResponse(
            actions=valid_actions,
            location=self.state.world.location,
            total_count=len(valid_actions),
        )

    def get_all_actions_metadata(self) -> List[ActionMetadata]:
        """Get metadata for all possible actions (even if not currently valid).

        Returns:
            List of ActionMetadata for all actions
        """
        return self._get_action_metadata_list()

    def validate_action(self, action_id: str) -> ActionValidation:
        """Validate if an action can be executed in the current state.

        Args:
            action_id: The action to validate

        Returns:
            ActionValidation with validation result
        """
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
            # Extract item_id and index from action_id (e.g., "repair_bed_basic_5" -> "bed_basic", 5)
            parts = action_id[7:].rsplit('_', 1)  # Remove "repair_" prefix and split from right
            
            if len(parts) == 2 and parts[1].isdigit():
                # New format with index: repair_{item_id}_{index}
                item_id = parts[0]
                item_index = int(parts[1])
                
                # Get the item by index
                if 0 <= item_index < len(self.state.items):
                    item_to_repair = self.state.items[item_index]
                    # Verify the item matches expectations (correct item_id and location)
                    if item_to_repair.item_id != item_id or item_to_repair.placed_in != self.state.world.location:
                        item_to_repair = None
                else:
                    item_to_repair = None
            else:
                # Legacy format without index: repair_{item_id}
                repair_prefix_len = len("repair_")
                item_id = action_id[repair_prefix_len:]
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

        # Handle sell actions
        if action_id.startswith("sell_"):
            from .engine import _get_item_metadata
            
            # Extract item_id and index from action_id (e.g., "sell_bed_basic_5" -> "bed_basic", 5)
            sell_prefix_len = len("sell_")
            parts = action_id[sell_prefix_len:].rsplit('_', 1)  # Remove "sell_" prefix and split from right
            
            if len(parts) == 2 and parts[1].isdigit():
                # New format with index: sell_{item_id}_{index}
                item_id = parts[0]
                item_index = int(parts[1])
                
                # Get the item by index
                if 0 <= item_index < len(self.state.items):
                    item_to_sell = self.state.items[item_index]
                    # Verify the item matches expectations (correct item_id and location)
                    if item_to_sell.item_id != item_id or item_to_sell.placed_in != self.state.world.location:
                        item_to_sell = None
                else:
                    item_to_sell = None
            else:
                # Legacy format without index: sell_{item_id}
                sell_prefix_len = len("sell_")
                item_id = action_id[sell_prefix_len:]
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

            # Check if item has a price (can be sold)
            metadata = _get_item_metadata(item_to_sell.item_id)
            base_price = metadata.get("price", 0)
            if base_price <= 0:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item cannot be sold (starter item)",
                )

            return ActionValidation(valid=True, action_id=action_id)

        # Handle purchase actions
        if action_id.startswith("purchase_"):
            from .engine import _get_item_metadata
            
            purchase_prefix_len = len("purchase_")
            item_id = action_id[purchase_prefix_len:]  # Remove "purchase_" prefix
            metadata = _get_item_metadata(item_id)
            
            if not metadata:
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Item not found in catalog",
                )
            
            price = metadata.get("price", 0)
            if self.state.player.money_pence < price:
                missing.append(f"need {price}p (have {self.state.player.money_pence}p)")
                return ActionValidation(
                    valid=False,
                    action_id=action_id,
                    reason="Insufficient funds",
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

    def execute_action(self, action_id: str, rng_seed: Optional[int] = None) -> ActionResult:
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
        apply_action(self.state, action_id, rng_seed)

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
        actions = [
            ActionMetadata(
                action_id="work",
                display_name="Work",
                description="Do freelance work to earn money",
                category=ActionCategory.WORK,
                requirements={},
                effects={
                    "money": "+3500p",
                    "fatigue": "+15 (discipline adjusted)",
                    "mood": "-2",
                    "skill": "technical_literacy +2.0",
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
        # Use enumerate on state.items to track the actual index for unique action_ids
        for item_index, item in enumerate(self.state.items):
            if item.placed_in != current_location:
                continue
            
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
                    action_id=f"repair_{item.item_id}_{item_index}",
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
            category_name = category.get("name", "Items")
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
        # Use enumerate on state.items to track the actual index for unique action_ids
        for item_index, item in enumerate(self.state.items):
            if item.placed_in != current_location:
                continue
                
            metadata = _get_item_metadata(item.item_id)
            base_price = metadata.get("price", 0)

            # Calculate sell price
            if base_price > 0:
                condition_multiplier = item.condition_value / 100.0
                sell_price = int(base_price * 0.4 * condition_multiplier)
                sell_price = max(100, sell_price)

                item_display_name = metadata.get("name", item.item_id.replace('_', ' ').title())
                actions.append(ActionMetadata(
                    action_id=f"sell_{item.item_id}_{item_index}",
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

        return actions
