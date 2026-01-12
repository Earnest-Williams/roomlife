# RoomLife Implementation Plan

## ✅ IMPLEMENTATION COMPLETE

**Status**: All game systems from Stages 1-3 have been successfully implemented as of January 2026.

**Completed Systems:**
- ✅ **Stage 1**: Building NPC events (npc_ai.py) - Deterministic NPC-initiated events with tier computation under NPC scope
- ✅ **Stage 2**: Social actions + memory + encounters (social.py) - Player-initiated social actions, bidirectional relationships, bounded memory, hallway encounters
- ✅ **Stage 3**: Director + content validation + pacing (director.py, validate_content.py) - Daily goal seeding, tier previews, pacing presets, content linter with reachability/richness metrics

**Key Achievements:**
- 🎯 Fully deterministic simulation with seed-based RNG
- 🎯 Backward-compatible schema v2 with migration support
- 🎯 Comprehensive test coverage (test_npc_system.py)
- 🎯 Content validation tooling with automated metrics
- 🎯 Clean separation: minimal diffs to engine, new focused modules

See the sections below for the original implementation plan that guided this work.

---

## Executive Summary

This plan outlines the phased development strategy for RoomLife, prioritizing features by impact and organizing them into 4 main phases:

1. **Phase 1: MVP Improvements** - Movement, essential actions, item interactions (12-16 hours)
2. **Phase 2: Core Gameplay Systems** - Health, social, economy, random events (16-21 hours)
3. **Phase 3: Content Expansion** - Advanced actions, goals, expanded world (13-17 hours)
4. **Phase 4: Polish & Refinement** - Testing, balance, telemetry/metrics, UI/UX improvements (18-24 hours)

**Total estimated effort:** 59-78 hours for complete implementation

### Acceptance Criteria Framework

Each feature in this plan includes a dedicated **Acceptance Criteria** section with:
- ✓ **Measurable thresholds**: Exact values for stat changes, costs, and effects
- ✓ **Testable conditions**: Specific scenarios that must pass/fail correctly
- ✓ **Verifiable behavior**: Clear success/failure states for each feature
- ✓ **Edge cases**: Boundary conditions and error handling requirements
- ✓ **Integration points**: How features interact with existing systems

These criteria enable precise QA, automated testing, and clear definition of "done" for each feature.

---

## Architecture Analysis

### Current Strengths
- Clean separation of concerns (models, engine, view, IO)
- Sophisticated skill/trait system already in place
- Event logging system ready for expansion
- Schema versioning for backward compatibility
- Data-driven content via YAML files
- Deterministic RNG for testing

### Current Gaps
- 12 skills but only 6 actions (50% utilization)
- Space/Item models exist but are purely decorative
- No player agency in movement or interaction
- Limited gameplay loop (work → pay bills → repeat)
- No social gameplay despite relationship tracking
- No consequences for extreme needs

### Save Migration Strategy
- **Use defaults in loading logic** for newly added fields (e.g., `health=100`) to keep legacy saves playable, aligning with the existing schema versioning/backward compatibility guidance above.
- **Increment `schema_version`** only for breaking structure changes that cannot be safely defaulted.
- **Provide targeted data migrations** when expanding the world (new spaces/items) so older saves can be upgraded to the new content set without losing progress.

---

## UI/UX Phased Rollout Strategy

**Goal:** Introduce UI/UX improvements progressively throughout development rather than as a single late-phase effort. This prevents large UI refactors late in the plan and improves usability as core systems are built.

### Phase 1 UI/UX: Core Action Visibility (Integrated with 1.1-1.3)
**When:** Implemented alongside movement and essential actions
**What:**
- ✓ **Action filtering basics**: Only show movement actions for connected locations
- ✓ **Location-aware action display**: Filter actions by current location (e.g., shower only in bathroom)
- ✓ **Utility-aware action display**: Show/hide utility-dependent actions (shower requires water)
- ✓ **Simple cost preview**: Display basic costs for actions (e.g., "move: +2 fatigue")

**Implementation:**
- Modify `view.py` to filter actions based on location and context
- Add simple cost indicators in parentheses next to action names
- No complex UI library needed yet - basic text formatting

**Rationale:** Players need immediate feedback on what actions are available as spatial gameplay is introduced. Prevents confusion about why actions fail.

---

### Phase 2 UI/UX: Status Warnings & Feedback (Integrated with 2.1-2.4)
**When:** Implemented alongside health system and social features
**What:**
- ✓ **Basic status warnings**: Highlight critical needs with simple markers (e.g., "⚠ Hunger: 85")
- ✓ **Health warnings**: Show health status with visual indicator when below 50
- ✓ **NPC presence indicators**: Show which NPCs are at current location
- ✓ **Event formatting improvements**: Add visual separation for events in log

**Implementation:**
- Add warning symbols (⚠, ‼) to critical stats in view.py
- Simple conditional formatting for health display
- Basic event log formatting with newlines/separators
- Still no external UI dependencies

**Rationale:** Health system introduces stakes that require player awareness. Social system needs clear NPC visibility to encourage interaction.

---

### Phase 3 UI/UX: Progress & Information (Integrated with 3.1-3.2)
**When:** Implemented alongside advanced actions and goals
**What:**
- ✓ **Action details on demand**: Show detailed costs/benefits for actions (command-based or help system)
- ✓ **Goal progress display**: Show active goals with simple progress indicators
- ✓ **Skill progress indicators**: Basic progress display for skills (e.g., "Focus: 45/100")
- ✓ **Smart suggestions (basic)**: Highlight near-complete goals or urgent needs in view

**Implementation:**
- Add `help <action>` command to show detailed action info
- Display goal list with completion status
- Add progress fraction to skill display
- Simple rule-based suggestions in view model

**Rationale:** Goals system needs visibility to be effective. Players need information to make strategic decisions about skill development.

---

### Phase 4 UI/UX: Polish & Rich Formatting (4.4)
**When:** Final polish phase, after core systems complete
**What:**
- ✓ **Rich library integration**: Color-coded warnings (red/yellow/green)
- ✓ **Progress bars**: Visual progress bars for skills, goals, relationships
- ✓ **Enhanced event formatting**: Colors for positive/negative events
- ✓ **Smart suggestions (advanced)**: Context-aware recommendations with rationale
- ✓ **Action preview system**: Show projected stat changes before taking action

**Implementation:**
- Integrate Rich library for terminal formatting
- Full color scheme implementation
- Advanced view model with calculations for projections
- Comprehensive filtering and suggestion engine

**Rationale:** Core gameplay complete - now optimize for readability and user experience. Rich formatting improves comprehension without changing functionality.

---

### UI/UX Feature Toggles

To support progressive rollout and A/B testing, implement feature flags in `constants.py`:

```python
UI_FEATURES = {
    "action_filtering": True,           # Phase 1 (always enabled)
    "cost_preview": True,               # Phase 1 (always enabled)
    "status_warnings": True,            # Phase 2 (always enabled)
    "goal_progress_display": True,      # Phase 3 (always enabled)
    "rich_formatting": False,           # Phase 4 (toggle for testing)
    "smart_suggestions": False,         # Phase 4 (toggle for testing)
    "action_projections": False,        # Phase 4 (toggle for testing)
}
```

