# RoomLife Implementation Plan

## Executive Summary

This plan outlines the phased development strategy for RoomLife, prioritizing features by impact and organizing them into 4 main phases:

1. **Phase 1: MVP Improvements** - Movement, essential actions, item interactions (12-16 hours)
2. **Phase 2: Core Gameplay Systems** - Health, social, economy, random events (16-21 hours)
3. **Phase 3: Content Expansion** - Advanced actions, goals, expanded world (13-17 hours)
4. **Phase 4: Polish & Refinement** - Testing, balance, UI/UX improvements (15-20 hours)

**Total estimated effort:** 56-74 hours for complete implementation

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

---

### 1.3 Essential Daily Actions (Priority: HIGH) ⏱️ 4-6 hours

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

**Files to modify:**
- `src/roomlife/engine.py`: Add 4 new action handlers
- `src/roomlife/view.py`: Filter actions by location/context
- `src/roomlife/constants.py`: Add action costs/benefits

**Backward Compatibility:** ✅ Full - just adds new actions.

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

---

### 4.3 UI/UX Improvements (Priority: LOW) ⏱️ 5-6 hours

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

---

## Implementation Dependencies

```
Phase 1: MVP (can be done in parallel)
├── 1.1 Movement (no dependencies)
├── 1.2 Item Interactions (no dependencies)
└── 1.3 Essential Actions (depends on 1.1 for location checks)

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
└── 4.3 UI/UX (ongoing improvements)
```

---

## Recommended Implementation Order (Maximum Impact)

1. **Movement System (1.1)** - 2-3 hours
   - Immediate gameplay variety
   - Unlocks spatial thinking

2. **Essential Actions (1.3)** - 4-6 hours
   - Biggest immediate impact on fun
   - Creates daily routine gameplay loop

3. **Item Interactions (1.2)** - 3-4 hours
   - Makes existing items matter
   - Adds strategic location choices

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

### Phase 1 Success
- ✅ Player can move between 3+ locations
- ✅ 10+ actions available
- ✅ Items affect action availability/effectiveness

### Phase 2 Success
- ✅ Health system creates meaningful consequences
- ✅ 3+ NPCs with relationships
- ✅ Random events fire 1-2 per day
- ✅ Economy has money sinks beyond utilities

### Phase 3 Success
- ✅ All 12 skills actively used in gameplay
- ✅ 5+ locations to explore
- ✅ 10+ goals for progression
- ✅ 20+ total actions available

### Overall Success
- ✅ Game session is engaging for 30+ in-game days
- ✅ Player faces interesting choices each turn
- ✅ Systems create emergent gameplay
- ✅ Clear progression path from beginning to mastery

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
