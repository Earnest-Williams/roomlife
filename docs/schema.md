# RoomLife Data Schema Documentation

## Overview

The RoomLife simulation uses a structured data model with the following design principles:
- **UI-agnostic**: The engine outputs structured state and structured events
- **Versioned saves**: Schema version tracking enables backward compatibility
- **Deterministic**: RNG seed storage ensures reproducible simulation
- **Extensible**: Flags and dynamic metadata allow content expansion without schema changes

## Schema Version: 2

Current schema version is **2**, which adds:
- **NPCs**: Building NPCs with skills, traits, and relationships
- **Player flags**: Dict for goals, pacing, cooldowns, and dynamic state
- **Player memory**: Bounded list of social interactions
- **World RNG seed**: Deterministic simulation seed

### Migration from Schema Version 1

When loading v1 saves:
- `state.npcs` defaults to empty dict
- `state.player.flags` defaults to empty dict
- `state.player.memory` defaults to empty list
- `state.world.rng_seed` defaults to 0
- All NPCs are initialized on first new day rollover

## Core Data Structures

### State

Top-level game state container.

```python
@dataclass
class State:
    schema_version: int = 2
    world: World
    player: Player
    utilities: Utilities
    spaces: Dict[str, Space]
    items: List[Item]
    event_log: List[dict]
    npcs: Dict[str, NPC]  # Building NPCs by id
```

### World

World/time/location state.

```python
@dataclass
class World:
    day: int = 1
    slice: str = "morning"       # "morning"|"afternoon"|"evening"|"night"
    location: str = "room_001"
    rng_seed: int = 0            # Simulation seed for deterministic NPCs/director
```

**Key**: `rng_seed` is the master seed for all deterministic systems (NPCs, director, encounters). It's set during `new_game(seed)` and never changes during gameplay.

### Player

Player state including needs, skills, relationships, and flags.

```python
@dataclass
class Player:
    money_pence: int = 5000
    utilities_paid: bool = True
    current_job: str = "recycling_collector"
    carry_capacity: int = 12
    needs: Needs
    skills: Dict[str, int]  # Legacy, use skills_detailed
    relationships: Dict[str, int]  # NPC relationships (-100 to +100)
    aptitudes: Aptitudes
    traits: Traits
    skills_detailed: Dict[str, Skill]  # Preferred skill storage
    habit_tracker: Dict[str, int]
    flags: Dict[str, Any]  # NEW: goals, pacing, cooldowns, etc.
    memory: List[Dict[str, Any]]  # NEW: social memory (bounded to 100)
```

**Player Flags**

Common flag keys:
- `"goals.today"`: List[Dict] - Daily goals from director
- `"pacing"`: str - Difficulty preset ("relaxed"|"normal"|"hard")
- `"npc.cooldowns"`: Dict[str, int] - NPC event cooldown tracking
- `"director.cooldown.<action_id>"`: int - Last day action was suggested
- `"encounter.available"`: str - NPC ID from recent encounter
- `"encounter.last_day"`: int - Day of last hallway encounter

**Player Memory**

Social memory entries (bounded FIFO, limit 100):
```python
{
    "day": 5,
    "action_id": "social.chat_neighbor",
    "other_id": "npc_neighbor_nina",
    "tier": 2,
    "tag": "pleasant_chat",
    "initiator": "player"
}
```

### NPC

Building NPC (neighbor, landlord, maintenance). NPCs are off-screen contacts.

```python
@dataclass
class NPC:
    id: str
    display_name: str
    role: str  # "neighbor"|"landlord"|"maintenance"

    # Skills/traits needed for tier computation when NPC is the actor
    skills_detailed: Dict[str, Skill]
    aptitudes: Aptitudes
    traits: Traits

    # Social state
    relationships: Dict[str, int]  # Includes "player"
    memory: List[Dict[str, Any]]  # Bounded to 100
```

**Design Notes**:
- NPCs are "player-shaped enough" for tier computation
- NPCs do not have inventory, money, or needs (minimal implementation)
- NPCs use the same skill/trait/aptitude structure as Player for deterministic tier computation

### Needs

Player needs (0-100 scale).

