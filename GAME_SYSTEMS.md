# RoomLife Game Systems Documentation

Complete technical guide to RoomLife's NPC, social, director, and pacing systems.

## Table of Contents

1. [Overview](#overview)
2. [NPC System](#npc-system)
3. [Social System](#social-system)
4. [Director System](#director-system)
5. [Pacing System](#pacing-system)
6. [Content Validation](#content-validation)
7. [Determinism](#determinism)
8. [Integration Guide](#integration-guide)

---

## Overview

RoomLife evolved from a single-room survival sim into a richer text/CLI life-sim with:

- **Building NPCs**: Off-screen neighbors, landlords, and maintenance staff
- **Deterministic Events**: NPC-initiated building events using seeded RNG
- **Social Actions**: Player-initiated interactions with NPCs
- **Daily Goals**: Light narrative director suggesting contextual actions
- **Pacing Presets**: Difficulty settings affecting needs decay and event frequency
- **Content Tooling**: Automated validation for action reachability and tier richness

**Core Principle**: Everything is deterministic and reproducible from a single seed.

---

## NPC System

**Module**: `src/roomlife/npc_ai.py`

### Design Philosophy

NPCs are **building contacts** (not roommates). They:
- Live off-screen and interact via hallway encounters and building events
- Are "player-shaped enough" for tier computation (have skills/traits/aptitudes)
- Do NOT have inventory, money, or needs (minimal implementation)
- Remember interactions and develop relationships with the player

### NPC Data Structure

```python
@dataclass
class NPC:
    id: str                                    # e.g., "npc_neighbor_nina"
    display_name: str                          # e.g., "Nina"
    role: str                                  # "neighbor"|"landlord"|"maintenance"

    # For tier computation when NPC is actor
    skills_detailed: Dict[str, Skill]
    aptitudes: Aptitudes
    traits: Traits

    # Social state
    relationships: Dict[str, int]              # Includes "player"
    memory: List[Dict[str, Any]]               # Bounded FIFO, limit 100
```

NPCs are stored in `state.npcs: Dict[str, NPC]`.

### NPC-Initiated Building Events

**Trigger**: Called on day rollover via `maybe_trigger_daily_building_event()`.

**Frequency**: At most **1 event per day**.

**Process**:
1. **Build candidates**: Actions where `dynamic.npc.initiates == true`
2. **Filter by slice**: Check `allowed_slices` (e.g., `["evening", "night"]`)
3. **Enforce cooldowns**: Actions have `cooldown_days` to prevent repetition
4. **Validate**: Run `validate_action_spec()` against current player state
5. **Choose NPC**: Select source NPC deterministically by role
6. **Compute tier**: Use NPC's skills/traits for tier computation (via `_actor_scope`)
7. **Apply outcome**: Outcome affects the player (state.player restored after tier computation)
8. **Log event**: `npc.event` with npc_id, action_id, tier
9. **Update cooldowns**: Store last trigger day in `state.player.flags`

**Example YAML**:
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
  requires:
    # Typically minimal - no items or money
  outcomes:
    0:
      deltas:
        needs:
          mood: -5
          stress: 3
    2:
      deltas:
        needs:
          mood: -2
    3:
      deltas:
        needs:
          mood: 1
```

### NPC Encounters

**Trigger**: Called when player moves to a new space via `on_player_entered_space()`.

**Frequency**: ~15% chance when entering hallway, **at most 1 per day**.

**Process**:
1. **Detect hallway**: Check if `to_space` has "hallway" tag
2. **Roll encounter**: Deterministic roll based on seed components
3. **Choose NPC**: Select NPC by role deterministically
4. **Set flags**: Store `encounter.available` and `encounter.last_day`
5. **Log event**: `npc.encounter` with npc_id, location

Encounters create **opportunities** (set flags) but don't force actions. The player can then initiate social actions.

### Actor Scope (Critical Implementation Detail)

**Problem**: Tier computation needs NPC's skills, but outcomes need to apply to player.

**Solution**: `_actor_scope` context manager temporarily replaces `state.player` with NPC proxy.

```python
@contextmanager
def _actor_scope(state: State, npc: NPC):
    original_player = state.player

    class NPCActor:
        def __getattr__(self, name: str):
            # Use NPC skills/traits/aptitudes for tier computation
            if name in ('skills_detailed', 'aptitudes', 'traits'):
                return getattr(npc, name)
            # Fall back to player for everything else
            return getattr(original_player, name)

    try:
        state.player = NPCActor()  # type: ignore
        yield
    finally:
        state.player = original_player  # Always restore
```

**Usage**:
```python
with _actor_scope(state, npc):
    tier = compute_tier(state, spec, item_meta, rng_seed=tier_seed)
# state.player is now restored to original player
apply_outcome(state, spec, tier, item_meta, current_tick, emit_events=True)
```

---

## Social System

**Module**: `src/roomlife/social.py`

### Relationship Management

Relationships are **bidirectional** and range from **-100 to +100**.

```python
def bump_relationship(actor_like: Union[Player, NPC], other_id: str, delta: int) -> None:
    """Update relationship value between actor and target."""
    current = actor_like.relationships.get(other_id, 0)
    actor_like.relationships[other_id] = clamp_rel(current + delta)
```

**Storage**:
- Player relationships: `state.player.relationships[npc_id]`
- NPC relationships: `state.npcs[npc_id].relationships["player"]`

### Memory System

Both players and NPCs have **bounded memory** (FIFO, limit 100).

```python
def append_memory(actor_like: Union[Player, NPC], entry: Dict[str, Any], limit: int = 100) -> None:
    """Append entry to memory with size limit."""
    actor_like.memory.append(entry)
    if len(actor_like.memory) > limit:
        actor_like.memory = actor_like.memory[-limit:]
```

**Memory Entry Format**:
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

### Social Actions

**Execution Flow**:
1. Player executes action with `target_npc_id` parameter
2. Action validation checks:
   - Player is in hallway (location requirement)
   - Target NPC exists in `state.npcs`
   - Parameter type `npc_id` is valid
3. Tier computation uses **player's** skills (player is actor)
4. Outcome applies to player (mood, stress, etc.)
5. **Social post-hook** runs after outcome:
   - Reads `social` block from outcome
   - Updates bidirectional relationships
   - Appends memory to both parties
   - Logs `social.interaction` event

**Example Social Action**:
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
  modifiers:
    primary_skill: presence
    secondary_skills:
      articulation: 0.25
    traits:
      empathy: 0.20
  outcomes:
    2:
      deltas:
        needs:
          mood: 3
          stress: -1
      social:
        rel_to_target: 5           # Player's relationship to NPC +5
        rel_to_actor_on_target: 4  # NPC's relationship to player +4
        memory_tag: "pleasant_chat"
```

**Social Block Fields**:
- `rel_to_target`: How much actor's relationship to target changes
- `rel_to_actor_on_target`: How much target's relationship to actor changes
- `memory_tag`: Tag stored in both memories

### Parameter Validation

**Extension**: `src/roomlife/param_resolver.py`

New parameter type `npc_id` validates:
- Parameter exists in ActionCall.params
- Value exists in state.npcs
- Returns validation failure (not exception) if invalid

```python
# In validate_parameters()
if param_type == "npc_id":
    npc_id = params.get(param_name)
    if not npc_id or npc_id not in state.npcs:
        missing.append(f"npc_id:{param_name}")
```

---

## Director System

**Module**: `src/roomlife/director.py`

### Purpose

A **light narrative director** that suggests 2-4 daily goals based on player needs and context.

**Not**: An intrusive quest system or forced storyline.

**Is**: A helpful assistant that surfaces relevant actions.

### Daily Goal Seeding

**Trigger**: Called on day rollover via `seed_daily_goals()`.

**Process**:
1. **Build candidates**: Actions where `dynamic.director.suggest == true`
2. **Score urgency**: Weight actions by player needs and flags
   - High hunger? Prioritize food actions
   - Low money? Suggest income actions
   - High stress? Recommend relaxation
3. **Pick 2-4 goals**: Deterministic weighted sampling
4. **Validate each goal**: Run `validate_action_spec()` at current location
5. **Generate previews**: Use `preview_tier_distribution()` and `build_preview_notes()`
6. **Store in flags**: Save to `state.player.flags["goals.today"]`
7. **Log event**: `director.goals_seeded` with goal_action_ids

**Goal Structure**:
```python
{
    "action_id": "cook_basic_meal",
    "valid": True,
    "reason": "",                    # Empty if valid, else reason why not
    "missing": [],                   # List of missing requirements
    "tier_distribution": {           # Probability distribution
        0: 0.0,
        1: 0.33,
        2: 0.44,
        3: 0.23
    },
    "notes": [                       # Human-readable preview notes
        "Primary skill: nutrition (2.5)",
        "Optional: item providing 'cook_surface'"
    ]
}
```

### Urgency Scoring

```python
def _score_action_urgency(state: State, action_id: str, spec: Any) -> float:
    score = 1.0  # Base score
    needs = state.player.needs

    # Example scoring logic:
    if "hunger" in need_deltas and needs.hunger > 60:
        score += 2.0
    if "fatigue" in need_deltas and needs.fatigue > 60:
        score += 2.0
    if "finance" in tags and state.player.money_pence < 2000:
        score += 1.5

    return score
```

Higher scores = more likely to be suggested.

### Director YAML Configuration

```yaml
- id: cook_basic_meal
  display_name: "Cook basic meal"
  category: survival
  dynamic:
    director:
      suggest: true
      tags: ["selfcare", "survival"]
      cooldown_days: 0
```

**Tags** (advisory):
- `selfcare`: Hygiene, mood, stress reduction
- `chore`: Maintenance, cleaning
- `finance`: Income, expense management
- `social`: Social interactions

**Cooldown**: Optional days before action can be suggested again.

---

## Pacing System

**Storage**: `state.player.flags["pacing"]` = `"relaxed"` | `"normal"` | `"hard"`

**Default**: `"normal"`

### Pacing Effects

| Aspect | Relaxed | Normal | Hard |
|--------|---------|--------|------|
| Needs decay rate | 0.75x | 1.0x | 1.25x |
| NPC event frequency | 0.5x | 1.0x | 1.5x |
| Random event probability | 0.5x | 1.0x | 1.5x |

**Implementation**:
```python
# In environment update:
pacing = state.player.flags.get("pacing", "normal")
multiplier = {
    "relaxed": 0.75,
    "normal": 1.0,
    "hard": 1.25
}[pacing]

# Apply to needs decay
needs.hunger += int(base_decay * multiplier)
```

**Determinism**: Pacing changes do not affect RNG stream. Multipliers are applied to computed values, not random seeds.

---

## Content Validation

**Tool**: `tools/validate_content.py`

### Purpose

Automated checks to ensure content quality and accessibility.

### Validation Checks

#### 1. Reachability

**Goal**: At least 90% of actions should be reachable by typical player archetypes.

**Method**:
- Create 4 archetypes: fresh_start, skilled, broke, master
- Run `validate_action_spec()` for each action against each archetype
- Track which actions are reachable by at least one archetype

**Output**:
```
Reachable actions: 45/50 (90.0%)
Unreachable actions: 5
  building.landlord_eviction
    Common blockers: requires 'landlord_office' space
```

#### 2. Tier Richness

**Goal**: At least 70% of actions should have rich tier distributions (not degenerate).

**Criteria**:
- At least 2 different tiers occur
- No single tier dominates (>90% probability)

**Method**:
- Run `preview_tier_distribution()` with 9 samples
- Check diversity of resulting distribution

**Output**:
```
Rich tier distributions: 42/50 (84.0%)
Degenerate tiers: 8
  social.intimidate
    Issues: single tier dominates (94%)
    Distribution: T0:6%, T1:94%
```

### Usage

```bash
# Run validation
python tools/validate_content.py

# Exit codes:
# 0 = PASS (all thresholds met)
# 1 = FAIL (some thresholds violated)
```

**Integration**: Can be run in CI/CD to catch content issues before release.

---

## Determinism

**Core Principle**: Same seed = same simulation trajectory.

### RNG Architecture

**Master Seed**: `state.world.rng_seed` (set once during `new_game(seed)`)

**Local RNG**: Each system creates its own `random.Random(local_seed)`:
```python
# NPC events
day_seed = state.world.rng_seed + state.world.day * 97
rng = random.Random(day_seed)

# Encounters
encounter_seed = (
    state.world.rng_seed
    + state.world.day * 97
    + TIME_SLICES.index(state.world.slice) * 13
    + stable_hash(location)
)
rng = random.Random(encounter_seed)

# Director
day_seed = state.world.rng_seed + state.world.day * 97
rng = random.Random(day_seed)
```

**Critical Rules**:
1. **Never use Python's global random**: Always create local `random.Random(seed)`
2. **Never consume engine RNG**: NPC/director have their own RNG instances
3. **Use stable hashing**: `zlib.crc32()` not `hash()` (which is not stable across runs)
4. **Sort before iterating**: Always `sorted(action_specs.items())` for stable ordering

### Stable Hash

```python
def stable_hash(s: str) -> int:
    """Stable hash using zlib.crc32 (not Python hash)."""
    return zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF
```

**Why not `hash()`?**: Python's `hash()` is randomized per-process for security. `zlib.crc32()` is deterministic.

### Testing Determinism

```python
# Create two games with same seed
state1 = engine.new_game(seed=123)
state2 = engine.new_game(seed=123)

# Advance both identically
for _ in range(7):
    engine.apply_action(state1, "sleep")
    engine.apply_action(state2, "sleep")

# Compare event logs
events1 = [e for e in state1.event_log if e["event_id"] == "npc.event"]
events2 = [e for e in state2.event_log if e["event_id"] == "npc.event"]

assert events1 == events2  # Must match exactly
```

---

## Integration Guide

### Adding NPC-Initiated Events

1. **Create action YAML**:
```yaml
- id: building.water_shutoff
  display_name: "Water shutoff notice"
  category: building_event
  dynamic:
    npc:
      initiates: true
      weight: 0.5
      roles: ["maintenance"]
      allowed_slices: ["morning"]
      cooldown_days: 7
  outcomes:
    0:
      deltas:
        flags:
          water_shutoff_warned: true
      events: [{ id: "building.water_notice" }]
```

2. **No code changes needed**. The NPC AI system discovers it automatically.

### Adding Social Actions

1. **Create action YAML**:
```yaml
- id: social.complain_about_noise
  display_name: "Complain about noise"
  category: social
  parameters:
    - name: target_npc_id
      type: npc_id
      required: true
  requires:
    location:
      any_space_tags: ["hallway"]
  modifiers:
    primary_skill: articulation
    traits:
      confidence: 0.20
  outcomes:
    2:
      deltas:
        needs:
          stress: -3
      social:
        rel_to_target: -5
        rel_to_actor_on_target: -3
        memory_tag: "noise_complaint"
```

2. **No code changes needed**. The social post-hook handles relationship updates automatically.

### Adding Director Goals

1. **Tag existing actions**:
```yaml
- id: exercise
  display_name: "Exercise"
  category: health
  dynamic:
    director:
      suggest: true
      tags: ["health", "selfcare"]
      cooldown_days: 1
```

2. **No code changes needed**. Director discovers and scores actions automatically.

### Extending NPC Roles

1. **Add NPC in new_game()** (in `src/roomlife/engine.py`):
```python
def new_game(seed: int = 0, location: str = "room_001") -> State:
    # ... existing code ...

    # Add new NPC
    state.npcs["npc_super_johnson"] = NPC(
        id="npc_super_johnson",
        display_name="Johnson",
        role="superintendent",
        skills_detailed=_default_skills_detailed(),
        aptitudes=Aptitudes(),
        traits=Traits(discipline=60, confidence=70),
        relationships={"player": 0},
        memory=[],
    )
```

2. **Use in YAML**:
```yaml
dynamic:
  npc:
    roles: ["superintendent"]
```

---

## File Overview

| File | Lines | Purpose |
|------|-------|---------|
| `src/roomlife/npc_ai.py` | ~310 | NPC-initiated events, encounters, actor scoping |
| `src/roomlife/social.py` | ~160 | Relationship/memory management, social post-hook |
| `src/roomlife/director.py` | ~225 | Daily goal seeding, urgency scoring, tier previews |
| `tools/validate_content.py` | ~295 | Content reachability/richness validation |
| `tests/test_npc_system.py` | ~250 | Comprehensive determinism and integration tests |

**Total**: ~992 lines of new code + minimal diffs to existing files.

---

## Best Practices

### DO ✅

- Use `stable_hash()` for deterministic hashing
- Sort collections before iterating for stable ordering
- Create local RNG instances with deterministic seeds
- Always restore `state.player` in finally blocks
- Bound memory lists to prevent unbounded growth
- Log events with structured params for debugging
- Validate actions before execution
- Use `_log()` helper when available for consistent event logging

### DON'T ❌

- Use Python's global `random` module
- Use Python's `hash()` builtin
- Consume the engine's existing RNG stream
- Mutate state during validation
- Assume NPC exists without checking `state.npcs.get()`
- Trigger more than 1 NPC event per day
- Forget to update cooldowns after events
- Skip parameter validation for social actions

---

## Future Extensions

**Planned but not yet implemented:**

1. **Content Packs**: `data/packs/<pack_id>/actions.yaml` with deterministic merge
2. **Advanced NPC Schedules**: Time-based NPC location tracking
3. **Relationship Thresholds**: Unlock special actions at high relationship levels
4. **Memory Queries**: Allow actions to check NPC memory for context
5. **Telemetry**: Metrics collection for balance tuning (Phase 4.3 from plan)

See `docs/implementation-plan.md` for the full roadmap.

---

## Questions & Troubleshooting

### Q: Why aren't NPCs appearing?

A: Check:
1. NPCs are initialized in `new_game()`
2. You're in a hallway space (has "hallway" tag)
3. Encounter rolled (15% chance per hallway entry, max 1/day)

### Q: Why aren't social actions available?

A: Check:
1. Current location has "hallway" tag
2. Target NPC exists in `state.npcs`
3. Action validation passes (use `validate_action_spec()`)

### Q: Why aren't goals being suggested?

A: Check:
1. Actions have `dynamic.director.suggest: true`
2. Not on cooldown (`director.cooldown.<action_id>` flag)
3. Director system is being called on day rollover
4. Goals are stored in `state.player.flags["goals.today"]`

### Q: How do I debug determinism issues?

A:
1. Check event logs for NPC events: `[e for e in state.event_log if "npc" in e["event_id"]]`
2. Verify seed is set: `state.world.rng_seed`
3. Look for sorted iteration: `sorted(candidates)`
4. Check for global random usage (should be none)

### Q: Where are NPC events logged?

A: In `state.event_log` with event_id `"npc.event"` or `"npc.encounter"`. Access via:
```python
npc_events = [e for e in state.event_log if e["event_id"] in ["npc.event", "npc.encounter"]]
```

---

## Summary

RoomLife's game systems provide:

- **Deterministic NPC interactions** with minimal state overhead
- **Rich social gameplay** via bidirectional relationships and memory
- **Contextual guidance** through the director's daily goals
- **Flexible difficulty** via pacing presets
- **Quality assurance** through automated content validation

All systems are:
- ✅ Deterministic and reproducible
- ✅ Backward compatible with schema v1 saves
- ✅ Extensible via YAML without code changes
- ✅ Well-tested and documented

For implementation details, see the source files. For API usage, see `API_DOCUMENTATION.md`.
