# YAML ActionCatalog System - Comprehensive Error Review

**Review Date:** 2026-01-12
**System Version:** Schema Version 1
**Total Actions:** 26

---

## Executive Summary

The YAML ActionCatalog system is **well-designed and mostly functional**, with comprehensive validation and error handling. However, **1 critical error** and several design limitations were identified that should be addressed.

**Overall Status:** ⚠️ **Requires Fix** (1 critical error, several design limitations)

---

## Critical Errors (Must Fix)

### 1. Invalid Skill Reference in `study_focused` Action ❌

**Location:** `data/actions.yaml:510, 520, 529, 538`

**Issue:** The `study_focused` action references `"logic"` as a secondary skill, but `"logic"` is not defined in `SKILL_NAMES`.

```yaml
study_focused:
  modifiers:
    primary_skill: ergonomics
    secondary_skills:
      logic: 0.30  # ❌ ERROR: 'logic' is not a valid skill
```

**Available Skills:**
- analysis, articulation, ergonomics, focus, introspection, maintenance
- nutrition, persuasion, presence, reflexivity, resource_management, technical_literacy

**Impact:**
- The `compute_tier()` function will call `_get_skill_value(state, "logic")` which returns 0.0 for unknown skills
- Action will work but the intended secondary skill bonus will never apply
- Silent failure - no error thrown, just missing functionality

**Recommended Fix:**
Replace `logic` with an appropriate skill, likely one of:
- `analysis` (most similar to logic)
- `focus` (concentration aspect)
- `technical_literacy` (academic knowledge)

**Code Reference:** `src/roomlife/action_engine.py:331-332`

---

## Design Limitations (Known Issues)

### 2. Instance-Level Selection Issues for `sell_item` and `discard_item` ⚠️

**Location:** `src/roomlife/catalog.py:245-249, 298-300`

**Issue:** Both `sell_item` and `discard_item` actions:
- Use `item_id` parameter (not `instance_id`)
- List only one action per `item_id` even if multiple instances exist
- Execute on the first instance found at the current location

**Example Scenario:**
```
Player has 2 chairs at location:
- chair_1: condition_value=90 (pristine)
- chair_2: condition_value=30 (broken)

Catalog shows: "Sell Basic Chair (~180p)" (based on chair_1)
Execution sells: chair_1 (first found)
```

**Impact:**
- Players cannot choose which specific instance to sell/discard when duplicates exist
- Sell price shown in catalog may not match actual item sold
- Reduces player control over inventory management

**Documented:** Yes, comments in code acknowledge this limitation

**Recommended Fix:**
- Enhance actions to accept `instance_id` parameter
- Update catalog to list each instance separately with condition info
- Backward compatibility: keep `item_id` mode for legacy support

**Code References:**
- `src/roomlife/catalog.py:233-284` (sell listing)
- `src/roomlife/catalog.py:286-325` (discard listing)
- `src/roomlife/action_engine.py:847-894` (sell execution)
- `src/roomlife/action_engine.py:896-927` (discard execution)

---

### 3. Validation Timing Gaps ⚠️

**Issue:** Several validation checks occur only before action execution, not during:

#### 3.1 Utility Validation Not Re-checked
**Location:** `src/roomlife/action_engine.py` (various special actions)

- Utilities validated in `validate_action_spec()`
- Not re-validated in `execute_action()`
- If utilities cut off between validation and execution, action proceeds anyway

**Example:**
```
Time 0: Player validates "shower" action (water=on) ✓
Time 1: Water utility cuts off
Time 2: Player executes "shower" action (still succeeds despite water=off)
```

**Impact:** Low (requires external state change between validation and execution)

#### 3.2 Money Validation
**Location:** `src/roomlife/action_engine.py` (repair_item, purchase_item)

- Initial validation checks money
- Some actions double-check during execution (good!)
- Edge case: if player gains money between validation and execution, previously invalid action becomes valid

**Current Handling:**
- ✅ `repair_item`: Double-checks money (line 635)
- ✅ `purchase_item`: Double-checks money (line 814)
- ✅ `pay_utilities`: Double-checks money (line 747)

**Status:** ✅ Well-handled for money-consuming actions

---

### 4. Item Durability Consumption Edge Case ⚠️

**Location:** `src/roomlife/action_engine.py:534-550`

**Issue:** In `apply_consumes()`, if the required item is not found:
```python
it = _find_best_item_for_provides(state, item_meta, prov, state.world.location)
if it is None:
    _log(state, "item.durability_missing", provides=prov)
    return  # Action already succeeded, just logs error
```

**Scenario:**
```
1. Player starts "cook_basic_meal" (requires heat_source)
2. Validation passes (kettle exists)
3. Action executes: tier computed, money consumed, outcomes applied
4. apply_consumes() tries to degrade kettle durability
5. Kettle has been moved/removed in concurrent action
6. Logs error but action already completed successfully
```

**Impact:**
- Low probability (requires concurrent modification)
- Resource consumption silently skipped
- Could lead to infinite item durability if exploited

**Recommended Fix:**
- Validate item presence at start of `apply_consumes()`
- Consider making this a hard failure if critical

---

## Informational Issues (Consider Addressing)

### 5. Missing Tier 0 Outcomes ℹ️

**Issue:** 17 actions have primary skills but no tier 0 (fail/partial) outcome defined:

```
repair_item, eat_meal_portion, shower, clean_room, deep_clean,
budget_review, study_focused, work, study, sleep, eat_charity_rice,
pay_utilities, exercise, rest, purchase_item, sell_item, apply_job
```

**Current Behavior:**
- If tier 0 computed, falls back to tier 1 outcome
- No explicit failure state for these actions

