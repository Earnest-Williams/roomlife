#!/usr/bin/env python3
"""Basic API usage example.

This example demonstrates the core functionality of the RoomLife API.
"""

from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI


def main():
    print("="*60)
    print("RoomLife API - Basic Usage Example")
    print("="*60)

    # Create a new game
    print("\n1. Creating new game...")
    state = new_game()
    api = RoomLifeAPI(state)
    print("✓ Game created")

    # Get initial state snapshot
    print("\n2. Getting state snapshot...")
    snapshot = api.get_state_snapshot()
    print(f"✓ Day {snapshot.world.day}, {snapshot.world.slice}")
    print(f"  Location: {snapshot.current_location.name}")
    print(f"  Money: £{snapshot.player_money_pence / 100:.2f}")

    # Display needs
    print("\n3. Current needs:")
    for need, value in snapshot.needs.to_dict().items():
        bar = "█" * (value // 5) + "░" * (20 - value // 5)
        print(f"  {need.capitalize():12} [{bar}] {value:3}")

    # Get available actions
    print("\n4. Available actions:")
    actions = api.get_available_actions()
    print(f"  Total: {actions.total_count}")
    for action in actions.actions[:5]:  # Show first 5
        print(f"  - {action.action_id}: {action.description}")

    # Validate an action
    print("\n5. Validating 'work' action...")
    validation = api.validate_action("work")
    if validation.valid:
        print("  ✓ Action is valid")
    else:
        print(f"  ✗ Action invalid: {validation.reason}")

    # Execute an action
    print("\n6. Executing 'work' action...")
    result = api.execute_action("work")
    if result.success:
        print("  ✓ Action succeeded!")
        if result.state_changes:
            print("  Changes:")
            for key, value in result.state_changes.items():
                print(f"    {key}: {value}")
        if result.events_triggered:
            print("  Events:")
            for event in result.events_triggered:
                print(f"    - {event.event_id}")
    else:
        print("  ✗ Action failed")

    # Get updated state
    print("\n7. Updated state:")
    new_snapshot = api.get_state_snapshot()
    print(f"  Day {new_snapshot.world.day}, {new_snapshot.world.slice}")
    print(f"  Money: £{new_snapshot.player_money_pence / 100:.2f}")
    print(f"  Fatigue: {new_snapshot.needs.fatigue}")

    # Show skills gained
    print("\n8. Skills with XP:")
    for skill in new_snapshot.skills:
        if skill.value > 0:
            print(f"  {skill.name}: {skill.value:.2f}")

    # Demonstrate action validation failure
    print("\n9. Testing invalid action (shower without being in bathroom)...")
    validation = api.validate_action("shower")
    if not validation.valid:
        print(f"  ✗ As expected: {validation.reason}")
        if validation.missing_requirements:
            print(f"    Missing: {', '.join(validation.missing_requirements)}")

    # Get action metadata
    print("\n10. Action metadata example:")
    all_actions = api.get_all_actions_metadata()
    work_action = next(a for a in all_actions if a.action_id == "work")
    print(f"  Action: {work_action.display_name}")
    print(f"  Category: {work_action.category}")
    print(f"  Description: {work_action.description}")
    print("  Effects:")
    for effect_key, effect_value in work_action.effects.items():
        print(f"    {effect_key}: {effect_value}")

    print("\n" + "="*60)
    print("Example complete!")
    print("="*60)


if __name__ == "__main__":
    main()
