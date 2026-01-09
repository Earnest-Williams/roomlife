from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from .engine import apply_action, new_game
from .io import load_state, save_state
from .view import build_view_model

app = typer.Typer(add_completion=False)
DEFAULT_SAVE = Path("saves/save_001.json")


def _render_status(vm: dict) -> None:
    t = vm["time"]
    rprint(f"[bold]{vm['location']['space_name']}[/bold]  (day {t['day']}, {t['slice']})")

    util = vm["utilities"]
    rprint(
        f"Utilities: power={util['power']} heat={util['heat']} water={util['water']}  "
        f"paid={vm['player']['utilities_paid']}"
    )
    rprint(f"Money: {vm['player']['money_pence']} pence")

    n = vm["player"]["needs"]
    table = Table(title="Needs", show_header=True, header_style="bold")
    table.add_column("Hunger")
    table.add_column("Fatigue")
    table.add_column("Warmth")
    table.add_column("Hygiene")
    table.add_column("Mood")
    table.add_row(str(n["hunger"]), str(n["fatigue"]), str(n["warmth"]), str(n["hygiene"]), str(n["mood"]))
    rprint(table)

    if vm["items_here"]:
        itable = Table(title="Room contents", show_header=True, header_style="bold")
        itable.add_column("Item")
        itable.add_column("Condition")
        itable.add_column("Slot")
        for it in vm["items_here"]:
            itable.add_row(it["item_id"], it["condition"], it["slot"])
        rprint(itable)

    if vm["recent_events"]:
        rprint("[bold]Recent events[/bold]")
        for e in vm["recent_events"]:
            rprint(f"- {e['event_id']}  {e.get('params', {})}")

    rprint("[bold]Actions[/bold]")
    for a in vm["actions_hint"]:
        rprint(f"- {a['id']}: {a['label']}")


def _load_or_new(path: Path):
    if path.exists():
        return load_state(path)
    return new_game()


@app.command()
def status(save: Path = DEFAULT_SAVE):
    state = _load_or_new(save)
    _render_status(build_view_model(state))


@app.command()
def act(action_id: str, save: Path = DEFAULT_SAVE, seed: int = 1):
    state = _load_or_new(save)
    apply_action(state, action_id, rng_seed=seed)
    save_state(state, save)
    _render_status(build_view_model(state))


@app.command()
def dump(save: Path = DEFAULT_SAVE):
    state = _load_or_new(save)
    print(json.dumps(build_view_model(state), indent=2, sort_keys=True))


def main():
    app()


if __name__ == "__main__":
    main()
