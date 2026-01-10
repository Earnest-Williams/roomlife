"""Example adapters for different visualization engines.

This module demonstrates how to adapt the RoomLife API to various
UI/UX frameworks and protocols (REST, WebSocket, CLI, etc.).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from .api_service import RoomLifeAPI
from .api_types import EventInfo, GameStateSnapshot
from .engine import new_game
from .io import load_state, save_state
from .models import State


class VisualizationAdapter(ABC):
    """Base class for visualization adapters."""

    def __init__(self, api: RoomLifeAPI):
        """Initialize adapter with API instance."""
        self.api = api

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the adapter."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the adapter."""
        pass


class RESTAdapter(VisualizationAdapter):
    """Adapter for REST API-style interfaces.

    This adapter shows how to expose the RoomLife API as REST endpoints.
    Can be used with frameworks like Flask, FastAPI, etc.
    """

    def initialize(self) -> None:
        """Initialize REST adapter."""
        print("REST adapter initialized")

    def shutdown(self) -> None:
        """Shutdown REST adapter."""
        print("REST adapter shutdown")

    def get_state(self) -> Dict[str, Any]:
        """GET /api/state - Get current game state."""
        snapshot = self.api.get_state_snapshot()
        return snapshot.to_dict()

    def get_actions(self) -> Dict[str, Any]:
        """GET /api/actions - Get available actions."""
        actions = self.api.get_available_actions()
        return actions.to_dict()

    def get_all_actions(self) -> Dict[str, Any]:
        """GET /api/actions/all - Get all action metadata."""
        actions = self.api.get_all_actions_metadata()
        return {
            "actions": [action.to_dict() for action in actions],
            "total_count": len(actions),
        }

    def validate_action(self, action_id: str) -> Dict[str, Any]:
        """GET /api/actions/{action_id}/validate - Validate action."""
        validation = self.api.validate_action(action_id)
        return validation.to_dict()

    def execute_action(self, action_id: str, rng_seed: Optional[int] = None) -> Dict[str, Any]:
        """POST /api/actions/{action_id}/execute - Execute action."""
        result = self.api.execute_action(action_id, rng_seed)
        return result.to_dict()


class WebSocketAdapter(VisualizationAdapter):
    """Adapter for WebSocket-based real-time interfaces.

    This adapter demonstrates event streaming over WebSocket connections.
    """

    def __init__(self, api: RoomLifeAPI):
        super().__init__(api)
        self.connected_clients: List[Callable[[str], None]] = []

    def initialize(self) -> None:
        """Initialize WebSocket adapter."""
        # Subscribe to events and state changes
        self.api.subscribe_to_events(self._on_event)
        self.api.subscribe_to_state_changes(self._on_state_change)
        print("WebSocket adapter initialized")

    def shutdown(self) -> None:
        """Shutdown WebSocket adapter."""
        self.api.unsubscribe_from_events(self._on_event)
        self.api.unsubscribe_from_state_changes(self._on_state_change)
        self.connected_clients.clear()
        print("WebSocket adapter shutdown")

    def connect_client(self, send_callback: Callable[[str], None]) -> None:
        """Register a new WebSocket client.

        Args:
            send_callback: Function to send messages to client
        """
        self.connected_clients.append(send_callback)

        # Send initial state
        snapshot = self.api.get_state_snapshot()
        message = json.dumps({
            "type": "state_update",
            "data": snapshot.to_dict(),
        })
        send_callback(message)

    def disconnect_client(self, send_callback: Callable[[str], None]) -> None:
        """Unregister a WebSocket client."""
        if send_callback in self.connected_clients:
            self.connected_clients.remove(send_callback)

    def handle_message(self, message: str) -> str:
        """Handle incoming WebSocket message.

        Args:
            message: JSON message from client

        Returns:
            JSON response to send back to client
        """
        data = json.loads(message)
        msg_type = data.get("type")

        if msg_type == "get_state":
            snapshot = self.api.get_state_snapshot()
            return json.dumps({
                "type": "state_update",
                "data": snapshot.to_dict(),
            })

        elif msg_type == "get_actions":
            actions = self.api.get_available_actions()
            return json.dumps({
                "type": "actions_list",
                "data": actions.to_dict(),
            })

        elif msg_type == "execute_action":
            action_id = data.get("action_id")
            rng_seed = data.get("rng_seed")
            result = self.api.execute_action(action_id, rng_seed)
            return json.dumps({
                "type": "action_result",
                "data": result.to_dict(),
            })

        else:
            return json.dumps({
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            })

    def _on_event(self, event: EventInfo) -> None:
        """Handle game events and broadcast to clients."""
        message = json.dumps({
            "type": "event",
            "data": event.to_dict(),
        })
        self._broadcast(message)

    def _on_state_change(self, state: GameStateSnapshot) -> None:
        """Handle state changes and broadcast to clients."""
        message = json.dumps({
            "type": "state_update",
            "data": state.to_dict(),
        })
        self._broadcast(message)

    def _broadcast(self, message: str) -> None:
        """Broadcast message to all connected clients."""
        for client in self.connected_clients:
            try:
                client(message)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")