**Benefits:**
- Test features independently before full rollout
- Disable advanced UI if terminal compatibility issues arise
- Easy comparison between minimal/rich UI experiences
- Support for testing automation (disable rich formatting in tests)

---

### UI/UX Implementation Checklist

| Phase | Feature | Priority | Implementation Location | Status |
|-------|---------|----------|------------------------|--------|
| 1 | Action filtering by location | HIGH | `view.py`, `_get_available_actions()` | Pending |
| 1 | Basic cost preview | HIGH | `view.py`, action display | Pending |
| 2 | Status warnings (⚠ symbols) | MEDIUM | `view.py`, needs display | Pending |
| 2 | Health status indicator | HIGH | `view.py`, health display | Pending |
| 2 | NPC presence display | MEDIUM | `view.py`, location info | Pending |
| 3 | Action help/details system | MEDIUM | `cli.py`, help command | Pending |
| 3 | Goal progress display | HIGH | `view.py`, goals section | Pending |
| 3 | Skill progress fractions | LOW | `view.py`, skills display | Pending |
| 3 | Basic smart suggestions | MEDIUM | `view.py`, suggestion engine | Pending |
| 4 | Rich library integration | LOW | `cli.py`, full migration | Pending |
| 4 | Color-coded warnings | LOW | `view.py` + `cli.py` | Pending |
| 4 | Progress bars | LOW | `view.py`, Rich integration | Pending |
| 4 | Action projections | LOW | `view.py`, calculation engine | Pending |

---

## Phase 1: MVP Improvements (Immediate Gameplay Impact)

**Goal:** Make the game significantly more engaging with minimal architectural changes.

### 1.1 Movement System (Priority: HIGHEST) ⏱️ 2-3 hours

**Why First:** Unlocks spatial gameplay, very low complexity, high impact.

**Implementation Strategy:**
- Add `move` action to engine.py that changes `state.world.location`
- Validate movement against `space.connections` list
- Add movement cost: fatigue +2, time advances
- Update view.py to show available exits
- Skills affected: None directly (keep simple)

**Files to modify:**
- `src/roomlife/engine.py`: Add `move` action handler
- `src/roomlife/view.py`: Add `available_exits` to view model
- `src/roomlife/constants.py`: Add movement cost constants

**Backward Compatibility:** ✅ Full - just adds new action, doesn't change state structure.

**Acceptance Criteria:**
- ✓ `move <location_id>` action successfully changes `state.world.location`
- ✓ Movement validates against `space.connections` list - invalid moves rejected with error message
- ✓ Each movement costs exactly +2 fatigue
- ✓ Each movement advances time by exactly 1 time slice
- ✓ View displays list of available exits from current location
- ✓ Attempting to move to a non-connected space returns error, does not change location
- ✓ Movement works from any starting location in existing save files
- ✓ Can chain movements: move to A, then A to B, then B to C successfully

---

### 1.2 Basic Item Interactions (Priority: HIGHEST) ⏱️ 3-4 hours

**Why Second:** Enables context-aware actions, uses existing item tags.

**Implementation Strategy:**
- Create `_get_usable_items()` helper that filters items by location and tags
- Modify existing actions to require/benefit from items:
  - `sleep` requires item with "sleep" tag or +10 fatigue cost
  - `study` requires item with "study" tag or -1 skill gain
  - Add `work_from_home` that requires "work" tag desk
- Add item condition degradation on use (pristine→used→worn→broken)
- Add `maintenance` skill integration (reduces degradation)

**Files to modify:**
- `src/roomlife/engine.py`: Add item query helpers and item checks to actions
- `src/roomlife/models.py`: Add method `Item.degrade()`
- `src/roomlife/view.py`: Show which items enable which actions

**Backward Compatibility:** ✅ Full - existing saves work, items just start affecting actions.

**Acceptance Criteria:**
- ✓ `_get_usable_items()` returns only items at player's current location
- ✓ `_get_usable_items()` filters items by tag (e.g., tag="sleep" returns only sleep-tagged items)
- ✓ `sleep` action without "sleep" tag item costs +10 additional fatigue
- ✓ `study` action without "study" tag item reduces skill gain by exactly -1 point
- ✓ `work_from_home` action requires item with "work" tag, fails if not present
- ✓ Item degradation follows exact sequence: pristine → used → worn → broken
- ✓ Each use of an item triggers degradation check
- ✓ Maintenance skill level ≥ 50 reduces degradation probability by 50%
- ✓ Broken items do not count as usable for action requirements
- ✓ View shows which items enable/enhance specific actions at current location
- ✓ Existing save files with pristine items load correctly and degrade normally

---

### 1.3 Essential Daily Actions (Priority: HIGH) ⏱️ 4-6 hours ✅ COMPLETED

**Why Third:** Fills critical gameplay gaps, utilizes underused skills.

**New Actions to Add:**

#### 1. shower (location: bath_001)
- Hygiene: +40
- Mood: +5
- Warmth: -10 (if no heat)
- Water required
- Skill gain: None (basic need)

#### 2. cook_basic_meal (requires kettle or stove)
- Hunger: -35 (better than charity rice)
- Mood: +3
- Cost: 300 pence (ingredients)
- Skill gain: nutrition +1.5
- Creativity trait bonus: +10% hunger reduction

#### 3. clean_room
- Hygiene: +5
- Mood: +8
- Stress: -3
- Skill gain: maintenance +2.0
- Affects item conditions (worn→used if maintenance skill high enough)

#### 4. exercise (can be done anywhere)
- Fatigue: +20
- Hunger: +5
- Mood: +10
- Energy: +5 (long-term)
- Skill gain: reflexivity +2.5
- Fitness trait bonus: -20% fatigue cost

**Implementation Strategy:**
- Add each action in `apply_action()` with similar pattern to existing actions
- Use `state.world.location` to gate location-specific actions
- Check `state.utilities.water` for shower
- Query items for cook action
- If 1.2 is not yet implemented, allow `cook_basic_meal` to fall back to a no-item-required version (temporary behavior) so Phase 1.3 can land first without blocking on item gating.

**Files to modify:**
- `src/roomlife/engine.py`: Add 4 new action handlers
- `src/roomlife/view.py`: Filter actions by location/context
- `src/roomlife/constants.py`: Add action costs/benefits

**Backward Compatibility:** ✅ Full - just adds new actions.

**Acceptance Criteria:**

**shower action:**
- ✓ Increases hygiene by exactly +40
- ✓ Increases mood by exactly +5
- ✓ Decreases warmth by exactly -10 (only when heat is unavailable)
- ✓ Only available in location "bath_001"
- ✓ Fails if `state.utilities.water` is False with appropriate error message
- ✓ No skill gains (basic need action)

**cook_basic_meal action:**
- ✓ Decreases hunger by exactly -35
- ✓ Increases mood by exactly +3
- ✓ Costs exactly 300 pence (fails if insufficient funds)
- ✓ Grants exactly +1.5 nutrition skill
- ✓ Requires item with "kettle" OR "stove" tag at current location
- ✓ Creativity trait (75+) provides additional 10% hunger reduction (-3.5 total = -38.5)

**clean_room action:**
- ✓ Increases hygiene by exactly +5
- ✓ Increases mood by exactly +8
- ✓ Decreases stress by exactly -3
- ✓ Grants exactly +2.0 maintenance skill
- ✓ Can be performed in any location
- ✓ Maintenance skill ≥ 60 can restore one worn item to used condition
- ✓ No effect on pristine or broken items

