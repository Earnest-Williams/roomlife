According to a document from **2026-01-11** (your `project_bundle.md` snapshot), here’s a concrete, “do-this-next” elaboration of each item, with code snippets that fit your current architecture and avoid the exact silent breakages you called out.

---

## Must-do (stability + correctness)

### 1) Add a “content integrity” check that runs in tests/CI

#### Why this is worth doing

Your content pipeline is already data-driven (YAML specs + loader code), but right now it’s still possible to ship content that “loads” while being subtly wrong:

* **Duplicate action IDs** in `actions.yaml` currently **overwrite silently** because `load_actions()` writes into a dict keyed by `id` without checking duplicates. That means the last definition wins, and the earlier one disappears with no signal. 
* **Shop catalog IDs** can drift from `items.yaml`, which breaks purchase action generation / UI listings.
* **`any_provides` depends on `items_meta.yaml` IDs matching actual item IDs**, otherwise capabilities exist “on paper” but never attach to real inventory items.

You already have a canonical test runner script that CI can call (`./scripts/test.sh` → `pytest`).

#### What I’d add

Create a dedicated test file, e.g. `tests/test_content_integrity.py`, and assert your invariants there.

##### ✅ Test: no duplicate action IDs (and YAML loads)

After you implement “duplicates are a hard error” (next section), this becomes a one-line smoke test:

```python
# tests/test_content_integrity.py
from pathlib import Path

from roomlife.content_specs import load_actions

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def test_actions_yaml_loads_and_has_unique_ids():
    # load_actions() should raise ValueError if duplicates exist.
    load_actions(DATA_DIR / "actions.yaml")
```

##### ✅ Test: every `shop_catalog.yaml` item exists in `items.yaml`

Your `shop_catalog.yaml` includes items like `vacuum`, `lamp_desk`, `lamp_floor` etc.
So make sure `items.yaml` defines them.

```python
# tests/test_content_integrity.py
import yaml
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def test_shop_catalog_items_exist_in_items_yaml():
    items_raw = _load_yaml(DATA_DIR / "items.yaml")
    catalog_raw = _load_yaml(DATA_DIR / "shop_catalog.yaml")

    item_ids = {it["id"] for it in items_raw.get("items", [])}

    missing = []
    for cat in catalog_raw.get("categories", []):
        cat_id = cat.get("id", "<unknown-category>")
        for item_id in cat.get("items", []):
            if item_id not in item_ids:
                missing.append(f"{cat_id}: {item_id}")

    assert not missing, "shop_catalog.yaml references unknown item ids:\n" + "\n".join(missing)
```

##### ✅ Test: `any_provides` providers must refer to real item IDs

This is the check that *directly* prevents “meta says X provides cleaning_kit but the actual item is named differently”.

Example:

* `deep_clean` requires `items.any_provides: ["cleaning_kit"]`.
* `items_meta.yaml` says `vacuum_cleaner` provides `cleaning_kit` (and `deep_clean_tool`).
* But the shop sells `vacuum` (not `vacuum_cleaner`).

So you want to fail if “provider meta IDs don’t exist as real items”.

```python
# tests/test_content_integrity.py
import yaml
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def test_any_provides_providers_are_real_item_ids():
    actions = _load_yaml(DATA_DIR / "actions.yaml").get("actions", [])
    items_meta = _load_yaml(DATA_DIR / "items_meta.yaml").get("items", [])
    items = _load_yaml(DATA_DIR / "items.yaml").get("items", [])

    base_item_ids = {it["id"] for it in items}

    # 1) Collect every capability referenced by requires.items.any_provides
    required_caps: set[str] = set()
    for a in actions:
        req = (a or {}).get("requires", {}) or {}
        items_req = req.get("items", {}) or {}
        required_caps.update(items_req.get("any_provides", []) or [])

    # 2) For each required capability, find all meta items that claim they provide it
    errors = []
    for cap in sorted(required_caps):
        providers = []
        for m in items_meta:
            provides = set(m.get("provides", []) or [])
            tags = set(m.get("tags", []) or [])
            if cap in provides or cap in tags:
                providers.append(m["id"])

        # If no item can provide it, that action requirement is impossible.
        assert providers, f"No items_meta entries provide/tag capability '{cap}'"

        # Every provider must exist as a real item id (items.yaml),
        # otherwise it's a “phantom provider” and will never satisfy requirements.
        for pid in providers:
            if pid not in base_item_ids:
                errors.append(f"cap '{cap}' is provided by meta item '{pid}', but '{pid}' not found in items.yaml")

    assert not errors, "Invalid any_provides providers:\n" + "\n".join(errors)
```

