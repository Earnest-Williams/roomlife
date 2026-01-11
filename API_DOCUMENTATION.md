# RoomLife Visualization API Documentation

This document describes the RoomLife API for attaching various visualization and UI/UX engines to the simulation.

## Overview

The RoomLife API provides a clean, typed interface for visualization engines to interact with the simulation. It supports:

- **State Queries**: Get complete snapshots of game state
- **Action Execution**: Execute actions and get results
- **Action Validation**: Check if actions are valid before execution
- **Action Metadata**: Get information about available actions
- **Event Streaming**: Subscribe to events and state changes in real-time
- **JSON Serialization**: All data types can be converted to JSON

## Architecture

The API consists of three main layers:

1. **api_types.py**: Type definitions for all API data structures
2. **api_service.py**: Core API service (RoomLifeAPI class)
3. **api_adapters.py**: Example adapters for different platforms

```
┌─────────────────────────────────────┐
│  Visualization Engine               │
│  (React, Unity, CLI, etc.)          │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  Adapter Layer                      │
│  (REST, WebSocket, Direct)          │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  RoomLifeAPI                        │
│  (Core API Service)                 │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  Simulation Engine                  │
│  (State, Actions, Events)           │
└─────────────────────────────────────┘
```

## Quick Start

### Launcher Script

The easiest way to get started is using the launcher script:

```bash
./launch.sh
```

This provides an interactive menu to launch:
- **GUI Application**: Tkinter-based graphical interface
- **REST API Server**: Flask-based REST endpoints
- **CLI Demo**: Interactive command-line interface
- **Basic Examples**: Simple API usage demonstrations

Or launch directly:
```bash
./launch.sh gui      # Launch GUI
./launch.sh rest     # Launch REST server
./launch.sh cli      # Launch CLI demo
./launch.sh example  # Run basic example
```

### GUI Application

The Tkinter GUI provides a complete visualization interface:

```bash
python3 roomlife_gui.py
```

**Features:**
- Real-time state visualization
  - Needs tracking (hunger, fatigue, warmth, hygiene, mood, stress, energy, health, illness, injury)
  - Traits display (discipline, confidence, empathy, fitness, etc.)
  - Utilities status (power, heat, water)
- Interactive action buttons for all available actions
- Event log showing game events and outcomes
- Save/Load functionality with file dialogs
- Location and time tracking
- Money and utilities payment status

**GUI Components:**
- **Status Panel**: Displays day, time, location, money, and utilities status
- **Needs Panel**: Progress bars for all player needs
- **Traits Panel**: Progress bars for all character traits
- **Utilities Panel**: Status of power, heat, and water
- **Actions Panel**: Dynamic buttons for available actions
- **Event Log**: Scrolling log of all game events and action results

The GUI uses the event subscription system to automatically update when state changes occur.

### CLI (Typer) Entry Points

The CLI is a lightweight way to inspect state and execute actions.

```bash
python -m roomlife status
python -m roomlife act work --seed 42
python -m roomlife dump --save saves/alt_save.yaml
```

Notes:
- Defaults to `saves/save_001.yaml` when `--save` is not provided.
- `act` requires a positive integer seed for deterministic execution.

### Basic Usage

```python
from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI

# Create or load a game state
state = new_game()

# Create API instance
api = RoomLifeAPI(state)

# Get current state snapshot
snapshot = api.get_state_snapshot()
print(f"Day {snapshot.world.day}, {snapshot.world.slice}")
print(f"Location: {snapshot.current_location.name}")
print(f"Money: {snapshot.player_money_pence}p")

# Get available actions
actions = api.get_available_actions()
for action in actions.actions:
    print(f"- {action.action_id}: {action.description}")

# Validate an action
validation = api.validate_action("work")
if validation.valid:
    print("Action is valid!")

# Execute an action
result = api.execute_action("work")
if result.success:
    print("Action succeeded!")
    print(f"State changes: {result.state_changes}")
```

### With Event Streaming

```python
from roomlife.api_service import RoomLifeAPI
from roomlife.api_types import EventInfo, GameStateSnapshot

api = RoomLifeAPI(state)

# Subscribe to events
def on_event(event: EventInfo):
    print(f"Event: {event.event_id}")
    print(f"Params: {event.params}")

api.subscribe_to_events(on_event)

# Subscribe to state changes
def on_state_change(state: GameStateSnapshot):
    print(f"State updated! Day {state.world.day}")

api.subscribe_to_state_changes(on_state_change)

# Now execute actions - callbacks will be triggered
api.execute_action("work")
```

## Core API Reference

### RoomLifeAPI Class

The main API class for interacting with the simulation.

#### Constructor