**exercise action:**
- ✓ Increases fatigue by exactly +20
- ✓ Increases hunger by exactly +5
- ✓ Increases mood by exactly +10
- ✓ Increases energy by exactly +5
- ✓ Grants exactly +2.5 reflexivity skill
- ✓ Fitness trait (75+) reduces fatigue cost by 20% (+16 instead of +20)
- ✓ Can be performed in any location

**General:**
- ✓ All actions appear in view only when requirements met (location, items, utilities)
- ✓ All actions advance time by 1 time slice
- ✓ All stat changes apply immediately in same turn

**Implementation Notes:**
- All four essential actions implemented in `src/roomlife/engine.py`
- `shower`: Requires water utility and bath_001 location, applies hygiene +40, mood +5, warmth -10 (if no heat)
- `cook_basic_meal`: Requires 300 pence and kettle/stove item at current location, reduces hunger by 35 (38.5 with creativity trait ≥75), mood +3, nutrition skill +1.5
- `clean_room`: Can be performed anywhere, hygiene +5, mood +8, stress -3, maintenance skill +2.0, discipline habit +10
- `exercise`: Can be performed anywhere, fatigue +20 (16 with fitness ≥75), hunger +5, mood +10, stress -5, reflexivity skill +2.5
- All actions include proper error handling with logged failure events

---

## Phase 2: Core Gameplay Systems (Depth & Consequences)

**Goal:** Add systems that create meaningful choices and consequences.

### 2.1 Health & Consequences System (Priority: HIGH) ⏱️ 3-4 hours

**Why:** Makes needs matter, adds stakes to gameplay.

**Implementation Strategy:**
- Add `health: int` field to Needs (0-100)
- Health degrades when extreme needs occur:
  - Hunger > 80: health -2 per turn, fatigue +5
  - Fatigue > 90: health -1 per turn, all actions +50% cost
  - Hygiene < 20: health -1 per turn, mood -5
  - Warmth < 30: health -3 per turn, fatigue +5
  - Stress > 80: health -1 per turn, mood -5
- Health below 50: All skill gains -50%
- Health below 30: New action `visit_doctor` (costs 5000 pence, restores 30 health)
- Health 0: "Game Over" state (can continue but with severe penalties)

**Files to modify:**
- `src/roomlife/models.py`: Add `health` to Needs
- `src/roomlife/engine.py`: Add `_apply_health_consequences()` called from `_apply_environment()`
- `src/roomlife/io.py`: Add health to save/load (default 100 for old saves)

**Backward Compatibility:** ⚠️ Semi-compatible - add `health=100` default in load function.

**Acceptance Criteria:**
- ✓ `health` field added to Needs dataclass with range 0-100
- ✓ Health initializes to 100 for new games
- ✓ Old save files load with health defaulting to 100
- ✓ Hunger > 80 causes exactly -2 health per turn
- ✓ Hunger > 80 causes exactly +5 fatigue per turn (in addition to health loss)
- ✓ Fatigue > 90 causes exactly -1 health per turn
- ✓ Fatigue > 90 increases all action costs by exactly 50%
- ✓ Hygiene < 20 causes exactly -1 health per turn
- ✓ Hygiene < 20 causes exactly -5 mood per turn
- ✓ Warmth < 30 causes exactly -3 health per turn
- ✓ Warmth < 30 causes exactly +5 fatigue per turn
- ✓ Stress > 80 causes exactly -1 health per turn
- ✓ Stress > 80 causes exactly -5 mood per turn
- ✓ Health < 50 reduces all skill gains by exactly 50%
- ✓ Health < 30 unlocks `visit_doctor` action
- ✓ `visit_doctor` costs exactly 5000 pence (fails if insufficient)
- ✓ `visit_doctor` restores exactly +30 health
- ✓ Health cannot exceed 100 or drop below 0
- ✓ Health = 0 displays "Critical Health" warning but allows continued play
- ✓ Health = 0 applies severe penalties to all actions (e.g., doubled costs)
- ✓ All health consequences apply in `_apply_environment()` call

---

### 2.2 Shopping & Economy Expansion (Priority: MEDIUM) ⏱️ 3-4 hours

**Why:** Creates money sink, enables progression, uses persuasion skill.

**Implementation Strategy:**
- Add `shop_catalog` to constants.py with consumables and physical items
- Items include:
  - Consumables: coffee (150p), proper_meal (800p), vitamins (500p)
  - Books: skill-specific XP boosts (2000p each)
  - Physical items: heater_portable (8000p), upgraded_desk (15000p)
- Add `buy <item_id>` action
- Persuasion skill: 10% discount per 10 skill points
- Frugality trait: Additional 5% discount at 75+

**Files to modify:**
- `src/roomlife/constants.py`: Add SHOP_ITEMS catalog
- `src/roomlife/engine.py`: Add `buy` action handler
- `src/roomlife/models.py`: Possibly add `consumables` list to Player

**Backward Compatibility:** ✅ Full - adds new action and optional inventory.

**Acceptance Criteria:**
- ✓ `shop_catalog` defined in constants.py with all specified items
- ✓ Coffee costs exactly 150 pence, provides defined benefits
- ✓ Proper meal costs exactly 800 pence, provides defined benefits
- ✓ Vitamins cost exactly 500 pence, provide defined benefits
- ✓ Skill-specific books cost exactly 2000 pence each
- ✓ Portable heater costs exactly 8000 pence
- ✓ Upgraded desk costs exactly 15000 pence
- ✓ `buy <item_id>` action successfully purchases item and deducts cost
- ✓ `buy` action fails with error if insufficient funds
- ✓ `buy` action fails with error if invalid item_id
- ✓ Persuasion skill provides exactly 1% discount per skill point (e.g., persuasion 50 = 50% off)
- ✓ Persuasion discount caps at 10 skill points = 10% maximum discount
- ✓ Frugality trait (75+) provides additional 5% discount stacked with persuasion
- ✓ Purchased consumables are tracked and usable
- ✓ Purchased physical items added to appropriate location with correct tags
- ✓ Book items grant XP boost when used with corresponding skill action
- ✓ View displays shop catalog with prices (including applied discounts)

---

### 2.3 Social System Foundation (Priority: MEDIUM) ⏱️ 6-8 hours

**Why:** Enables 3 social skills (presence, articulation, persuasion), adds variety.

**Implementation Strategy:**
- Add NPC data structure:
  ```python
  @dataclass
  class NPC:
      npc_id: str
      name: str
      location: str  # which space they're in
      schedule: Dict[str, str]  # time_slice -> location
      relationship_threshold: int = 20
  ```
- Add 3-5 NPCs with schedules:
  - neighbor (friendly, lives next door)
  - landlord (businesslike, office hours)
  - coworker (professional, workplace)
  - friend (casual, various locations)
  - shopkeeper (transactional, shop)
- Add basic social actions:
  - `chat <npc_id>`: Presence +1.5, relationship +3, mood +5
  - `deep_talk <npc_id>`: Articulation +2.0, relationship +8, stress -5 (requires relationship > 30)
  - `ask_favor <npc_id>`: Persuasion +1.0, can unlock bonuses