**CI wiring:** If your CI already runs `./scripts/test.sh`, you’re done (it runs `pytest`).

---

### 2) Make duplicate action IDs a hard error in `load_actions`

#### Why this is a correctness bug today

Your current loader overwrites duplicates silently:

```py
out[a["id"]] = ActionSpec(...)
```

so the last action spec wins with no warning.

You already have YAML line plumbing (`_action_line_map`, `_get_action_line`) to produce human-friendly errors.

#### Fix: detect duplicates and raise `ValueError` with line numbers

One subtlety: `_action_line_map` stores a dict keyed by `action_id`, so for duplicates the map can’t represent *both* lines. Your `index_lines` list is the reliable source for “nth action’s line”. Today `_get_action_line` prefers the id-map first, which can point at the *wrong* line in a duplicates scenario.

So I’d do two changes:

1. Prefer `index_lines[idx]` when available
2. Track `seen[action_id] = first_line` and raise when you hit it again

```python
# src/roomlife/content_specs.py

def _get_action_line(a: Any, line_map: Dict[str, int], index_lines: List[int], idx: int | None) -> int | None:
    # Prefer index-based line numbers; id-based mapping can't disambiguate duplicates.
    if idx is not None and idx < len(index_lines):
        return index_lines[idx]

    action_id = a.get("id") if isinstance(a, dict) else None
    if action_id:
        line = line_map.get(action_id)
        if line is not None:
            return line

    return None


def load_actions(path: str | Path) -> Dict[str, ActionSpec]:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    raw, text = _load_yaml_mapping(file_path)
    out: Dict[str, ActionSpec] = {}

    actions = raw.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError(f"{file_path}: actions must be a list")

    line_map, index_lines = _action_line_map(text)

    seen: Dict[str, int] = {}  # action_id -> first line number

    for idx, a in enumerate(actions):
        line = _get_action_line(a, line_map, index_lines, idx)
        _validate_action_dict(a, line)  # uses line in error messages

        action_id = a["id"]
        if action_id in seen:
            first_line = seen[action_id]
            this_line = line or "?"
            raise ValueError(
                f"{file_path}:{this_line}: duplicate action id '{action_id}' "
                f"(first defined at line {first_line})"
            )

        seen[action_id] = line or -1

        out[action_id] = ActionSpec(
            id=a["id"],
            display_name=a.get("display_name", a["id"]),
            description=a.get("description", ""),
            category=a.get("category", "other"),
            time_minutes=int(a.get("time_minutes", 0)),
            requires=a.get("requires", {}),
            modifiers=a.get("modifiers", {}),
            outcomes=_parse_outcomes(a.get("outcomes", {})),
            consumes=a.get("consumes"),
            parameters=a.get("parameters"),
            dynamic=a.get("dynamic"),
        )

    return out
```

Result: authors get a **fast, line-numbered** failure instead of silent overwrite.

---

### 3) Normalize/align IDs between `items.yaml` and `items_meta.yaml`

#### Why this matters mechanically (not just cleanliness)

Your engine loads item meta keyed by `id`:

```py
out[it["id"]] = ItemMeta(...)
```

so at runtime, an `Item(item_id="vacuum")` only gets meta if `items_meta.yaml` has `id: vacuum`.

Right now you have concrete mismatches:

* `items_meta.yaml` defines `vacuum_cleaner` (provides `cleaning_kit`)
* Shop sells `vacuum`
* `deep_clean` requires `any_provides: ["cleaning_kit"]`

Also:

* `items_meta.yaml`: `desk_lamp`, `floor_lamp`
* Shop sells `lamp_desk`, `lamp_floor`

So “capabilities exist” but don’t attach to real inventory items, which is exactly the “vacuum/vacuum_cleaner mismatch” class of bug.

#### Fix option A (recommended): make `items.yaml` IDs canonical

