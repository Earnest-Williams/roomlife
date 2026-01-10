#!/usr/bin/env python3
"""Event streaming example.

This example demonstrates how to subscribe to events and state changes.
"""

from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI
from roomlife.api_types import EventInfo, GameStateSnapshot


def main():
    print("="*60)
    print("RoomLife API - Event Streaming Example")
    print("="*60)

    # Create game and API
    state = new_game()
    api = RoomLifeAPI(state)

    # Event counter
    event_count = {"count": 0}
    state_change_count = {"count": 0}

    # Define event handler
    def on_event(event: EventInfo):
        event_count["count"] += 1
        print(f"\n📢 Event #{event_count['count']}: {event.event_id}")
        if event.params:
            print(f"   Params: {event.params}")

    # Define state change handler
    def on_state_change(state: GameStateSnapshot):
        state_change_count["count"] += 1
        print(f"\n🔄 State Change #{state_change_count['count']}")
        print(f"   Day {state.world.day}, {state.world.slice}")
        print(f"   Location: {state.current_location.name}")
        print(f"   Money: £{state.player_money_pence / 100:.2f}")

    # Subscribe to events
    print("\n1. Subscribing to events and state changes...")
    api.subscribe_to_events(on_event)
    api.subscribe_to_state_changes(on_state_change)
    print("✓ Subscribed")

    # Execute some actions
    print("\n2. Executing actions (events will be displayed as they occur)...")
    print("\n--- Action: work ---")
    api.execute_action("work")

    print("\n--- Action: study ---")
    api.execute_action("study")

    print("\n--- Action: sleep ---")
    api.execute_action("sleep")

    # Try to execute an invalid action
    print("\n--- Action: shower (invalid - wrong location) ---")
    api.execute_action("shower")

    # Move to bathroom
    print("\n--- Action: move to hallway ---")
    api.execute_action("move_hall_001")

    print("\n--- Action: move to bathroom ---")
    api.execute_action("move_bath_001")

    print("\n--- Action: shower (now valid) ---")
    api.execute_action("shower")

    # Summary
    print("\n" + "="*60)
    print(f"Summary:")
    print(f"  Total events: {event_count['count']}")
    print(f"  Total state changes: {state_change_count['count']}")
    print("="*60)

    # Unsubscribe
    print("\n3. Unsubscribing...")
    api.unsubscribe_from_events(on_event)
    api.unsubscribe_from_state_changes(on_state_change)
    print("✓ Unsubscribed")

    # Execute action after unsubscribe (no events should be printed)
    print("\n4. Executing action after unsubscribe (no events should print)...")
    api.execute_action("work")
    print("✓ Action executed (but no events printed)")

    print("\n" + "="*60)
    print("Example complete!")
    print("="*60)


if __name__ == "__main__":
    main()