**Files to modify:**
- `src/roomlife/models.py`: Add NPC dataclass, add npcs list to State
- `src/roomlife/engine.py`: Add NPC schedule system, add social actions
- `data/npcs.yaml`: Create NPC definitions (new file)
- `src/roomlife/view.py`: Show NPCs at current location

**Backward Compatibility:** ✅ Full - NPCs are new addition, relationships already exist.

**Acceptance Criteria:**
- ✓ NPC dataclass defined with all fields: npc_id, name, location, schedule, relationship_threshold
- ✓ At least 3 NPCs defined in data/npcs.yaml (neighbor, landlord, coworker minimum)
- ✓ Each NPC has valid schedule mapping time slices to locations
- ✓ NPCs appear in view only when at same location as player
- ✓ NPC location updates according to schedule each time slice
- ✓ `chat <npc_id>` action grants exactly +1.5 presence skill
- ✓ `chat <npc_id>` increases relationship by exactly +3
- ✓ `chat <npc_id>` increases mood by exactly +5
- ✓ `chat` action fails if NPC not at current location
- ✓ `deep_talk <npc_id>` grants exactly +2.0 articulation skill
- ✓ `deep_talk <npc_id>` increases relationship by exactly +8
- ✓ `deep_talk <npc_id>` decreases stress by exactly -5
- ✓ `deep_talk` requires relationship > 30 (fails with message if not met)
- ✓ `ask_favor <npc_id>` grants exactly +1.0 persuasion skill
- ✓ `ask_favor` can unlock bonuses (implementation-defined)
- ✓ All social actions fail gracefully if invalid npc_id
- ✓ Relationships persist across save/load cycles
- ✓ Old save files load with empty NPC list, NPCs initialize on first encounter
- ✓ View displays NPC names and relationship levels at current location

---

### 2.4 Random Events System (Priority: MEDIUM) ⏱️ 4-5 hours

**Why:** Adds unpredictability, makes world feel alive.

**Implementation Strategy:**
- Create event system using existing RNG
- Event types:
  - Financial: package_delivery (-500p), found_money (+200p)
  - Social: helpful_neighbor (+relationship), argument (-relationship)
  - Health: food_poisoning (-health), good_sleep (+energy)
  - Item: item_breaks (condition -20), surprise_gift (new item)
- Events can be:
  - Time-gated (only certain time slices)
  - Location-gated (only in certain spaces)
  - Requirement-gated (needs NPC, skill level, etc.)
- Roll for events in `_apply_environment()` with 3-8% chance per turn

**Files to modify:**
- `src/roomlife/constants.py`: Add RANDOM_EVENTS list
- `src/roomlife/engine.py`: Add `_process_random_events()` in `_apply_environment()`

**Backward Compatibility:** ✅ Full - just adds new event rolls.

**Acceptance Criteria:**
- ✓ RANDOM_EVENTS list defined in constants.py with all event types
- ✓ Events roll with probability between 3-8% per turn
- ✓ Only one event can trigger per turn (no event stacking)
- ✓ `package_delivery` event costs exactly -500 pence
- ✓ `found_money` event grants exactly +200 pence
- ✓ `helpful_neighbor` event increases specific NPC relationship (amount defined)
- ✓ `argument` event decreases specific NPC relationship (amount defined)
- ✓ `food_poisoning` event decreases health by defined amount
- ✓ `good_sleep` event increases energy by defined amount
- ✓ `item_breaks` event reduces item condition by exactly -20 (or one degradation level)
- ✓ `surprise_gift` event adds new item to player location
- ✓ Time-gated events only trigger during specified time slices
- ✓ Location-gated events only trigger in specified locations
- ✓ Requirement-gated events check prerequisites (NPC presence, skill levels, etc.)
- ✓ Events with unmet requirements are skipped from roll pool
- ✓ Event messages logged to event log with clear descriptions
- ✓ Events use existing deterministic RNG for reproducibility
- ✓ `_process_random_events()` called within `_apply_environment()`
- ✓ No events trigger on first turn of new game

---

## Phase 3: Content Expansion (Breadth & Variety)

**Goal:** Add content that uses all systems and provides long-term engagement.

### 3.1 Advanced Actions & Skill Utilization (Priority: MEDIUM) ⏱️ 4-6 hours

**Why:** Ensure all 12 skills have multiple uses, add strategic depth.

**New Actions:**

#### 1. meditate
- Stress: -15, Mood: +5, Fatigue: -5
- Skill gain: introspection +3.0
- Stoicism trait bonus: +50% stress reduction

#### 2. optimize_space (requires maintenance skill > 20)
- One-time action per space
- Marks space as "optimized"
- All actions in that space: -10% fatigue cost
- Skill gain: ergonomics +5.0

#### 3. budget_planning
- Skill gain: analysis +2.0
- Unlocks "financial_report" view with spending trends
- At analysis > 50: predicts upcoming expenses

#### 4. creative_hobby
- Mood: +12, Stress: -8
- Uses creativity trait
- Creativity trait bonus: double mood benefit

#### 5. study_advanced (requires focus > 30)
- Better version of study
- Skill gain: focus +4.5 (vs 3.0), analysis +1.5
- Fatigue: +15

**Files to modify:**
- `src/roomlife/engine.py`: Add 5 action handlers
- `src/roomlife/models.py`: Add `space_optimizations` dict to State

**Backward Compatibility:** ✅ Full - new actions, optional state additions.

**Acceptance Criteria:**

**meditate action:**
- ✓ Decreases stress by exactly -15
- ✓ Increases mood by exactly +5
- ✓ Decreases fatigue by exactly -5
- ✓ Grants exactly +3.0 introspection skill
- ✓ Stoicism trait (75+) increases stress reduction by 50% (-22.5 total)
- ✓ Can be performed in any location

**optimize_space action:**
- ✓ Requires maintenance skill > 20 (fails with message if not met)
- ✓ Can only be performed once per space (subsequent attempts fail)
- ✓ Marks space as "optimized" in `state.space_optimizations` dict
- ✓ All future actions in optimized space have -10% fatigue cost
- ✓ Grants exactly +5.0 ergonomics skill
- ✓ Optimization persists across save/load cycles

**budget_planning action:**
- ✓ Grants exactly +2.0 analysis skill
- ✓ Unlocks "financial_report" in view showing spending trends
- ✓ Analysis skill ≥ 50 enables expense prediction feature
- ✓ Predictions show upcoming bill dates and amounts
- ✓ Can be performed in any location

**creative_hobby action:**
- ✓ Increases mood by exactly +12
- ✓ Decreases stress by exactly -8
- ✓ Creativity trait (75+) doubles mood benefit (+24 instead of +12)
- ✓ Can be performed in any location
- ✓ No skill gains (pure recreational activity)

**study_advanced action:**
- ✓ Requires focus skill > 30 (fails with message if not met)
- ✓ Grants exactly +4.5 focus skill (compared to +3.0 for basic study)
- ✓ Grants exactly +1.5 analysis skill
- ✓ Increases fatigue by exactly +15
- ✓ All other study requirements apply (items, location bonuses, etc.)

**General:**
- ✓ All actions advance time by 1 time slice
- ✓ `space_optimizations` dict added to State model (defaults to empty)
- ✓ Old save files load with empty space_optimizations dict

---

