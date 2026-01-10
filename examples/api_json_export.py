#!/usr/bin/env python3
"""JSON export example.

This example demonstrates how to export game state as JSON,
useful for web APIs and external visualization tools.
"""

import json
from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI


def main():
    print("="*60)
    print("RoomLife API - JSON Export Example")
    print("="*60)

    # Create game and API
    state = new_game()
    api = RoomLifeAPI(state)

    # Execute some actions to generate interesting state
    print("\n1. Setting up game state...")
    api.execute_action("work")
    api.execute_action("study")
    print("✓ Actions executed")

    # Export state as JSON
    print("\n2. Exporting state as JSON...")
    snapshot = api.get_state_snapshot()
    state_json = json.dumps(snapshot.to_dict(), indent=2)

    # Save to file
    with open("game_state.json", "w") as f:
        f.write(state_json)
    print("✓ State exported to game_state.json")

    # Show sample of JSON
    print("\n3. Sample of exported JSON (first 50 lines):")
    print("-" * 60)
    lines = state_json.split("\n")
    for line in lines[:50]:
        print(line)
    if len(lines) > 50:
        print(f"... ({len(lines) - 50} more lines)")
    print("-" * 60)

    # Export actions metadata
    print("\n4. Exporting actions metadata as JSON...")
    actions = api.get_available_actions()
    actions_json = json.dumps(actions.to_dict(), indent=2)

    with open("available_actions.json", "w") as f:
        f.write(actions_json)
    print("✓ Actions exported to available_actions.json")

    # Export all actions metadata
    print("\n5. Exporting all actions metadata...")
    all_actions = api.get_all_actions_metadata()
    all_actions_dict = {
        "actions": [action.to_dict() for action in all_actions],
        "total_count": len(all_actions),
    }
    all_actions_json = json.dumps(all_actions_dict, indent=2)

    with open("all_actions.json", "w") as f:
        f.write(all_actions_json)
    print("✓ All actions exported to all_actions.json")

    # Demonstrate action result JSON
    print("\n6. Executing action and exporting result as JSON...")
    result = api.execute_action("eat_charity_rice")
    result_json = json.dumps(result.to_dict(), indent=2)

    with open("action_result.json", "w") as f:
        f.write(result_json)
    print("✓ Action result exported to action_result.json")

    print("\n7. Files created:")
    print("  - game_state.json (current game state)")
    print("  - available_actions.json (currently valid actions)")
    print("  - all_actions.json (all possible actions)")
    print("  - action_result.json (result of last action)")

    print("\n" + "="*60)
    print("Example complete!")
    print("These JSON files can be used by web frontends,")
    print("visualization tools, or external APIs.")
    print("="*60)


if __name__ == "__main__":
    main()
