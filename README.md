# RoomLife

A text-first life simulation engine focused on modeling a character's daily activities, needs, and decision-making within a single room environment. RoomLife provides multiple interfaces (GUI, CLI, and REST API) for interacting with the simulation.

## Features

### Core Simulation
- **Dynamic Need System**: Track and manage character needs like hunger, energy, hygiene, and more
- **Action-Based Gameplay**: Perform actions that affect character state and needs over time
- **Skill & Trait System**: 12 distinct skills with deterministic progression and trait-based modifiers
- **Health & Consequences**: Health deteriorates when needs are extreme, creating meaningful stakes

### Social & NPCs
- **Building NPCs**: Interact with neighbors, landlords, and maintenance staff
- **NPC-Initiated Events**: NPCs trigger building events (noise complaints, maintenance notices, etc.)
- **Player-Initiated Social Actions**: Chat, apologize, request maintenance from NPCs
- **Relationship System**: Bidirectional relationships with memory tracking
- **Encounter System**: Random NPC encounters in hallways and shared spaces

### Director & Pacing
- **Daily Goals**: Light narrative director suggests 2-4 contextual goals each day
- **Goal Validation**: Each goal includes validation status and tier preview
- **Pacing Presets**: Relaxed/normal/hard difficulty affects needs decay and event frequency
- **Deterministic Gameplay**: Fully reproducible simulation with seed-based RNG

### Content & Tools
- **Scalable Content**: Optional content packs system for modular expansion
- **Content Validation**: Automated tooling checks action reachability and tier richness
- **Event System**: Subscribe to state changes and events in real-time
- **Save/Load**: Persistent save system with backward-compatible schema versioning

### Multiple Interfaces
- **GUI**: Tkinter-based graphical interface with real-time visualization
- **CLI**: Command-line interface for quick interactions
- **REST API**: HTTP API for integration with other applications
- **Extensible Architecture**: Easy to add new actions, needs, and mechanics

## Requirements

- Python 3.11 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Earnest-Williams/roomlife.git
cd roomlife
```

2. Create a virtual environment and activate it:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install pyyaml rich typer pytest ruff
```

4. Set up Python path (for development):
```bash
export PYTHONPATH="$PWD/src"  # On Windows: set PYTHONPATH=%CD%\src
```

## Getting Started

### Quick Start with Launcher

The easiest way to run RoomLife is using the launcher script:
```bash
./launch.sh
```

This will show an interactive menu with options to:
- Launch the GUI Application
- Start the REST API Server
- Run the CLI Demo
- View API Examples

Or launch specific components directly:
```bash
./launch.sh gui      # Launch the GUI application
./launch.sh rest     # Launch the REST API server
./launch.sh cli      # Launch the CLI demo
./launch.sh example  # Run basic API example
```

### Using the GUI

The graphical interface provides the most user-friendly way to interact with RoomLife:

```bash
python3 roomlife_gui.py
```

**Features:**
- Real-time visualization of character needs, traits, and utilities
- Interactive action buttons for all available actions
- Event log to track what's happening
- Save and load game functionality
- Location and time tracking

### Using the CLI

For quick interactions via command line:

```bash
python -m roomlife status                # View character status
python -m roomlife act work              # Perform the 'work' action
python -m roomlife act eat_charity_rice  # Eat food
python -m roomlife dump                  # View full game state
```

**Options:**
- `--save path/to/save.yaml` - Use a specific save file (default: `saves/save_001.yaml`)
- `--seed N` - Use a specific random seed for deterministic behavior

### Using the REST API

Start the API server to integrate RoomLife with other applications:

```bash
./launch.sh rest
```

See `API_DOCUMENTATION.md` for complete API reference and usage examples.

## Game Systems

### NPCs & Social Interactions

The game features building NPCs (neighbors, landlords, maintenance staff) who:
- Live off-screen but interact via hallway encounters and building events
- Have their own skills, traits, and aptitudes for deterministic interactions
- Initiate events like noise complaints, maintenance notices, and friendly visits
- Remember interactions and develop relationships with the player

**Social Actions:**
- `social.chat_neighbor` - Friendly conversation (builds relationship)
- `social.apologize_noise` - Apologize for disturbances
- `social.request_maintenance` - Ask for building repairs

All social actions use the `target_npc_id` parameter and modify bidirectional relationships.

### Director System

A light narrative director provides daily guidance:
- **Daily Goals**: 2-4 contextually relevant actions suggested each morning
- **Smart Scoring**: Goals prioritize urgent needs and player circumstances
- **Preview Information**: Each goal includes validation status and tier probability distribution
- **Deterministic**: Same seed produces same goal sequence

Goals are stored in `state.player.flags["goals.today"]` and refresh on day rollover.

### Pacing System

Three difficulty presets control game rhythm:
- **Relaxed**: Slower needs decay, fewer random events
- **Normal**: Balanced gameplay (default)
- **Hard**: Faster needs decay, more frequent challenges

Pacing is stored in `state.player.flags["pacing"]` and affects environment updates.

### Content Validation

Built-in tooling ensures content quality:
```bash
python tools/validate_content.py
```

Checks:
- **Reachability**: At least 90% of actions accessible to typical archetypes
- **Tier Richness**: At least 70% of actions have meaningful outcome variation
- **Reports**: Detailed metrics on unreachable actions and degenerate tiers

## Project Structure

```
roomlife/
├── src/roomlife/       # Core engine and game logic
│   ├── api_service.py  # REST API service
│   ├── api_types.py    # API type definitions
│   ├── npc_ai.py       # NPC event system and encounters
│   ├── social.py       # Relationship and memory management
│   ├── director.py     # Daily goals and narrative cadence
│   └── ...
├── data/               # Game content (YAML files)
├── saves/              # Save game files
├── examples/           # API usage examples
├── tests/              # Test suite
├── tools/              # Content validation and development tools
├── roomlife_gui.py     # GUI application
└── launch.sh           # Launcher script
```

## Documentation

- **[API Documentation](API_DOCUMENTATION.md)**: Complete reference for the REST API
- **[Examples](examples/README.md)**: Sample code demonstrating API usage

## Contributing

Contributions are welcome! This project follows standard Python development practices:

```bash
# Run tests
pytest tests/

# Format code
ruff format .

# Lint code
ruff check .
```

## License

See the LICENSE file for details.