### 3.2 Goals & Progression System (Priority: LOW-MEDIUM) ⏱️ 5-6 hours

**Why:** Gives players direction, sense of achievement.

**Implementation Strategy:**
- Add Goal system:
  ```python
  @dataclass
  class Goal:
      goal_id: str
      description: str
      conditions: Dict  # e.g., {"skill.focus": 50}
      reward: Dict  # e.g., {"money_pence": 5000}
      completed: bool = False
  ```
- Predefined goal tree:
  - **Early:** "Survive 7 days", "Pay utilities 3 times"
  - **Mid:** "Reach focus 50", "Save 20000 pence"
  - **Late:** "Master a skill (100)", "Befriend all NPCs"
- Check goals after each action in `apply_action()`
- Completed goals unlock new goals

**Files to modify:**
- `src/roomlife/models.py`: Add Goal dataclass, goals list to State
- `src/roomlife/engine.py`: Add `_check_goals()` function
- `src/roomlife/constants.py`: Define GOAL_TREE
- `src/roomlife/view.py`: Show active goals

**Backward Compatibility:** ✅ Full - goals optional, default to empty list.

**Acceptance Criteria:**
- ✓ Goal dataclass defined with fields: goal_id, description, conditions, reward, completed
- ✓ GOAL_TREE defined in constants.py with early/mid/late progression
- ✓ "Survive 7 days" goal completes when day_count ≥ 7
- ✓ "Pay utilities 3 times" goal tracks utility payments, completes at 3
- ✓ "Reach focus 50" goal completes when focus skill ≥ 50
- ✓ "Save 20000 pence" goal completes when money_pence ≥ 20000
- ✓ "Master a skill (100)" goal completes when any skill reaches 100
- ✓ "Befriend all NPCs" goal completes when all NPCs have relationship > threshold
- ✓ Goal conditions support multiple criteria types (skill, money, day_count, etc.)
- ✓ Rewards apply immediately upon goal completion
- ✓ Completed goals persist across save/load cycles
- ✓ `_check_goals()` runs after each action in `apply_action()`
- ✓ Goal completion logged to event log
- ✓ Completing goals unlocks new goals in tree (dependency system)
- ✓ Goals cannot complete twice (completed flag prevents re-completion)
- ✓ View displays active goals with progress indicators
- ✓ View shows completed goals separately
- ✓ Old save files load with empty goals list, goals initialize on next turn

---

### 3.3 Expanded World & Locations (Priority: LOW) ⏱️ 4-5 hours

**Why:** More exploration, location-specific activities.

**New Spaces:**

#### 1. local_shop
- Connected to hall_001
- Shopping available here
- NPC: shopkeeper
- Actions: buy, chat

#### 2. park
- Connected to building exterior (new intermediate space)
- Better exercise benefits (+50%)
- Weather affects experience (future enhancement)
- Actions: exercise, meditate, socialize

#### 3. library
- Connected to building exterior
- Enhanced study benefits (+25% skill gain)
- Free books (consumable items)
- Actions: study, read, deep_talk

#### 4. workplace
- Connected to building exterior
- Work action more profitable here (+25%)
- Coworker NPCs present during work hours

**Implementation Strategy:**
- Add spaces to `data/spaces.yaml`
- Modify action handlers to check location and apply bonuses
- Add location-specific random events

**Files to modify:**
- `data/spaces.yaml`: Add new spaces
- `src/roomlife/engine.py`: Add location bonuses to existing actions
- `src/roomlife/constants.py`: Add location-specific event pools

**Backward Compatibility:** ⚠️ Semi-compatible - need migration to add new spaces to existing saves.

**Acceptance Criteria:**

**local_shop location:**
- ✓ Added to data/spaces.yaml with proper space_id
- ✓ Connected to hall_001 (bidirectional connection)
- ✓ Shopping actions available only in this location
- ✓ Shopkeeper NPC present according to schedule
- ✓ `buy` and `chat` actions work correctly at this location

**park location:**
- ✓ Added to data/spaces.yaml with proper space_id
- ✓ Connected to building exterior (new intermediate space created)
- ✓ Exercise action provides +50% benefits when performed here
- ✓ Park bonuses: mood +15 (vs +10), same fatigue cost
- ✓ Weather system integration points defined (future enhancement)
- ✓ `exercise`, `meditate`, and social actions available

**library location:**
- ✓ Added to data/spaces.yaml with proper space_id
- ✓ Connected to building exterior
- ✓ Study actions provide +25% skill gain when performed here
- ✓ Free books available as consumable items (one-time pickup)
- ✓ `study`, `read`, and `deep_talk` actions available
- ✓ Study bonus applies to both basic and advanced study

**workplace location:**
- ✓ Added to data/spaces.yaml with proper space_id
- ✓ Connected to building exterior
- ✓ Work action provides +25% income when performed here
- ✓ Work bonus: 125% of base pay
- ✓ Coworker NPCs present during work time slices only
- ✓ Work time slices defined in NPC schedules

**General:**
- ✓ All new spaces have proper tags, descriptions, and connections
- ✓ Building exterior intermediate space created and connected
- ✓ Location-specific bonuses apply automatically based on current location
- ✓ Location-specific events added to RANDOM_EVENTS for new locations
- ✓ Old save files load successfully with new locations added to world
- ✓ Migration script adds new spaces to existing world state
- ✓ No breaking changes to existing location IDs or connections

---

## Phase 4: Polish & Refinement

**Goal:** Improve testing, balance, and player experience.

### 4.1 Comprehensive Testing (Priority: HIGH) ⏱️ 6-8 hours

**Why:** Ensure quality, prevent regressions.

**Test Coverage to Add:**
1. **Action tests:** Each action has expected outcome test
2. **Skill integration tests:** Verify skill gains/rust
3. **Trait effect tests:** Verify traits modify actions correctly
4. **State consistency tests:** Invariants (health 0-100, etc.)
5. **Save/load tests:** Backward compatibility validation
6. **Balance tests:** Money flow, skill progression rates

**Files to create:**
- `tests/test_actions.py`: Test all actions
- `tests/test_skills.py`: Test skill system
- `tests/test_traits.py`: Test trait effects
- `tests/test_balance.py`: Test game balance
- `tests/test_compatibility.py`: Test save migrations

**Acceptance Criteria:**

**Action tests (test_actions.py):**
- ✓ Test suite covers 100% of implemented actions
- ✓ Each action test validates exact stat changes (e.g., sleep restores X fatigue)
- ✓ Each action test validates costs (money, fatigue, etc.)
- ✓ Each action test validates prerequisites (location, items, utilities)
- ✓ Each action test validates failure conditions return appropriate errors
- ✓ Movement action tests validate connection checking
- ✓ Item-dependent actions tested with/without required items

**Skill tests (test_skills.py):**
- ✓ Skill gain calculations tested for all actions
- ✓ Skill rust calculations tested over time periods
- ✓ Skill caps (0-100) enforced in all scenarios
- ✓ Health penalties (<50 health) reduce skill gains by exactly 50%
- ✓ Trait bonuses to skill gains calculated correctly
- ✓ Location bonuses to skill gains calculated correctly (e.g., library +25%)