```python
api = RoomLifeAPI(state: State)
```

Creates an API instance with the given game state.

#### Methods

##### get_state_snapshot() → GameStateSnapshot

Returns a complete snapshot of the current game state including:
- World info (day, time, location, tick)
- Player needs (hunger, fatigue, etc.)
- Player traits (discipline, fitness, etc.)
- Skills and aptitudes
- Utilities status
- Current location with items
- All locations
- Recent events

```python
snapshot = api.get_state_snapshot()
print(f"Hunger: {snapshot.needs.hunger}")
print(f"Location: {snapshot.current_location.name}")
```

##### get_available_actions() → AvailableActionsResponse

Returns all currently valid actions with their metadata.

```python
actions = api.get_available_actions()
for action in actions.actions:
    print(f"{action.action_id}: {action.description}")
    print(f"  Category: {action.category}")
    print(f"  Effects: {action.effects}")
```

##### get_all_actions_metadata() → List[ActionMetadata]

Returns metadata for all possible actions (even if not currently valid).

```python
all_actions = api.get_all_actions_metadata()
for action in all_actions:
    print(f"{action.action_id} - {action.display_name}")
```

##### validate_action(action_id: str) → ActionValidation

Validates if an action can be executed in the current state. Checks:
- Whether the action ID is known (rejects unknown actions)
- Whether location requirements are met
- Whether utility requirements are met
- Whether the player has sufficient funds
- Whether required items are present

If the action is valid, the response includes a preview showing probable outcomes.

```python
validation = api.validate_action("shower")
if not validation.valid:
    print(f"Cannot shower: {validation.reason}")
    print(f"Missing: {validation.missing_requirements}")
else:
    # Action is valid - preview is available
    if validation.preview:
        print(f"Outcome probabilities: {validation.preview.tier_distribution}")
        print(f"Expected changes: {validation.preview.delta_ranges}")
        print(f"Notes: {validation.preview.notes}")

# Unknown actions are rejected
validation = api.validate_action("invalid_action_xyz")
assert not validation.valid  # True
assert validation.reason == "Unknown action"  # True
```

##### execute_action(action_id: str, rng_seed: Optional[int] = None) → ActionResult

Executes an action and returns the result. The `success` field indicates whether the action completed successfully. Actions fail if they trigger any of these events:
- `action.failed` - Action couldn't be performed (e.g., wrong location, missing utilities)
- `action.unknown` - Action ID not recognized by the engine
- `bills.unpaid` - Insufficient funds to pay bills

```python
result = api.execute_action("work", rng_seed=42)
if result.success:
    print("Action succeeded!")
    print(f"Changes: {result.state_changes}")
    for event in result.events_triggered:
        print(f"Event: {event.event_id}")
else:
    print("Action failed!")
    # Check events to see why it failed
```

##### subscribe_to_events(callback: Callable[[EventInfo], None]) → None

Subscribe to game events.

```python
def handle_event(event: EventInfo):
    print(f"Event: {event.event_id}")

api.subscribe_to_events(handle_event)
```

##### subscribe_to_state_changes(callback: Callable[[GameStateSnapshot], None]) → None

Subscribe to state changes.

```python
def handle_state_change(state: GameStateSnapshot):
    print(f"State changed at day {state.world.day}")

api.subscribe_to_state_changes(handle_state_change)
```

##### unsubscribe_from_events(callback: Callable[[EventInfo], None]) → None

Unsubscribe from game events.

```python
def handle_event(event: EventInfo):
    print(f"Event: {event.event_id}")

# Subscribe
api.subscribe_to_events(handle_event)

# Later, unsubscribe
api.unsubscribe_from_events(handle_event)
```

##### unsubscribe_from_state_changes(callback: Callable[[GameStateSnapshot], None]) → None

Unsubscribe from state changes.

```python
def handle_state_change(state: GameStateSnapshot):
    print(f"State changed at day {state.world.day}")

# Subscribe
api.subscribe_to_state_changes(handle_state_change)

# Later, unsubscribe
api.unsubscribe_from_state_changes(handle_state_change)
```

## Data Types Reference

### GameStateSnapshot

Complete snapshot of game state.

**Fields:**
- `world: WorldInfo` - World/time information
- `player_money_pence: int` - Player's money in pence
- `utilities_paid: bool` - Whether utilities are paid
- `needs: NeedsSnapshot` - Player needs
- `traits: TraitsSnapshot` - Player traits
- `utilities: UtilitiesSnapshot` - Utilities status
- `skills: List[SkillInfo]` - All skills
- `aptitudes: Dict[str, float]` - Aptitude values
- `habit_tracker: Dict[str, int]` - Habit accumulation
- `current_location: LocationInfo` - Current location
- `all_locations: Dict[str, LocationInfo]` - All locations
- `recent_events: List[EventInfo]` - Recent events
- `schema_version: int` - State schema version

