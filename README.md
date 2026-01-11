# roomlife

A text-first lifesim engine where most play is reflected in a single room (and later a renderer can be attached).

## Requirements
- Python 3.11+
- Dependencies listed in `environment.yml` (pyyaml, rich, typer, pytest, ruff)

## Setup

### Option 1: sdc + direnv
From the project directory, run:
- `sdc` for a new environment
- `sdc -u` to update an existing environment from `environment.yml`
- `sdc -f` to remove and recreate the environment

### Option 2: Manual setup
If you are not using sdc, create an environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pyyaml rich typer
```

## Run

### Quick Start with Launcher Script
The easiest way to run RoomLife is using the launcher script:
```bash
./launch.sh
```

This will show an interactive menu with options to launch:
- GUI Application (Tkinter)
- REST API Server
- CLI Demo
- Basic API Example

Or launch specific components directly:
```bash
./launch.sh gui      # Launch the GUI application
./launch.sh rest     # Launch the REST API server
./launch.sh cli      # Launch the CLI demo
./launch.sh example  # Run basic API example
```

### Traditional CLI
```bash
python -m roomlife status
python -m roomlife act work
python -m roomlife act eat_charity_rice
python -m roomlife dump
```

Notes:
- The CLI defaults to `saves/save_001.yaml` for load/save.
- Use `--save path/to/save.yaml` to target a different save file.
- Use `--seed N` for deterministic action execution.

### GUI Application
Launch the graphical interface:
```bash
python3 roomlife_gui.py
```

Features:
- Real-time state visualization (needs, traits, utilities)
- Interactive action buttons
- Event log
- Save/Load functionality
- Location and time tracking

## Layout
- `src/roomlife/`: engine, models, IO, view-model, CLI, API
  - `api_service.py`: Main RoomLife API service
  - `api_types.py`: API type definitions
  - `api_adapters.py`: Example adapters for different platforms
- `data/`: content (YAML)
- `saves/`: save snapshots
- `tests/`: determinism and invariants
- `examples/`: API usage examples (basic, CLI, REST server, event streaming)
- `examples/README.md`: How to run each example
- `roomlife_gui.py`: Tkinter GUI application
- `launch.sh`: Launcher script for all components
- `API_DOCUMENTATION.md`: Complete API reference