**Trait tests (test_traits.py):**
- ✓ All trait thresholds tested (verify effects at 74, 75, 76)
- ✓ Creativity trait doubles mood benefit in creative_hobby
- ✓ Fitness trait reduces exercise fatigue by 20%
- ✓ Frugality trait provides 5% shopping discount
- ✓ Stoicism trait increases stress reduction by 50%
- ✓ Trait effects stack correctly with other bonuses

**Balance tests (test_balance.py):**
- ✓ Simulated 30-day playthrough completes without forced game over
- ✓ Money flow allows saving ~500p/day with reasonable play
- ✓ Each need requires attention every 2-3 days maximum
- ✓ Player can actively maintain 3-4 skills without excessive rust
- ✓ Health consequences avoidable with moderate needs management
- ✓ Item durability lasts reasonable duration with maintenance
- ✓ No actions create infinite money/stat loops

**Compatibility tests (test_compatibility.py):**
- ✓ Save files from version N-1 load successfully
- ✓ Missing health field defaults to 100
- ✓ Missing goals list defaults to empty []
- ✓ Missing space_optimizations defaults to empty {}
- ✓ Missing NPCs list defaults to empty []
- ✓ All new spaces added to existing world states
- ✓ Schema version increments correctly on breaking changes

**General:**
- ✓ All tests use deterministic RNG for reproducibility
- ✓ Test coverage ≥ 80% for engine.py
- ✓ All tests pass in CI/CD pipeline
- ✓ No flaky tests (100% pass rate on 10 consecutive runs)

---

### 4.2 Balance Pass (Priority: MEDIUM) ⏱️ 4-6 hours

**Why:** Ensure gameplay is engaging, not too easy or hard.

**Balance Parameters to Tune:**
- **Money:** Work income vs. expenses ratio (target: can save ~500p/day)
- **Needs:** Degradation rates (target: address each need every 2-3 days)
- **Skills:** Rust vs. gain rates (target: maintain 3-4 skills actively)
- **Health:** Consequence severity (target: avoidable with moderate care)
- **Items:** Durability and maintenance frequency

**Approach:**
- Create simulation script that plays 100 random games for 30 days
- Track metrics: survival rate, money at day 30, skill levels
- Adjust constants based on metrics

**Files to create:**
- `scripts/balance_sim.py`: Simulation runner
- Update `src/roomlife/constants.py`: Adjust tuning constants

**Acceptance Criteria:**
- ✓ Balance simulation script runs 100 games for 30 in-game days each
- ✓ Simulation uses varied random strategies (random, conservative, aggressive, balanced)
- ✓ Survival rate ≥ 90% for balanced strategy over 30 days
- ✓ Average money at day 30 between 10,000-20,000 pence (balanced strategy)
- ✓ Work income vs. expenses ratio allows saving 400-600 pence/day
- ✓ Needs degradation rates require attention every 2-3 days (not every turn)
- ✓ Hunger degradation: reaches 80 after ~48-72 hours of neglect
- ✓ Fatigue degradation: reaches 90 after ~2-3 days of activity
- ✓ Hygiene degradation: reaches critical (<20) after ~3-4 days
- ✓ Stress accumulation: manageable with 1-2 stress-relief actions per week
- ✓ Skill rust rate allows maintaining 3-4 skills with regular use
- ✓ Unused skills rust at rate: -1 to -2 points per day
- ✓ Actively used skills gain faster than rust: +3 to +5 per action
- ✓ Health consequences create challenge but not instant failure
- ✓ Health < 50 scenario: recoverable within 3-5 days of care
- ✓ Item durability: items last 7-14 uses before requiring maintenance
- ✓ Maintenance skill reduces degradation: high skill = 50% longer item life
- ✓ No single action dominates optimal play (variety encouraged)
- ✓ All 12 skills have viable progression paths to 100
- ✓ Simulation output includes graphs/tables of key metrics
- ✓ Constants adjusted based on simulation results documented in comments

---

### 4.3 Telemetry & Metrics System (Priority: HIGH) ⏱️ 3-4 hours

**Why:** Provides data-driven validation of balance assumptions, enables tuning based on actual gameplay patterns, and tracks player behavior to identify issues early.

**Implementation Strategy:**
- Create metrics collection system that tracks key gameplay indicators
- Define target ranges for critical metrics based on design goals
- Implement persistent logging to file for analysis
- Add metrics reporting to simulation runs
- Create dashboard/report generation for metrics visualization

**Metrics to Track:**

#### 1. Survival & Health Metrics
- **survival_rate**: % of games reaching day 30 without game over
  - **Target range**: 85-95% (balanced strategy)
  - **Storage**: `metrics_log.json`, field: `survival_30day`
- **avg_health**: Average health over time
  - **Target range**: 60-80 (healthy gameplay)
  - **Storage**: `metrics_log.json`, field: `health_timeseries`
- **critical_health_frequency**: # of times health drops below 30
  - **Target range**: 0-2 times per 30 days (rare but possible)
  - **Storage**: `metrics_log.json`, field: `critical_health_events`

#### 2. Economic Metrics
- **avg_balance_day30**: Money at day 30
  - **Target range**: 10,000-20,000 pence (steady savings)
  - **Storage**: `metrics_log.json`, field: `final_balance`
- **daily_savings_rate**: Average pence saved per day
  - **Target range**: 400-600 pence/day
  - **Storage**: `metrics_log.json`, field: `savings_rate`
- **bankruptcy_rate**: % of games with negative balance
  - **Target range**: <5%
  - **Storage**: `metrics_log.json`, field: `bankruptcy_count`
- **expense_breakdown**: Proportion of spending by category
  - **Target range**: Bills 60%, Food 20%, Other 20%
  - **Storage**: `metrics_log.json`, field: `expense_categories`

#### 3. Needs Management Metrics
- **need_critical_frequency**: How often each need reaches critical levels
  - **Target range**: Each need critical 0-1 times per week
  - **Storage**: `metrics_log.json`, field: `critical_needs_by_type`
- **avg_need_levels**: Average value of each need over time
  - **Target range**: Hunger 40-60, Fatigue 30-50, Hygiene 50-70, Stress 30-50
  - **Storage**: `metrics_log.json`, field: `needs_timeseries`
- **need_attention_frequency**: Days between addressing each need
  - **Target range**: 2-3 days per need
  - **Storage**: `metrics_log.json`, field: `need_service_intervals`

#### 4. Skill Progression Metrics
- **skills_maintained**: # of skills kept above 30
  - **Target range**: 3-4 skills (validates rust/gain balance)
  - **Storage**: `metrics_log.json`, field: `active_skills_count`
- **skill_progression_rate**: Average skill gain per day for active skills
  - **Target range**: +2 to +5 points/day
  - **Storage**: `metrics_log.json`, field: `skill_velocity`
- **skill_diversity**: % of skills used at least once per week
  - **Target range**: 70-80% (9-10 of 12 skills)
  - **Storage**: `metrics_log.json`, field: `skill_usage_diversity`

#### 5. Action & Content Engagement
- **action_diversity**: # of unique actions used per week
  - **Target range**: 12-15 actions (good variety)
  - **Storage**: `metrics_log.json`, field: `weekly_action_variety`
- **dominant_action_ratio**: % of actions that are most-used action
  - **Target range**: <30% (no single dominant strategy)
  - **Storage**: `metrics_log.json`, field: `action_concentration`
