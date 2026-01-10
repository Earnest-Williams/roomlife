# RoomLife API Examples

This directory contains working examples demonstrating how to use the RoomLife API with various visualization and UI frameworks.

## Examples

### 1. Basic Usage (`api_basic_usage.py`)

Demonstrates core API functionality:
- Creating a game and API instance
- Getting state snapshots
- Listing available actions
- Validating actions
- Executing actions
- Handling results

**Run:**
```bash
PYTHONPATH=src python examples/api_basic_usage.py
```

### 2. Event Streaming (`api_event_streaming.py`)

Shows how to subscribe to events and state changes for reactive UIs:
- Subscribing to events
- Subscribing to state changes
- Handling events in real-time
- Unsubscribing from events

**Run:**
```bash
PYTHONPATH=src python examples/api_event_streaming.py
```

### 3. Interactive CLI Demo (`api_cli_demo.py`)

Full interactive command-line interface using the API:
- State persistence (save/load)
- Interactive action selection
- Visual state display
- Action execution with feedback

**Run:**
```bash
PYTHONPATH=src python examples/api_cli_demo.py
```

**Controls:**
- Type action name and press Enter to execute
- Type `save` to save game
- Type `quit` to exit

### 4. JSON Export (`api_json_export.py`)

Demonstrates JSON serialization for web APIs:
- Exporting game state as JSON
- Exporting action metadata as JSON
- Exporting action results as JSON
- Saving JSON to files

**Run:**
```bash
PYTHONPATH=src python examples/api_json_export.py
```

**Output files:**
- `game_state.json` - Current game state
- `available_actions.json` - Currently valid actions
- `all_actions.json` - All possible actions
- `action_result.json` - Result of last action

### 5. GUI Application (`../roomlife_gui.py`)

Full-featured Tkinter GUI (located in root directory):
- Real-time state visualization (needs, traits, utilities)
- Interactive action buttons
- Event log with action outcomes
- Save/Load with file dialogs
- Automatic UI updates via event subscriptions

**Requirements:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Or on macOS/Windows, tkinter is usually pre-installed
```

**Run:**
```bash
python3 roomlife_gui.py
# Or use the launcher:
./launch.sh gui
```

**Features:**
- Status panel showing day, time, location, money
- Progress bars for all needs and traits
- Utilities status display
- Dynamic action buttons that update based on game state
- Scrolling event log
- File menu for save/load/new game

### 6. Launcher Script (`../launch.sh`)

Interactive launcher for all components (located in root directory):
- Menu-based component selection
- Dependency checking
- Multiple launch modes

**Run:**
```bash
./launch.sh          # Interactive menu
./launch.sh gui      # Launch GUI directly
./launch.sh rest     # Launch REST server
./launch.sh cli      # Launch CLI demo
./launch.sh example  # Run basic example
```

### 7. REST API Server (`api_rest_server.py`)

Complete REST API server using Flask:
- RESTful endpoints
- JSON responses
- CORS support for web frontends
- Auto-save on actions

**Requirements:**
```bash
pip install flask flask-cors
```

**Run:**
```bash
PYTHONPATH=src python examples/api_rest_server.py
```

**Endpoints:**
- `GET /api/state` - Get current game state
- `GET /api/actions` - Get available actions
- `GET /api/actions/all` - Get all action metadata
- `GET /api/actions/<id>/validate` - Validate action
- `POST /api/actions/<id>/execute` - Execute action
- `POST /api/save` - Save game
- `POST /api/reset` - Reset game

**Example curl commands:**
```bash
# Get state
curl http://localhost:5000/api/state

# Get actions
curl http://localhost:5000/api/actions

# Execute work action
curl -X POST http://localhost:5000/api/actions/work/execute

# Execute with custom seed
curl -X POST http://localhost:5000/api/actions/study/execute \
  -H "Content-Type: application/json" \
  -d '{"rng_seed": 42}'
```

## Usage Patterns

### Pattern 1: Direct Python Integration

Use the API directly in your Python application:

```python
from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI

state = new_game()
api = RoomLifeAPI(state)

# Get state
snapshot = api.get_state_snapshot()
print(f"Day {snapshot.world.day}")

# Execute action
result = api.execute_action("work")
if result.success:
    print("Action succeeded!")
```

### Pattern 2: Event-Driven UI

Subscribe to events for reactive updates:

```python
def on_state_change(state):
    # Update UI with new state
    update_display(state)

api.subscribe_to_state_changes(on_state_change)

# Now execute actions - UI updates automatically
api.execute_action("work")
```

### Pattern 3: Web Frontend

Use the REST server with any web framework:

```javascript
// Fetch state
const response = await fetch('http://localhost:5000/api/state');
const state = await response.json();

// Execute action
const result = await fetch('http://localhost:5000/api/actions/work/execute', {
    method: 'POST'
});
```

### Pattern 4: Game Engine Integration

Integrate with Unity, Godot, etc.:

```python
from roomlife.api_adapters import UnityAdapter

adapter = UnityAdapter(api)
scene_data = adapter.get_scene_data()
# Pass scene_data to Unity for rendering
```

## File Structure

```
examples/
├── README.md                    # This file
├── api_basic_usage.py          # Basic API usage
├── api_event_streaming.py      # Event streaming demo
├── api_cli_demo.py             # Interactive CLI
├── api_json_export.py          # JSON export demo
└── api_rest_server.py          # REST API server
```

## Next Steps

After exploring these examples:

1. Read the full [API Documentation](../API_DOCUMENTATION.md)
2. Explore the [API types](../src/roomlife/api_types.py)
3. Look at the [API service](../src/roomlife/api_service.py)
4. Check out [adapters](../src/roomlife/api_adapters.py)

## Creating Your Own Visualization

To create your own visualization engine:

1. **Choose an adapter pattern** (REST, WebSocket, Direct)
2. **Subscribe to events** for real-time updates
3. **Use snapshots** for rendering state
4. **Validate actions** before execution
5. **Handle results** and update UI

Example minimal visualization:

```python
from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI

# Initialize
api = RoomLifeAPI(new_game())

# Subscribe to updates
api.subscribe_to_state_changes(lambda state: render(state))

# Game loop
while running:
    action = get_user_input()
    if api.validate_action(action).valid:
        api.execute_action(action)
        # render() is called automatically via subscription
```

## Troubleshooting

### Import Errors

If you get import errors, make sure you're running from the project root:

```bash
cd /path/to/roomlife
python examples/api_basic_usage.py
```

Or install the package:

```bash
pip install -e .
```

### Flask Not Found

For the REST server example:

```bash
pip install flask flask-cors
```

### Save File Issues

Examples create save files in the current directory:
- `demo_savegame.yml` (CLI demo)
- `server_savegame.yml` (REST server)

Delete these to start fresh.

## Contributing

To add a new example:

1. Create a new `.py` file in this directory
2. Add docstring explaining what it demonstrates
3. Include usage instructions in comments
4. Update this README with the new example
5. Test it works from project root

## License

Same as RoomLife project.
