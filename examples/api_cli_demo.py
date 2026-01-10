#!/usr/bin/env python3
"""Interactive CLI demo using the API.

This example shows how to build a simple CLI using the RoomLife API.
"""

from roomlife.engine import new_game
from roomlife.api_adapters import CLIAdapter, StatePersistenceAdapter


def main():
    print("="*60)
    print("RoomLife - Interactive CLI Demo")
    print("="*60)

    # Load or create game
    persistence = StatePersistenceAdapter("demo_savegame.yml")
    api = persistence.create_api()

    # Create CLI adapter
    adapter = CLIAdapter(api)
    adapter.initialize()

    # Game loop
    running = True
    while running:
        # Display state
        adapter.display_state()

        # Display actions
        adapter.display_actions()

        # Get user input
        print("\nEnter action (or 'quit' to exit, 'save' to save):")
        action = input("> ").strip()

        if action == "quit":
            running = False
        elif action == "save":
            persistence.save(api)
            print("✓ Game saved")
        elif action:
            # Execute action
            adapter.execute_action_interactive(action)
        else:
            print("Please enter an action")

    # Save before exit
    print("\nSaving game before exit...")
    persistence.save(api)
    adapter.shutdown()
    print("\nThanks for playing!")


if __name__ == "__main__":
    main()