- **location_utilization**: % of locations visited per week
  - **Target range**: 60-80% of available locations
  - **Storage**: `metrics_log.json`, field: `location_visit_rate`

#### 6. Social & Events Metrics
- **relationship_progression**: Average relationship gain per 10 days
  - **Target range**: +15 to +30 per NPC
  - **Storage**: `metrics_log.json`, field: `relationship_velocity`
- **event_trigger_rate**: % of turns with random events
  - **Target range**: 3-8% (as designed)
  - **Storage**: `metrics_log.json`, field: `event_frequency`
- **positive_negative_event_ratio**: Ratio of beneficial to harmful events
  - **Target range**: 1.0-1.5 (slightly positive bias)
  - **Storage**: `metrics_log.json`, field: `event_sentiment_ratio`

#### 7. Item System Metrics
- **item_durability_lifespan**: Average uses before item breaks
  - **Target range**: 7-14 uses
  - **Storage**: `metrics_log.json`, field: `item_lifetime`
- **maintenance_frequency**: # of maintenance actions per week
  - **Target range**: 2-3 (regular but not excessive)
  - **Storage**: `metrics_log.json`, field: `maintenance_cadence`

**Files to create:**
- `src/roomlife/telemetry.py`: Metrics collection and reporting
- `scripts/analyze_metrics.py`: Metrics visualization and analysis
- `metrics_log.json`: Persistent metrics storage (gitignored)

**Files to modify:**
- `src/roomlife/engine.py`: Add `_collect_metrics()` called each turn
- `scripts/balance_sim.py`: Integrate telemetry system

**Implementation Details:**
- Metrics collected every turn and written to `metrics_log.json` as append-only log
- JSON format: `{"timestamp": "...", "day": 5, "metric_name": "...", "value": ..., "context": {...}}`
- Simulation runs aggregate metrics across all games
- `analyze_metrics.py` generates summary reports and charts (matplotlib)
- Telemetry can be disabled via environment variable `ROOMLIFE_DISABLE_TELEMETRY=1`

**Backward Compatibility:** ✅ Full - telemetry is additive and optional.

**Acceptance Criteria:**
- ✓ Telemetry system tracks all 25+ specified metrics
- ✓ Each metric has defined target range documented
- ✓ Metrics logged to `metrics_log.json` in append-only format
- ✓ Log entries include timestamp, day, metric name, value, and context
- ✓ `_collect_metrics()` called every turn in engine.py
- ✓ Telemetry adds <2% performance overhead to engine
- ✓ Simulation runs generate aggregate metrics reports
- ✓ `analyze_metrics.py` produces summary statistics for all tracked metrics
- ✓ Metrics visualization includes time-series graphs for key indicators
- ✓ Target ranges highlighted in reports (green=in range, yellow=borderline, red=out of range)
- ✓ Telemetry can be disabled without affecting gameplay
- ✓ All target ranges validated through Phase 4.2 balance simulations
- ✓ Out-of-range metrics trigger actionable recommendations (e.g., "Increase work income by 10%")
- ✓ Metrics storage does not grow unbounded (rotation after 100k entries)
- ✓ Documentation includes metrics dictionary explaining each metric's purpose

---

### 4.4 UI/UX Improvements (Priority: LOW) ⏱️ 5-6 hours

**Why:** Better player experience, easier to understand.

**Improvements:**
1. **Action filtering:** Only show available actions (location-aware, item-aware)
2. **Action details:** Show costs/benefits before taking action
3. **Smart suggestions:** Highlight urgent needs or opportunities
4. **Better event formatting:** Rich formatting for event log
5. **Status warnings:** Color-code critical needs (red < 20, yellow < 40)
6. **Progress indicators:** Show skill progress bars

**Files to modify:**
- `src/roomlife/view.py`: Enhanced view model
- `src/roomlife/cli.py`: Better rendering with Rich library

**Acceptance Criteria:**

**Action filtering:**
- ✓ View only shows actions available at current location
- ✓ Item-dependent actions shown only when required items present
- ✓ Utility-dependent actions shown only when utilities available
- ✓ Skill-gated actions shown only when skill requirements met
- ✓ Unavailable actions not displayed in action list
- ✓ Action list dynamically updates as context changes

**Action details:**
- ✓ Each action displays costs before execution (e.g., "300 pence, +15 fatigue")
- ✓ Each action displays benefits before execution (e.g., "-35 hunger, +3 mood")
- ✓ Skill gains shown in action preview
- ✓ Location bonuses shown in action preview (e.g., "library: +25% skill gain")
- ✓ Trait bonuses shown in action preview if applicable
- ✓ Prerequisites clearly stated for locked actions

**Smart suggestions:**
- ✓ System highlights needs that are critical (< 20 or > 80)
- ✓ System suggests actions to address critical needs
- ✓ System highlights low health (< 50) with suggested recovery actions
- ✓ System suggests goals that are near completion
- ✓ Suggestions update dynamically based on current state

**Event formatting:**
- ✓ Event log uses Rich formatting (colors, bold, italics)
- ✓ Positive events displayed in green
- ✓ Negative events displayed in red
- ✓ Neutral events displayed in default color
- ✓ Important events (goal completion, health warnings) highlighted

**Status warnings:**
- ✓ Needs < 20 displayed in red
- ✓ Needs 20-40 displayed in yellow
- ✓ Needs > 80 displayed in red (for hunger, stress, fatigue)
- ✓ Health < 30 displayed with red warning
- ✓ Health 30-50 displayed with yellow warning
- ✓ Money < 2000 pence displayed with yellow warning

**Progress indicators:**
- ✓ Skills show progress bars (e.g., "Focus: [████░░░░░░] 45/100")
- ✓ Goals show completion percentage
- ✓ Item condition shows visual indicator (pristine/used/worn/broken)
- ✓ Relationship levels show progress bars
- ✓ Progress bars use Rich library components

**General:**
- ✓ All UI improvements work in terminal environment
- ✓ UI remains readable in both light and dark terminal themes
- ✓ No performance degradation from UI enhancements
- ✓ UI gracefully handles very long action lists (pagination if needed)

---

## Implementation Dependencies

```
Phase 1: MVP (can be done in parallel)
├── 1.1 Movement (no dependencies)
├── 1.2 Item Interactions (no dependencies; optional prerequisite for item-gated 1.3 actions)
└── 1.3 Essential Actions (depends on 1.1 for location checks; can ship before 1.2 if item-gated actions temporarily fall back)

Phase 2: Core Systems
├── 2.1 Health System (depends on Phase 1 complete)
├── 2.2 Shopping (no dependencies, but better with 1.1)
├── 2.3 Social System (depends on 1.1 for location-based interactions)
└── 2.4 Random Events (no dependencies)

Phase 3: Content
├── 3.1 Advanced Actions (depends on 2.1, 2.3)
├── 3.2 Goals (depends on most Phase 1-2 features)
└── 3.3 Expanded World (depends on 1.1, 2.3)

Phase 4: Polish
├── 4.1 Testing (ongoing, but comprehensive pass after Phase 2)
├── 4.2 Balance (after Phase 3)
├── 4.3 Telemetry & Metrics (after Phase 3, during balance tuning)
└── 4.4 UI/UX (ongoing improvements throughout all phases)
```

---

## Recommended Implementation Order (Maximum Impact)

