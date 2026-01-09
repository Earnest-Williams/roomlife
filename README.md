# roomlife

A text-first lifesim engine where most play is reflected in a single room (and later a renderer can be attached).

## Setup (sdc + direnv)
From the project directory, run:
- `sdc` for a new environment
- `sdc -u` to update an existing environment from `environment.yml`
- `sdc -f` to remove and recreate the environment

## Run
```bash
python -m roomlife status
python -m roomlife act work
python -m roomlife act eat_charity_rice
python -m roomlife dump
```

## Layout
- `src/roomlife/`: engine, models, IO, view-model, CLI
- `data/`: content (YAML)
- `saves/`: save snapshots
- `tests/`: determinism and invariants
