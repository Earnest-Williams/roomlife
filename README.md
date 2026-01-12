# RoomLife

A text-first life simulation engine focused on modeling a character's daily activities, needs, and decision-making within a single room environment. RoomLife provides multiple interfaces (GUI, CLI, and REST API) for interacting with the simulation.

## Features

- **Dynamic Need System**: Track and manage character needs like hunger, energy, hygiene, and more
- **Action-Based Gameplay**: Perform actions that affect character state and needs over time
- **Multiple Interfaces**:
  - **GUI**: Tkinter-based graphical interface with real-time visualization
  - **CLI**: Command-line interface for quick interactions
  - **REST API**: HTTP API for integration with other applications
- **Event System**: Subscribe to state changes and events in real-time
- **Save/Load**: Persistent save system with YAML-based storage
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

## Project Structure

```
roomlife/
├── src/roomlife/       # Core engine and game logic
│   ├── api_service.py  # REST API service
│   ├── api_types.py    # API type definitions
│   └── ...
├── data/               # Game content (YAML files)
├── saves/              # Save game files
├── examples/           # API usage examples
├── tests/              # Test suite
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
