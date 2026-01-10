#!/usr/bin/env python3
"""REST API server example using Flask.

This example shows how to create a REST API server for RoomLife
that can be consumed by web frontends.

Install dependencies:
    pip install flask flask-cors

Run:
    python api_rest_server.py

Then access:
    http://localhost:5000/api/state
    http://localhost:5000/api/actions
    etc.
"""

try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
except ImportError:
    print("Error: Flask not installed")
    print("Install with: pip install flask flask-cors")
    exit(1)

from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI
from roomlife.api_adapters import RESTAdapter, StatePersistenceAdapter


# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for web frontends

# Load or create game
persistence = StatePersistenceAdapter("server_savegame.yml")
api = persistence.create_api()
adapter = RESTAdapter(api)
adapter.initialize()


@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current game state."""
    return jsonify(adapter.get_state())


@app.route('/api/actions', methods=['GET'])
def get_actions():
    """Get available actions."""
    return jsonify(adapter.get_actions())


@app.route('/api/actions/all', methods=['GET'])
def get_all_actions():
    """Get all action metadata."""
    return jsonify(adapter.get_all_actions())


@app.route('/api/actions/<action_id>/validate', methods=['GET'])
def validate_action(action_id):
    """Validate if action can be executed."""
    return jsonify(adapter.validate_action(action_id))


@app.route('/api/actions/<action_id>/execute', methods=['POST'])
def execute_action(action_id):
    """Execute an action."""
    data = request.get_json() or {}
    rng_seed = data.get('rng_seed')
    result = adapter.execute_action(action_id, rng_seed)

    # Auto-save after each action
    persistence.save(api)

    return jsonify(result)


@app.route('/api/save', methods=['POST'])
def save_game():
    """Manually save game state."""
    persistence.save(api)
    return jsonify({"status": "saved"})


@app.route('/api/reset', methods=['POST'])
def reset_game():
    """Reset game to new state."""
    global api, adapter
    state = new_game()
    api = RoomLifeAPI(state)
    adapter = RESTAdapter(api)
    adapter.initialize()
    persistence.save(api)
    return jsonify({"status": "reset"})


@app.route('/', methods=['GET'])
def index():
    """API documentation."""
    return jsonify({
        "name": "RoomLife REST API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/state": "Get current game state",
            "GET /api/actions": "Get available actions",
            "GET /api/actions/all": "Get all action metadata",
            "GET /api/actions/<id>/validate": "Validate action",
            "POST /api/actions/<id>/execute": "Execute action",
            "POST /api/save": "Save game",
            "POST /api/reset": "Reset game",
        },
        "example_curl": {
            "get_state": "curl http://localhost:5000/api/state",
            "execute_work": "curl -X POST http://localhost:5000/api/actions/work/execute",
        }
    })


if __name__ == '__main__':
    print("="*60)
    print("RoomLife REST API Server")
    print("="*60)
    print("\nStarting server on http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  GET  /api/state")
    print("  GET  /api/actions")
    print("  GET  /api/actions/all")
    print("  GET  /api/actions/<id>/validate")
    print("  POST /api/actions/<id>/execute")
    print("  POST /api/save")
    print("  POST /api/reset")
    print("\nExample curl commands:")
    print("  curl http://localhost:5000/api/state")
    print("  curl -X POST http://localhost:5000/api/actions/work/execute")
    print("\nPress Ctrl+C to stop")
    print("="*60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