**Methods:**
- `to_dict() → Dict[str, Any]` - Convert to JSON-serializable dict

### ActionMetadata

Metadata about an action.

**Fields:**
- `action_id: str` - Unique action identifier
- `display_name: str` - Human-readable name
- `description: str` - Action description
- `category: ActionCategory` - Category (WORK, SURVIVAL, etc.)
- `requirements: Dict[str, Any]` - Requirements to execute
- `effects: Dict[str, str]` - Expected effects
- `cost_pence: Optional[int]` - Money cost
- `requires_location: Optional[str]` - Required location
- `requires_utilities: Optional[List[str]]` - Required utilities
- `requires_items: Optional[List[str]]` - Required items

### ActionValidation

Result of validating an action before execution.

**Fields:**
- `valid: bool` - Whether the action can be executed
- `action_id: str` - The action that was validated
- `reason: Optional[str]` - Reason why action is invalid (empty if valid)
- `missing_requirements: List[str]` - List of missing requirements (empty if valid)
- `preview: Optional[ActionPreview]` - Preview of action outcomes (only present if valid)

**Methods:**
- `to_dict() → Dict[str, Any]` - Convert to JSON-serializable dict

**Usage:**
Call `api.validate_action(action_id)` to check if an action can be executed. If valid, the response includes a preview showing probable outcomes.

### ActionResult

Result of executing an action.

**Fields:**
- `success: bool` - Whether action succeeded
- `action_id: str` - Action that was executed
- `new_state: GameStateSnapshot` - State after action
- `events_triggered: List[EventInfo]` - Events from this action
- `state_changes: Dict[str, Any]` - Summary of changes

### ActionPreview

Preview information for action outcomes, showing probable results before execution.

**Fields:**
- `tier_distribution: Dict[int, float]` - Probability distribution of outcome tiers (0-100 scale)
- `delta_ranges: Dict[str, Any]` - Expected ranges of state changes for each affected attribute
- `notes: List[str]` - Human-readable notes about action effects and requirements

**Methods:**
- `to_dict() → Dict[str, Any]` - Convert to JSON-serializable dict

**Usage:**
The preview is included in `ActionValidation` when an action is valid, allowing UIs to show users what might happen before they execute the action.

### NeedsSnapshot

Player needs (0-100 scale).

**Fields:**
- `hunger: int` - Hunger level (higher = more hungry)
- `fatigue: int` - Fatigue level
- `warmth: int` - Warmth level
- `hygiene: int` - Hygiene level
- `mood: int` - Mood level
- `stress: int` - Stress level
- `energy: int` - Energy level (calculated from fatigue + fitness)
- `health: int` - Health level (0-100, decreases when needs are extreme)
- `illness: int` - Illness level (0-100, higher = more ill)
- `injury: int` - Injury level (0-100, higher = more injured)

## Adapter Examples

The API includes several example adapters showing how to integrate with different platforms.

### REST API Adapter

For web applications using REST endpoints:

```python
from roomlife.api_adapters import RESTAdapter

adapter = RESTAdapter(api)
adapter.initialize()

# Use like REST endpoints
state_dict = adapter.get_state()
actions_dict = adapter.get_actions()
result_dict = adapter.execute_action("work")
```

### WebSocket Adapter

For real-time web applications:

```python
from roomlife.api_adapters import WebSocketAdapter

adapter = WebSocketAdapter(api)
adapter.initialize()

# Connect a client
def send_to_client(message: str):
    # Send JSON message to WebSocket client
    websocket.send(message)

adapter.connect_client(send_to_client)

# Handle incoming messages
response = adapter.handle_message('{"type": "get_state"}')
```

### CLI Adapter

For command-line interfaces:

```python
from roomlife.api_adapters import CLIAdapter

adapter = CLIAdapter(api)
adapter.initialize()

# Display state
adapter.display_state()

# Display actions
adapter.display_actions()

# Execute action interactively
adapter.execute_action_interactive("work")
```

### React/Unity Adapters

See `api_adapters.py` for conceptual adapters showing how to integrate with:
- React web applications
- Unity game engine
- Other visualization frameworks

## Integration Patterns

### Pattern 1: Direct Integration

Use the API directly in your Python application:

```python
api = RoomLifeAPI(state)
snapshot = api.get_state_snapshot()
# Use snapshot data in your visualization
```

### Pattern 2: REST Server

Wrap the API in a REST server (Flask, FastAPI):