Because `shop_catalog.yaml` and `items.yaml` already agree on names like `lamp_desk` / `lamp_floor`, the cleanest fix is to rename the meta IDs to match the base IDs.

##### Patch snippet: `data/items_meta.yaml`

```yaml
# data/items_meta.yaml

# Cleaning items
- id: cleaning_supplies
  name: "Cleaning supplies"
  tags: ["tool", "cleaning"]
  provides: ["cleaning_kit"]
  requires_utilities: []
  durability:
    max: 50
    degrade_per_use_default: 2

- id: vacuum            # <-- was vacuum_cleaner
  name: "Vacuum cleaner"
  tags: ["appliance", "cleaning"]
  provides: ["cleaning_kit", "deep_clean_tool"]
  requires_utilities: ["power"]
  durability:
    max: 100
    degrade_per_use_default: 3

# Lighting
- id: lamp_desk         # <-- was desk_lamp
  name: "Desk lamp"
  tags: ["lighting"]
  provides: ["task_lighting"]
  requires_utilities: ["power"]
  durability:
    max: 100
    degrade_per_use_default: 1

- id: lamp_floor        # <-- was floor_lamp
  name: "Floor lamp"
  tags: ["lighting"]
  provides: ["ambient_lighting"]
  requires_utilities: ["power"]
  durability:
    max: 100
    degrade_per_use_default: 1
```

This keeps all existing references in `shop_catalog.yaml` intact.

#### Fix option B: introduce an explicit alias layer

If you need backward compatibility for save files that already contain `vacuum_cleaner`, add an alias mapping on load (or a migration step), but keep content canonical. Example:

```python
# src/roomlife/content_specs.py (or a dedicated migration module)

ITEM_ID_ALIASES = {
    "vacuum_cleaner": "vacuum",
    "desk_lamp": "lamp_desk",
    "floor_lamp": "lamp_floor",
}

def canonical_item_id(item_id: str) -> str:
    return ITEM_ID_ALIASES.get(item_id, item_id)
```

Then apply it when loading old saves / items, not in the meta itself.

---

### 4) Resolve `repair_item` to one parameter style (keep `item_ref`)

#### Why it’s currently inconsistent

You *already* lean heavily toward `item_ref`:

* `ActionCall.from_legacy()` maps legacy `repair_<item_id>` into `ActionCall("repair_item", {"item_ref": {"mode": "by_item_id", ...}})`
* `ActionCatalog._list_repair_actions()` enumerates repair actions using `item_ref` with `mode: "instance_id"`

…and your parameter validator only knows how to validate `space_id` and `item_ref`.

But `actions.yaml` currently defines `repair_item` twice (duplicate IDs), and the later one uses `item_id` with `type: item_at_location`.
That duplicate will overwrite the good version today (silent overwrite), and will become a hard error once you fix duplicates.

#### Fix: delete the `item_at_location` version

Keep the existing `item_ref` version:

```yaml
# data/actions.yaml
- id: repair_item
  display_name: "Repair item"
  parameters:
    - name: item_ref
      type: item_ref
      required: true
  requires:
    location:
      any_space_tags: ["room", "shared"]
    items:
      item_ref_constraints:
        in_inventory: true
  outcomes:
    # ...
```

…and remove the duplicate entry that uses `item_id: item_at_location`.

---

## Next (usability + scaling)

### 5) Generalize “parameterized action listing” for `pick_up_item` and `drop_item`

#### Current behavior

`ActionCatalog.list_available()` only parameterizes:

* movement (`move_to_space`) and
* repair (`repair_item`)

Everything else is only listed if it has **no required parameters** (`_is_listing_safe`).

But:

* `pick_up_item` requires `item_ref`
* `drop_item` requires `item_ref`

So neither will show up in “available actions” unless you enumerate them like you do for repair/move.

#### Implementation: add `_list_pickup_actions` and `_list_drop_actions`