**Is This Intentional?**
Likely yes for most actions. Examples:
- `shower`: Can't really "fail" a shower
- `sleep`: Can't fail to sleep (just sleep quality varies)
- `eat_charity_rice`: Can't fail to eat

**Actions That Might Benefit from Tier 0:**
- ❓ `repair_item`: Could break item further on bad roll
- ❓ `apply_job`: Could have explicit rejection outcome

**Recommendation:** Consider if any actions should have explicit failure outcomes

---

### 6. Tier Computation Thresholds ℹ️

**Location:** `src/roomlife/action_engine.py:356-362`

**Thresholds:**
```
base < 25   → tier 0 (fail/partial)
base < 55   → tier 1 (normal)
base < 85   → tier 2 (good)
base >= 85  → tier 3 (great)
```

**Score Components:**
- Primary skill: 0-100 (with aptitude scaling)
- Secondary skills: weighted addition
- Traits: 0-100 range, weighted
- Item quality: condition (0-100) × 0.7 + quality × 10, weighted
- RNG: ±8 points

**Analysis:**
- Tier 3 requires ~85 points total
- Primary skill alone maxes at 100
- Need high skill (70+) + good items + favorable traits + decent RNG for tier 3
- System well-balanced for progression

**Recommendation:** No changes needed, thresholds are reasonable

---

### 7. Parameter Type Safety ℹ️

**Issue:** Actions with `string` parameters don't validate references during parameter validation:

```yaml
sell_item:
  parameters:
    - name: item_id
      type: string  # Only validates it's a string, not that item exists
```

**Validation Flow:**
1. `param_resolver.validate_parameters()`: Checks type is string ✓
2. `execute_action()`: Checks if item exists at execution time ✓

**Why This Design?**
- String parameters are context-dependent (item_id, job_id)
- Validation happens in specialized execution code
- Keeps parameter system simple and extensible

**Impact:** None - works as designed

**Recommendation:** Consider adding optional `validates_against` field for future enhancement:
```yaml
parameters:
  - name: item_id
    type: string
    validates_against: items_catalog  # Future enhancement
```

---

## Positive Findings ✅

### What's Working Well:

1. **✅ Comprehensive Validation**
   - Duplicate action ID detection with line numbers
   - Type checking for all YAML fields
   - Clear error messages with file:line references

2. **✅ Safe Error Handling**
   - Graceful fallback for missing outcomes
   - Null checks before item operations
   - Try-catch in YAML parsing with detailed errors

3. **✅ Consistent Data Model**
   - All items in `items_meta.yaml` have complete metadata
   - All `provides` references in actions have corresponding items
   - All skills referenced are defined in `SKILL_NAMES` (except "logic")
   - All traits referenced are valid

4. **✅ Good Code Architecture**
   - Clear separation: specs → engine → catalog → API
   - Frozen dataclasses prevent accidental mutation
   - Line number tracking for YAML errors
   - Deterministic tier computation with RNG seeds

5. **✅ Test Coverage**
   - Test files exist for action engine, content integrity, determinism
   - Comprehensive test infrastructure in place

---

## Recommended Actions

### Immediate (Critical)
1. **Fix `study_focused` skill reference** - Replace `logic` with valid skill (e.g., `analysis`)

### Short-term (Within Sprint)
2. **Document tier 0 behavior** - Add comment in actions.yaml explaining fallback
3. **Review sell/discard limitation** - Decide if instance-level selection is needed
4. **Add validation for concurrent modifications** - Strengthen `apply_consumes()`

### Long-term (Future Enhancement)
5. **Enhance sell/discard with instance selection** - Allow choosing specific item instance
6. **Add parameter validation registry** - Validate string params against catalogs
7. **Consider re-validation on execution** - Re-check utilities in execute_action()
8. **Add tier 0 outcomes where appropriate** - For actions that can meaningfully fail

---

## Testing Recommendations

### Add Tests For:
1. ✅ Invalid skill reference handling
2. ✅ Duplicate item_id sell/discard scenarios
3. ✅ Concurrent modification during action execution
4. ✅ Missing tier outcomes (verify fallback works)
5. ✅ Money validation timing
6. ✅ Utility state changes during execution

### Existing Test Coverage:
- ✅ Action spec loading (test_action_engine.py)
- ✅ Content integrity (test_content_integrity.py)
- ✅ Determinism (test_determinism.py)
- ✅ Purchase actions (test_purchase.py)
- ✅ Movement (test_movement.py)
- ✅ Discard (test_discard.py)

---

## Summary Statistics

**Actions Reviewed:** 26
**Critical Errors:** 1 (invalid skill reference)
**Design Limitations:** 3 (documented/acceptable)
**Informational Issues:** 4 (mostly FYI)
**System Health:** 🟡 Good (requires 1 fix)

**Files Reviewed:**
- ✅ `/data/actions.yaml` (987 lines)
- ✅ `/data/items_meta.yaml` (194 lines)
- ✅ `/src/roomlife/content_specs.py` (357 lines)
- ✅ `/src/roomlife/action_engine.py` (980 lines)
- ✅ `/src/roomlife/catalog.py` (362 lines)
- ✅ `/src/roomlife/param_resolver.py` (171 lines)

---

## Conclusion

The YAML ActionCatalog system is **well-architected and production-ready** after fixing the critical "logic" skill reference. The system demonstrates:

- ✅ Strong validation and error handling
- ✅ Clear separation of concerns
- ✅ Comprehensive data-driven design
- ✅ Good documentation and comments

The identified design limitations are **known and documented**, with clear paths for future enhancement if needed. The system shows mature engineering practices with attention to determinism, testing, and extensibility.

**Primary Action Required:** Fix the `study_focused` action's `logic` skill reference.

---

*Review conducted by: Claude (AI Assistant)*
*Review methodology: Static code analysis, YAML validation, cross-reference checking*