```python
from flask import Flask, jsonify
from roomlife.api_adapters import RESTAdapter

app = Flask(__name__)
adapter = RESTAdapter(api)

@app.route('/api/state')
def get_state():
    return jsonify(adapter.get_state())

@app.route('/api/actions/<action_id>/execute', methods=['POST'])
def execute_action(action_id):
    return jsonify(adapter.execute_action(action_id))
```

### Pattern 3: WebSocket Server

For real-time updates:

```python
import asyncio
import websockets
from roomlife.api_adapters import WebSocketAdapter

adapter = WebSocketAdapter(api)

async def handle_client(websocket):
    adapter.connect_client(lambda msg: asyncio.create_task(websocket.send(msg)))
    async for message in websocket:
        response = adapter.handle_message(message)
        await websocket.send(response)

asyncio.run(websockets.serve(handle_client, "localhost", 8765))
```

### Pattern 4: State Persistence

Save and load game state:

```python
from roomlife.api_adapters import StatePersistenceAdapter

persistence = StatePersistenceAdapter("savegame.yml")
api = persistence.create_api()  # Load or create new

# ... use api ...

persistence.save(api)  # Save state
```

## Available Actions

The simulation currently supports these actions:

### Work & Learning
- **work**: Earn money, gain technical_literacy
- **study**: Improve focus skill

### Survival
- **sleep**: Recover fatigue, improve mood
- **eat_charity_rice**: Reduce hunger (free)
- **cook_basic_meal**: Reduce hunger, improve mood (costs 300p, needs kettle/stove)
- **shower**: Improve hygiene and mood (needs bathroom + water)

### Maintenance
- **pay_utilities**: Pay bills to keep utilities active (~2000p)
- **skip_utilities**: Skip payment (utilities will be cut)
- **clean_room**: Improve mood, reduce stress

### Health
- **exercise**: Improve mood, reduce stress, gain reflexivity

### Movement
- **move_<location>**: Move between connected locations

## Event Types

Events are logged when actions occur. Common event types:

- `game.start`: Game started
- `time.advance`: Time advanced to next slice
- `time.new_day`: New day started
- `action.work`: Work action completed
- `action.study`: Study action completed
- `action.sleep`: Sleep action completed
- `action.shower`: Shower action completed
- `action.move`: Movement between locations
- `action.failed`: Action failed (with reason)
- `food.eat`: Food consumed
- `bills.paid`: Utilities paid
- `bills.unpaid`: Insufficient funds for utilities
- `bills.skipped`: Utilities skipped
- `trait.drift`: Trait changed due to habit accumulation
- `utility.no_water`: No water utility
- `utility.no_heat`: No heat utility
- `utility.no_power`: No power utility
- `building.noise`: Random noise event

## Best Practices

### 1. State Management

Always work with snapshots for display:

```python
# Good - use snapshot
snapshot = api.get_state_snapshot()
display_needs(snapshot.needs)

# Bad - don't access internal state directly
display_needs(api.state.player.needs)
```

### 2. Action Validation

Always validate before executing actions:

```python
validation = api.validate_action(action_id)
if validation.valid:
    result = api.execute_action(action_id)
else:
    show_error(validation.reason)
```

### 3. Event Streaming

Use event streaming for reactive UIs:

```python
# Subscribe once at initialization
api.subscribe_to_events(update_ui_on_event)
api.subscribe_to_state_changes(update_ui_on_state)

# Then just execute actions - UI updates automatically
api.execute_action("work")
```

### 4. JSON Serialization

All types have `.to_dict()` for JSON:

```python
snapshot = api.get_state_snapshot()
json_data = snapshot.to_dict()
# Can now send over network, save to file, etc.
```

### 5. Deterministic Simulation

Use consistent rng_seed for reproducibility:

```python
# Same seed = same result
result1 = api.execute_action("work", rng_seed=42)
result2 = api.execute_action("work", rng_seed=42)
# result1 and result2 will be identical
```

## Examples

See the `examples/` directory for complete working examples:

- `api_basic_usage.py`: Basic API usage
- `api_rest_server.py`: REST API server with Flask
- `api_websocket_server.py`: WebSocket server for real-time updates
- `api_cli_demo.py`: Interactive CLI using the API
- `api_event_streaming.py`: Event subscription examples

Additionally:
- `roomlife_gui.py`: Full-featured Tkinter GUI application (in root directory)
- `launch.sh`: Launcher script to coordinate all components (in root directory)

## Contributing

When extending the API:

1. Add new types to `api_types.py`
2. Add new methods to `api_service.py`
3. Update adapters in `api_adapters.py`
4. Document in this file
5. Add examples to `examples/`

## License

Same as RoomLife project.
