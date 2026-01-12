"""
Content integrity tests for YAML data files.

These tests ensure that the data files are internally consistent and catch
silent breakages like duplicate IDs, missing references, and ID mismatches.
"""
import yaml
from pathlib import Path

from roomlife.content_specs import load_actions

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_yaml(path: Path):
    """Load a YAML file and return its contents."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_actions_yaml_loads_and_has_unique_ids():
    """Test that actions.yaml loads without duplicate action IDs.

    After implementing duplicate detection in load_actions(), this test
    ensures that the loader will raise ValueError if duplicates exist.
    """
    # load_actions() should raise ValueError if duplicates exist.
    load_actions(DATA_DIR / "actions.yaml")


def test_shop_catalog_items_exist_in_items_yaml():
    """Test that every item in shop_catalog.yaml exists in items.yaml.

    This prevents broken purchase actions and UI listings where the shop
    references items that don't exist in the base items definition.
    """
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


def test_any_provides_providers_are_real_item_ids():
    """Test that items_meta entries that provide capabilities exist in items.yaml.

    This prevents the "phantom provider" bug where:
    - An action requires items.any_provides: ["cleaning_kit"]
    - items_meta.yaml says vacuum_cleaner provides cleaning_kit
    - But shop sells "vacuum", not "vacuum_cleaner"

    Result: the capability exists "on paper" but never attaches to real items.
    """
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
        # otherwise it's a "phantom provider" and will never satisfy requirements.
        for pid in providers:
            if pid not in base_item_ids:
                errors.append(f"cap '{cap}' is provided by meta item '{pid}', but '{pid}' not found in items.yaml")

    assert not errors, "Invalid any_provides providers:\n" + "\n".join(errors)


def test_items_meta_ids_exist_in_items_yaml():
    """Test that every item in items_meta.yaml exists in items.yaml.

    This is a broader check than the any_provides test - it ensures ALL
    metadata entries correspond to actual items, not just capability providers.
    """
    items_raw = _load_yaml(DATA_DIR / "items.yaml")
    items_meta_raw = _load_yaml(DATA_DIR / "items_meta.yaml")

    item_ids = {it["id"] for it in items_raw.get("items", [])}
    meta_ids = {it["id"] for it in items_meta_raw.get("items", [])}

    missing = meta_ids - item_ids
    assert not missing, "items_meta.yaml defines metadata for non-existent items:\n" + "\n".join(sorted(missing))


def test_all_parameter_types_are_supported():
    """Test that all parameter types in actions.yaml are supported by the validator.

    This prevents spec drift where content authors add new parameter types
    that aren't actually validated by the parameter resolver.
    """
    actions = _load_yaml(DATA_DIR / "actions.yaml").get("actions", [])

    SUPPORTED_TYPES = {"space_id", "item_ref", "string"}

    unsupported = []
    for action in actions:
        action_id = action.get("id", "<unknown>")
        parameters = action.get("parameters", [])
        for param in parameters:
            param_name = param.get("name", "<unknown>")
            param_type = param.get("type")
            if param_type not in SUPPORTED_TYPES:
                unsupported.append(f"{action_id}.{param_name}: {param_type}")

    assert not unsupported, "actions.yaml contains unsupported parameter types:\n" + "\n".join(unsupported)
