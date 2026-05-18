# Claude Code hooks for momentum-candle

This file documents what each hook does, why it exists, and how to disable
it temporarily during debugging. The machine-readable config is in
`settings.json`.

## UserPromptSubmit

### `skill-eval.py`
Runs on every prompt submission. Matches the prompt against
`hooks/skill-rules.json`. When matches exceed the confidence threshold,
emits a `SKILL ACTIVATION REQUIRED` block on stderr that Claude reads.
Pure Python, no Node dependency.

## PreToolUse

### `branch-guard.sh` (matcher: `Edit|Write|MultiEdit`)
Blocks every file edit when the current git branch is `main` or `master`.
Forces feature branches with conventional prefixes (`feat/`, `fix/`,
`strat/`, `ea/`).

Bypass: switch to a feature branch — `git checkout -b feat/<scope>`.

### `live-trade-guard.sh` (matcher: MT5 destructive tools)
Blocks calls to `place_market_order`, `modify_position`, `close_position`,
`close_all_positions` when **either**:
- `MT5_DRY_RUN` is not `0`, **or**
- the user prompt does not contain the literal token `CONFIRM_LIVE`.

Bypass for live trading: `MT5_DRY_RUN=0` in `.env` *and* prompt includes
`CONFIRM_LIVE`. Both conditions must hold.

## PostToolUse

### `ruff-format.sh` (matcher: `Edit|Write|MultiEdit`)
Runs `uv run ruff format` on changed `*.py` files, then
`uv run ruff check --fix` to auto-fix import order and trivial issues.
Runs silently on success; failures are non-blocking but surfaced.

### `pytest-on-edit.sh` (matcher: `Edit|Write|MultiEdit`)
Runs `uv run pytest -x --no-header -q` only when a `*.py` file under
`src/` or `tests/` was changed. Bails on first failure to keep feedback
fast. Non-blocking — the agent sees the failure but continues.

## Disabling temporarily

Either remove the relevant block from `settings.json` or copy the file to
`settings.local.json` (gitignored) with the unwanted hooks omitted —
Claude merges local on top of project settings.