1. **Movement System (1.1)** - 2-3 hours
   - Immediate gameplay variety
   - Unlocks spatial thinking

2. **Essential Actions (1.3)** - 4-6 hours
   - Biggest immediate impact on fun
   - Creates daily routine gameplay loop
   - Can land before 1.2 with temporary fallback behavior for item-gated actions

3. **Item Interactions (1.2)** - 3-4 hours
   - Makes existing items matter
   - Adds strategic location choices
   - Should precede 1.3 if you want strict item gating from day one

4. **Health & Consequences (2.1)** - 3-4 hours
   - Adds stakes to gameplay
   - Creates tension and urgency

5. **Social System (2.3)** - 6-8 hours
   - Major new gameplay dimension
   - Uses 3 unused skills

6. **Shopping & Economy (2.2)** - 3-4 hours
   - Creates money sink and progression
   - Simple to implement

7. **Random Events (2.4)** - 4-5 hours
   - Keeps gameplay fresh
   - Extensible content system

8. **Advanced Actions (3.1)** - 4-6 hours
   - Ensures all skills useful
   - Adds strategic depth

9. **Testing Pass (4.1)** - 6-8 hours
   - Ensure quality
   - Enable confident iteration

10. **Goals System (3.2)** - 5-6 hours
    - Provides direction
    - Increases engagement

**Total Estimated Time for Core Features (1-9):** 35-45 hours

---

## Architectural Trade-offs & Decisions

### Trade-off 1: Action System Architecture
**Current:** String-based actions in big if/elif block
**Alternatives:** Action class hierarchy, registry/plugin system, command pattern

**✅ Recommendation:** Keep current system for now
**Reasoning:** Simple, works well for ~20 actions, easy to understand, can refactor later if needed (beyond 30-40 actions)

---

### Trade-off 2: Item System Complexity
**Option A:** Simple tags + effects (current approach)
**Option B:** Full component system (items have behaviors, states)

**✅ Recommendation:** Start with Option A, expand gradually
**Reasoning:** Tags already exist, avoid premature abstraction, easy to iterate

---

### Trade-off 3: NPC System
**Option A:** Lightweight (relationships + schedules)
**Option B:** Full NPC simulation (needs, actions, AI)

**✅ Recommendation:** Option A for Phase 2, expand in Phase 3+
**Reasoning:** Focus on player experience first, keep scope manageable

---

### Trade-off 4: Save File Migration Strategy
**Option A:** Strict versioning with migration functions
**Option B:** Flexible loading with defaults for missing fields

**✅ Recommendation:** Option B (current approach)
**Reasoning:** Already working well, dataclass defaults handle missing fields, less maintenance

---

### Trade-off 5: Content Management
**Option A:** Hardcoded in constants.py
**Option B:** YAML files in data/
**Option C:** Database/content system

**✅ Recommendation:** Use Option B for data, Option A for tuning
**Reasoning:** Actions/costs/formulas in constants.py, Items/spaces/NPCs in YAML

---

## Risk Mitigation

### Risk 1: Feature Creep
**Mitigation:** Stick to phased plan, complete Phase 1 fully before Phase 2

### Risk 2: Balance Issues
**Mitigation:** Build simulation/testing tools early (Phase 4.1), iterate on constants

### Risk 3: Save Compatibility Breaking
**Mitigation:** Test loading old saves after each change, use schema_version for breaking changes

### Risk 4: Action Space Too Large
**Mitigation:** Context-aware action filtering in view.py, don't show unavailable actions

### Risk 5: Code Complexity Growth
**Mitigation:** Keep engine.py focused on logic, extract helpers, maintain test coverage

---

## Success Metrics

**Note:** Each phase now includes detailed **Acceptance Criteria** sections with measurable, testable specifications for every feature. The high-level success metrics below summarize phase completion goals, while the detailed criteria define exact thresholds and validation methods.

### Phase 1 Success (See sections 1.1-1.3 for detailed acceptance criteria)
- ✅ Player can move between 3+ locations with validated connections
- ✅ 10+ actions available (6 existing + 4 new essential actions)
- ✅ Items affect action availability/effectiveness with measurable impacts
- ✅ Movement costs exactly +2 fatigue per move
- ✅ Item degradation follows pristine→used→worn→broken sequence
- ✅ All new actions have specific, testable stat changes

### Phase 2 Success (See sections 2.1-2.4 for detailed acceptance criteria)
- ✅ Health system creates meaningful consequences with exact thresholds
  - Hunger > 80: -2 health/turn
  - Fatigue > 90: -1 health/turn + 50% action cost increase
  - Health < 50: -50% skill gains
- ✅ 3+ NPCs with relationships and schedules
- ✅ Random events fire with 3-8% probability per turn
- ✅ Economy has money sinks (shopping) with exact pricing
- ✅ Social actions grant specific skill gains (presence, articulation, persuasion)

### Phase 3 Success (See sections 3.1-3.3 for detailed acceptance criteria)
- ✅ All 12 skills actively used with multiple action paths
- ✅ 5+ locations to explore with measurable bonuses
  - Library: +25% skill gains
  - Park: +50% exercise benefits
  - Workplace: +25% work income
- ✅ 6+ goals defined with concrete completion conditions
- ✅ 20+ total actions available across all phases
- ✅ Space optimization system with -10% fatigue reduction

### Phase 4 Success (See sections 4.1-4.4 for detailed acceptance criteria)
- ✅ Test coverage ≥ 80% for engine.py
- ✅ Balance simulation shows ≥ 90% survival rate over 30 days
- ✅ Telemetry system tracks 25+ metrics with defined target ranges
- ✅ All key metrics within target ranges (validated by 4.3 metrics analysis)
- ✅ Money flow allows saving 400-600 pence/day
- ✅ Needs require attention every 2-3 days (validated through simulation)
- ✅ UI shows color-coded warnings (red < 20, yellow 20-40)
- ✅ Action filtering shows only contextually available actions (implemented progressively)

### Overall Success (Validated by detailed acceptance criteria throughout)
- ✅ Game session is engaging for 30+ in-game days (balance sim validates)
- ✅ Player faces interesting choices each turn (no dominant strategy)
- ✅ Systems create emergent gameplay (NPCs + events + locations + skills)
- ✅ Clear progression path from beginning to mastery (goals system)
- ✅ All features have concrete, testable acceptance criteria
- ✅ Backward compatibility maintained or explicitly documented

---

## Critical Files for Implementation

The 5 most critical files for this implementation plan:

1. **`src/roomlife/engine.py`** - Core action processing logic; will receive the most additions (movement, items, social, health, all new actions). Every feature touches this file.

2. **`src/roomlife/constants.py`** - Game balance and content definitions; needs expansion for action costs, shop items, events, and tuning parameters.

3. **`src/roomlife/models.py`** - Data structures; needs additions for NPCs, goals, health, and expanded state.

4. **`src/roomlife/view.py`** - View model generation; must expose new systems to UI (NPCs, goals, available actions, health warnings).

5. **`data/items.yaml`** - Content database; needs expansion for all new items, will drive variety in gameplay.

---

## Next Steps

To begin implementation:

1. Review and approve this plan
2. Set up development branch
3. Start with Phase 1.1 (Movement System)
4. Implement features in recommended order
5. Test after each phase
6. Iterate on balance as needed

Happy coding! 🎮