```python
@dataclass
class Needs:
    hunger: int = 40       # Higher = more hungry
    fatigue: int = 20
    warmth: int = 70
    hygiene: int = 60
    mood: int = 60
    stress: int = 0        # Higher = more stressed
    energy: int = 80       # Derived from fatigue + fitness trait
    health: int = 100      # 0-100, decreases when needs are extreme
    illness: int = 0       # 0-100
    injury: int = 0        # 0-100
```

### Skill

Individual skill state.

```python
@dataclass
class Skill:
    value: float = 0.0      # 0.0-100.0
    rust_rate: float = 0.5  # Decay per day of non-use
    last_tick: int = 0      # Last tick this skill was exercised
```

### Space

Location in the game world.

```python
@dataclass
class Space:
    space_id: str
    name: str
    kind: str
    base_temperature_c: int
    has_window: bool
    connections: List[str]
    tags: List[str]  # e.g., ["hallway"], ["bedroom"], ["kitchen"]
    fixtures: List[str]  # e.g., ["sink"], ["toilet"], ["bed"]
    utilities_available: List[str]  # e.g., ["water", "power", "heat"]
```

**Tags**:
- `"hallway"`: Enables NPC encounters and social actions
- `"bedroom"`: Sleep actions available
- `"bathroom"`: Shower actions available

## Event Log

Events are appended as `{"event_id": str, "params": dict}` and trimmed to `MAX_EVENT_LOG` (default 1000) entries.

### NPC Event IDs

- `"npc.event"`: NPC-initiated building event
  - params: `npc_id`, `npc_name`, `npc_role`, `action_id`, `tier`
- `"npc.encounter"`: Player encountered NPC in hallway
  - params: `npc_id`, `npc_name`, `npc_role`, `location`

### Social Event IDs

- `"social.interaction"`: Player-initiated social action
  - params: `actor`, `target`, `action_id`, `tier`
- `"social.chat"`: Chat outcome
  - params: `outcome` ("awkward"|"okay"|"pleasant"|"delightful")

### Director Event IDs

- `"director.goals_seeded"`: Daily goals selected
  - params: `goal_action_ids` (list), `day`

## Action Specification Extensions

Actions use YAML with optional `dynamic` metadata for NPCs and director.

### NPC-Initiated Actions

```yaml
- id: building.neighbor_noise
  display_name: "Neighbor noise complaint"
  category: building_event
  dynamic:
    npc:
      initiates: true
      weight: 1.0
      roles: ["neighbor"]
      allowed_slices: ["evening", "night"]
      cooldown_days: 2
  # ... rest of action spec
```

### Director-Suggested Actions

```yaml
- id: cook_basic_meal
  display_name: "Cook basic meal"
  category: survival
  dynamic:
    director:
      suggest: true
      tags: ["selfcare", "survival"]
      cooldown_days: 0
  # ... rest of action spec
```

### Social Actions

```yaml
- id: social.chat_neighbor
  display_name: "Chat with neighbor"
  category: social
  parameters:
    - name: target_npc_id
      type: npc_id
      required: true
  requires:
    location:
      any_space_tags: ["hallway"]
  outcomes:
    2:
      deltas:
        needs:
          mood: 3
          stress: -1
      social:
        rel_to_target: 5
        rel_to_actor_on_target: 4
        memory_tag: "pleasant_chat"
```

**Social Block Format**:
- `rel_to_target`: Actor's relationship to target changes by this amount
- `rel_to_actor_on_target`: Target's relationship to actor changes by this amount
- `memory_tag`: Tag stored in both parties' memory

## Save Format

Saves are YAML files with the full State serialized:

```yaml
schema_version: 2
world:
  day: 5
  slice: "afternoon"
  location: "room_001"
  rng_seed: 12345
player:
  money_pence: 3500
  flags:
    pacing: "normal"
    goals.today:
      - action_id: "cook_basic_meal"
        valid: true
        missing: []
  memory:
    - day: 4
      action_id: "social.chat_neighbor"
      other_id: "npc_neighbor_nina"
      tier: 2
      tag: "pleasant_chat"
  # ... rest of player
npcs:
  npc_neighbor_nina:
    id: "npc_neighbor_nina"
    display_name: "Nina"
    role: "neighbor"
    relationships:
      player: 25
    # ... rest of NPC
# ... rest of state
```

## Content Pack Support

**Not yet implemented, but schema is ready.**

Content packs would live in `data/packs/<pack_id>/actions.yaml` and be merged deterministically during spec loading.