class CLIAdapter(VisualizationAdapter):
    """Adapter for command-line interfaces.

    This adapter provides a simple text-based interface.
    """

    def initialize(self) -> None:
        """Initialize CLI adapter."""
        print("CLI adapter initialized")

    def shutdown(self) -> None:
        """Shutdown CLI adapter."""
        print("CLI adapter shutdown")

    def display_state(self) -> None:
        """Display current state in CLI format."""
        snapshot = self.api.get_state_snapshot()

        print("\n" + "="*60)
        print(f"Day {snapshot.world.day} - {snapshot.world.slice.title()}")
        print(f"Location: {snapshot.current_location.name}")
        print(f"Money: £{snapshot.player_money_pence / 100:.2f}")
        print("="*60)

        print("\nNeeds:")
        for need, value in snapshot.needs.to_dict().items():
            bar = "█" * (value // 5) + "░" * (20 - value // 5)
            print(f"  {need.capitalize():12} [{bar}] {value:3}")

        print("\nTraits:")
        for trait, value in snapshot.traits.to_dict().items():
            bar = "█" * (value // 10) + "░" * (10 - value // 10)
            print(f"  {trait.capitalize():12} [{bar}] {value:3}")

        print("\nUtilities:")
        print(f"  Power: {'✓' if snapshot.utilities.power else '✗'}")
        print(f"  Heat:  {'✓' if snapshot.utilities.heat else '✗'}")
        print(f"  Water: {'✓' if snapshot.utilities.water else '✗'}")

        if snapshot.recent_events:
            print("\nRecent Events:")
            for event in snapshot.recent_events[-3:]:
                print(f"  - {event.event_id}")

    def display_actions(self) -> None:
        """Display available actions in CLI format."""
        actions = self.api.get_available_actions()

        print(f"\nAvailable Actions ({actions.total_count}):")
        print("-" * 60)

        by_category: Dict[str, List] = {}
        for action in actions.actions:
            category = action.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(action)

        for category, category_actions in by_category.items():
            print(f"\n{category.upper()}:")
            for action in category_actions:
                print(f"  {action.action_id:20} - {action.description}")
                if action.cost_pence:
                    print(f"    {'':20}   Cost: £{action.cost_pence / 100:.2f}")

    def execute_action_interactive(self, action_id: str) -> None:
        """Execute action and display results."""
        print(f"\nExecuting: {action_id}")

        # Validate first
        validation = self.api.validate_action(action_id)
        if not validation.valid:
            print(f"❌ Action invalid: {validation.reason}")
            if validation.missing_requirements:
                print(f"   Missing: {', '.join(validation.missing_requirements)}")
            return

        # Execute
        result = self.api.execute_action(action_id)

        if result.success:
            print("✓ Action completed successfully")
        else:
            print("✗ Action failed")

        # Display state changes
        if result.state_changes:
            print("\nChanges:")
            for key, value in result.state_changes.items():
                print(f"  {key}: {value}")

        # Display events
        if result.events_triggered:
            print("\nEvents:")
            for event in result.events_triggered:
                print(f"  - {event.event_id}")


class StatePersistenceAdapter:
    """Adapter for saving/loading game state.

    This adapter handles state persistence to files.
    """

    def __init__(self, save_path: str = "savegame.yml"):
        """Initialize persistence adapter.

        Args:
            save_path: Path to save file
        """
        self.save_path = save_path

    def create_api(self) -> RoomLifeAPI:
        """Create or load API instance with state.

        Returns:
            RoomLifeAPI instance with loaded or new state
        """
        try:
            state = load_state(self.save_path)
            print(f"Loaded state from {self.save_path}")
        except FileNotFoundError:
            state = new_game()
            print("Created new game")

        return RoomLifeAPI(state)

    def save(self, api: RoomLifeAPI) -> None:
        """Save current state to file.

        Args:
            api: API instance to save
        """
        save_state(api.state, self.save_path)
        print(f"Saved state to {self.save_path}")


class ReactAdapter(VisualizationAdapter):
    """Conceptual adapter for React/Web frontend.

    This demonstrates the interface a React app would use.
    In practice, this would be implemented as a REST or WebSocket adapter
    with a React frontend consuming the API.
    """

    def initialize(self) -> None:
        """Initialize React adapter."""
        print("React adapter initialized")
        # In real implementation, this would set up the API server

    def shutdown(self) -> None:
        """Shutdown React adapter."""
        print("React adapter shutdown")

    def get_initial_props(self) -> Dict[str, Any]:
        """Get initial props for React component.

        Returns:
            Props dictionary for React component
        """
        snapshot = self.api.get_state_snapshot()
        actions = self.api.get_available_actions()

        return {
            "gameState": snapshot.to_dict(),
            "availableActions": actions.to_dict(),
            "apiEndpoint": "/api",
        }

    def setup_event_stream(self, on_event: Callable[[EventInfo], None]) -> None:
        """Setup event streaming for React components.

        Args:
            on_event: Callback for events
        """
        self.api.subscribe_to_events(on_event)

    def setup_state_stream(self, on_state_change: Callable[[GameStateSnapshot], None]) -> None:
        """Setup state streaming for React components.

        Args:
            on_state_change: Callback for state changes
        """
        self.api.subscribe_to_state_changes(on_state_change)


class UnityAdapter(VisualizationAdapter):
    """Conceptual adapter for Unity game engine.

    This demonstrates how Unity could integrate with the simulation.
    """

    def initialize(self) -> None:
        """Initialize Unity adapter."""
        print("Unity adapter initialized")
        # Setup event callbacks for Unity

    def shutdown(self) -> None:
        """Shutdown Unity adapter."""
        print("Unity adapter shutdown")

    def get_scene_data(self) -> Dict[str, Any]:
        """Get data for Unity scene rendering.

        Returns:
            Scene data for Unity
        """
        snapshot = self.api.get_state_snapshot()

        return {
            "player": {
                "needs": snapshot.needs.to_dict(),
                "traits": snapshot.traits.to_dict(),
                "money": snapshot.player_money_pence,
            },
            "environment": {
                "location": snapshot.current_location.to_dict(),
                "utilities": snapshot.utilities.to_dict(),
                "time_of_day": snapshot.world.slice,
            },
            "objects": [item.to_dict() for item in snapshot.current_location.items],
        }

    def on_player_action(self, action_id: str) -> Dict[str, Any]:
        """Handle player action from Unity.

        Args:
            action_id: Action to execute

        Returns:
            Result of action
        """
        result = self.api.execute_action(action_id)
        return result.to_dict()