```python
# src/roomlife/action_catalog.py

from .action_call import ActionCall
from .models import State

class ActionCatalog:
    # ...

    def list_available(self, state: State) -> List[ActionCard]:
        cards: List[ActionCard] = []

        # existing safe listing
        for spec in self.specs.values():
            if not self._is_listing_safe(spec):
                continue
            call = ActionCall(spec.id, {})
            ok, reason, missing = self._validate_call(state, call)
            cards.append(ActionCard(
                call=call,
                display_name=spec.display_name,
                description=spec.description,
                available=ok,
                missing_requirements=missing if not ok else None,
            ))

        # existing parameterized listings
        cards.extend(self._list_move_actions(state))
        cards.extend(self._list_repair_actions(state))

        # NEW
        cards.extend(self._list_pickup_actions(state))
        cards.extend(self._list_drop_actions(state))

        return cards

    def _list_pickup_actions(self, state: State) -> List[ActionCard]:
        spec = self.specs.get("pick_up_item")
        if not spec:
            return []

        cards: List[ActionCard] = []
        here = state.world.location

        for it in state.items:
            if it.placed_in != here:
                continue

            call = ActionCall(
                "pick_up_item",
                {"item_ref": {"mode": "instance_id", "instance_id": it.instance_id}},
            )
            ok, reason, missing = self._validate_call(state, call)
            # (Optional) use item_meta for nicer names
            meta = self.item_meta.get(it.item_id)
            item_name = meta.name if meta else it.item_id

            cards.append(ActionCard(
                call=call,
                display_name=f"Pick up {item_name}",
                description=spec.description,
                available=ok,
                missing_requirements=missing if not ok else None,
            ))

        return cards

    def _list_drop_actions(self, state: State) -> List[ActionCard]:
        spec = self.specs.get("drop_item")
        if not spec:
            return []

        cards: List[ActionCard] = []
        for it in state.items:
            if it.placed_in != "inventory":
                continue

            call = ActionCall(
                "drop_item",
                {"item_ref": {"mode": "instance_id", "instance_id": it.instance_id}},
            )
            ok, reason, missing = self._validate_call(state, call)
            meta = self.item_meta.get(it.item_id)
            item_name = meta.name if meta else it.item_id

            cards.append(ActionCard(
                call=call,
                display_name=f"Drop {item_name}",
                description=spec.description,
                available=ok,
                missing_requirements=missing if not ok else None,
            ))

        return cards
```

This mirrors your existing move/repair patterns, and will make pickup/drop show up naturally in UI.

---

### 6) Decide what remains legacy vs YAML

#### Current state (hybrid)

Your API merges:

* YAML-driven actions (`ActionCatalog`) and
* legacy action metadata,

then filters out legacy actions if a YAML equivalent exists (by checking `ActionCall.from_legacy`).

That’s a good migration approach, but the system remains cognitively heavy because:

* Some actions exist in two places (legacy + YAML), and
* The CLI view still shows hardcoded “actions_hint” including legacy actions (work/study/sleep etc).

#### Practical migration approach

1. **Define “source of truth” per action domain**

   * Movement, pickup/drop, repair, cleaning, cooking, etc → YAML
   * Purchases (dynamic catalog) → could stay legacy until you model shop actions in YAML
   * Jobs/bills/events → whichever is faster

2. **Add an explicit gate flag**
   Example: only include legacy actions in metadata when `enable_legacy=True`.

```python
# src/roomlife/api_service.py

class RoomLifeAPI:
    def __init__(self, *, enable_legacy_actions: bool = True):
        self.enable_legacy_actions = enable_legacy_actions
        # existing init...

    def _get_action_metadata_list(self) -> List[ActionMetadata]:
        catalog_actions = self._get_catalog_action_metadata_list()

        legacy_actions: List[ActionMetadata] = []
        if self.enable_legacy_actions:
            legacy_actions = self._get_legacy_action_metadata_list()

            # existing filter-out logic for overlap:
            legacy_actions = [
                action for action in legacy_actions
                if ActionCall.from_legacy(action.action_id).action_id not in self._action_specs
            ]

        return catalog_actions + legacy_actions
```

3. **Eventually retire legacy**
   As you port actions like work/study/sleep into YAML, you can delete the legacy branches in `engine.apply_action`, or leave them behind a migration flag until old saves are migrated.

---

### 7) Expand parameter validation support (or tighten it)

#### The current issue

Your spec validator supports only:

* `space_id`
* `item_ref`

and silently ignores other parameter types.

That means a spec can introduce `type: item_at_location` (as the duplicate `repair_item` spec does) and it won’t be validated properly.

