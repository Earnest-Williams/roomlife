"""Social interaction helpers for managing relationships and memory.

This module provides utilities for:
- Relationship management (bidirectional updates)
- Memory tracking (bounded lists)
- Social interaction event logging
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

from .constants import MAX_EVENT_LOG
from .models import NPC, Player, State


def clamp_rel(value: int) -> int:
    """Clamp relationship value to [-100, 100] range.

    Args:
        value: Relationship value

    Returns:
        Clamped value between -100 and 100
    """
    return max(-100, min(100, value))


def bump_relationship(
    actor_like: Union[Player, NPC],
    other_id: str,
    delta: int,
) -> None:
    """Update relationship value between actor and target.

    Args:
        actor_like: Player or NPC object with relationships dict
        other_id: ID of the other party
        delta: Amount to change relationship (positive or negative)
    """
    current = actor_like.relationships.get(other_id, 0)
    actor_like.relationships[other_id] = clamp_rel(current + delta)


def append_memory(
    actor_like: Union[Player, NPC],
    entry: Dict[str, Any],
    limit: int = 100,
) -> None:
    """Append an entry to actor's memory with size limit.

    Memory is a bounded FIFO list. When limit is exceeded,
    oldest entries are removed.

    Args:
        actor_like: Player or NPC object with memory list
        entry: Memory entry dict (should include day, action_id, outcome, etc.)
        limit: Maximum memory size (default 100)
    """
    actor_like.memory.append(entry)
    if len(actor_like.memory) > limit:
        actor_like.memory = actor_like.memory[-limit:]


def record_interaction_event(
    state: State,
    event_id: str,
    **params: Any,
) -> None:
    """Log a social interaction event with proper trimming.

    Args:
        state: Game state
        event_id: Event identifier (e.g., "social.interaction")
        **params: Event parameters
    """
    state.event_log.append({"event_id": event_id, "params": params})
    if len(state.event_log) > MAX_EVENT_LOG:
        state.event_log = state.event_log[-MAX_EVENT_LOG:]


def apply_social_effects(
    state: State,
    actor_id: str,
    target_id: str,
    action_id: str,
    tier: int,
    social_block: Dict[str, Any],
) -> None:
    """Apply bidirectional relationship and memory updates from social block.

    This function is called after a social action's outcome is applied.
    It reads the "social" block from the outcome and updates relationships
    and memory for both actor and target.

    Args:
        state: Game state
        actor_id: ID of the actor (usually "player")
        target_id: ID of the target NPC
        action_id: Action ID
        tier: Outcome tier
        social_block: The "social" dict from the outcome

    Social block format:
        {
            "rel_to_target": +5,        # Actor's relationship to target changes by +5
            "rel_to_actor_on_target": +2,  # Target's relationship to actor changes by +2
            "memory_tag": "pleasant_chat"  # Memory tag for both parties
        }
    """
    if not social_block:
        return

    # Get actor and target objects
    actor = state.player if actor_id == "player" else state.npcs.get(actor_id)
    target = state.npcs.get(target_id) if target_id != "player" else state.player

    if actor is None or target is None:
        return

    # Apply relationship changes
    rel_to_target = social_block.get("rel_to_target", 0)
    if rel_to_target != 0:
        bump_relationship(actor, target_id, rel_to_target)

    rel_to_actor = social_block.get("rel_to_actor_on_target", 0)
    if rel_to_actor != 0:
        bump_relationship(target, actor_id, rel_to_actor)

    # Add memory entries
    memory_tag = social_block.get("memory_tag")
    if memory_tag:
        # Actor's memory
        append_memory(
            actor,
            {
                "day": state.world.day,
                "action_id": action_id,
                "other_id": target_id,
                "tier": tier,
                "tag": memory_tag,
                "initiator": actor_id,
            },
            limit=100,
        )

        # Target's memory
        append_memory(
            target,
            {
                "day": state.world.day,
                "action_id": action_id,
                "other_id": actor_id,
                "tier": tier,
                "tag": memory_tag,
                "initiator": actor_id,
            },
            limit=100,
        )
