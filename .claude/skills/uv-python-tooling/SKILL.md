---
name: uv-python-tooling
description: uv add/sync/run, lockfile policy, .python-version. Use when adding/removing Python dependencies, syncing the venv, or pinning the Python version.
---

# uv tooling — what we use

## Install / bootstrap

```powershell
# one-time on a fresh machine
winget install astral-sh.uv
uv python install 3.12

# bootstrap project deps
uv sync
```

`uv sync` reads `pyproject.toml` + `uv.lock` and creates `.venv/` if
missing. No `python -m venv`, no manual activation.

## Running anything

```powershell
uv run mt5-mvp                # entrypoint script
uv run pytest                 # unit tests
uv run ruff check .           # lint
uv run python -c "..."        # one-off scripts
```

`uv run` resolves the project venv automatically — it works from any
shell, no activation needed.

## Adding deps

```powershell
uv add MetaTrader5            # runtime dep -> [project].dependencies
uv add --dev pytest           # dev dep    -> [dependency-groups].dev
uv remove some-package
```

Always commit the resulting `uv.lock` change.

## Python version pinning

`.python-version` contains `3.12`. uv reads it and uses the matching
toolchain. `pyproject.toml` constrains compatible versions:

```toml
requires-python = ">=3.12,<3.13"
```

We pin to 3.12 because the `MetaTrader5` lib only ships wheels up to 3.12
as of writing. The system Python on this dev machine is 3.14 — never use
it.

## Lockfile etiquette

- `uv.lock` is committed. Reproducible builds matter for trading code.
- Run `uv lock --upgrade` only when you intend to refresh deps; commit
  the result with a separate "deps: upgrade" commit.
- CI / VPS runs `uv sync --frozen` to refuse drift.

## What not to do

- No `pip install` outside the venv — uv manages it.
- No `python -m pip` either; `uv pip ...` if you really must.
- No global-install of project deps; everything stays in `.venv/`.