#### Simplest safe path: reject unknown parameter types

```python
# src/roomlife/param_resolver.py

def validate_parameters(state: State, spec: ActionSpec, call: ActionCall) -> Tuple[bool, str | None]:
    if not spec.parameters:
        return True, None

    missing = []
    for p in spec.parameters:
        name = p.get("name")
        ptype = p.get("type")
        required = bool(p.get("required"))
        constraints = p.get("constraints") or {}

        if required and name not in call.params:
            missing.append(name)
            continue

        if name not in call.params:
            continue

        # supported types
        if ptype == "space_id":
            ok, err = validate_space_id(state, call.params[name])
            if not ok:
                missing.append(f"{name} ({err})")

        elif ptype == "item_ref":
            ok, err = validate_item_ref(state, call.params[name], constraints=constraints)
            if not ok:
                missing.append(f"{name} ({err})")

        else:
            # NEW: fail hard on unknown types so specs can't silently rot
            missing.append(f"{name} (unknown parameter type: {ptype})")

    if missing:
        return False, f"parameter validation failed: {', '.join(missing)}"

    return True, None
```

Then add a content test to ensure all `parameters[].type` are from an allowed set. This prevents “spec drift” as content authors experiment.

If you *do* want `item_at_location`, implement it end-to-end (resolution + validation + listing + execution), but until then, rejecting unknown types is the safest scaling move.

---

### 8) Lean into previews for player clarity

#### What you already have

`validate_action()` already computes:

* `preview_tier_distribution(...)`
* `preview_delta_ranges(...)`
* `build_preview_notes(...)`

and returns them as `ActionValidation.preview`.

That’s great—right now it’s just not leveraged for “at-a-glance” browsing in the action list.

#### Recommended UX step: include preview in action metadata

Instead of requiring the client to call `validate_action` per action, you can add an **optional preview** field on `ActionMetadata`.

##### Step 1: extend `ActionMetadata`

```python
# src/roomlife/api_types.py

@dataclass
class ActionMetadata:
    action_id: str
    display_name: str
    description: str
    category: ActionCategory
    available: bool
    missing_requirements: Optional[List[str]] = None
    requirements: Optional[Dict[str, Any]] = None
    effects: Optional[Dict[str, Any]] = None

    # NEW (additive)
    preview: Optional[ActionPreview] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "actionId": self.action_id,
            "displayName": self.display_name,
            "description": self.description,
            "category": self.category.value,
            "available": self.available,
            "missingRequirements": self.missing_requirements,
            "requirements": self.requirements,
            "effects": self.effects,
        }
        if self.preview is not None:
            d["preview"] = self.preview.to_dict()
        return d
```

##### Step 2: populate it when building catalog actions

```python
# src/roomlife/api_service.py

def _get_catalog_action_metadata_list(self) -> List[ActionMetadata]:
    # ...
    for card in catalog.list_available(self._state):
        spec = self._action_specs.get(card.call.action_id)
        preview = None
        if spec is not None:
            # Cheap + deterministic previews
            tier_dist = preview_tier_distribution(self._state, spec, samples=9, rng_seed=1)
            delta_ranges = preview_delta_ranges(spec)
            notes = build_preview_notes(self._state, spec)
            preview = ActionPreview(
                tier_distribution=tier_dist,
                delta_ranges=delta_ranges,
                notes=notes,
            )

        actions.append(ActionMetadata(
            action_id=card.call.action_id,
            display_name=card.display_name,
            description=card.description,
            category=ActionCategory.from_string(spec.category if spec else "other"),
            available=card.available,
            missing_requirements=card.missing_requirements,
            requirements={"params": card.call.params} if card.call.params else None,
            preview=preview,
        ))
```

Now your UI can show:

* “Expected hunger change: -20 to -35”
* “Likely tier: 60% good / 30% ok / 10% bad”
* Notes like “Missing: cleaning_kit” / “Requires power”

…without trial-and-error.

---

If you apply the **Must-do** items first, you’ll eliminate the two biggest sources of silent breakage in this codebase today:

* silent overwrites (duplicate action IDs)
* capability providers that don’t match actual item IDs (vacuum/lamp mismatches)

And the “Next” items will make the YAML system feel complete to players (action listings + previews) without needing a huge rewrite.
