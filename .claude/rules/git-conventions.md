---
name: git-conventions
description: Branch naming and conventional commit rules for momentum-candle.
---

# Git conventions

## Branch prefixes

| Prefix | Use for |
|---|---|
| `feat/` | new functionality |
| `fix/` | bug fixes |
| `chore/` | tooling, deps, formatting |
| `docs/` | docs and skills only |
| `strat/` | strategy work (e.g. `strat/momentum-candle-v1`) |
| `ea/` | MQL5 EA work |
| `test/` | test-only changes |

`branch-guard.sh` blocks edits when the current branch is `main` or
`master`. Always create a feature branch first.

## Conventional commits

```
<type>[scope]: <subject>

[body, optional]
```

Examples:

```
feat(trade): add place_market_order with dry-run guard
fix(client): timeout init when terminal is unresponsive
chore(deps): upgrade fastmcp to 2.4.0
docs(strategy): document momentum-candle entry rules
strat(momentum-candle): add ATR filter
```

## What we don't do

- No `--amend` to published commits.
- No `--force` push to shared branches.
- No commits straight to `main`.
- No mixing unrelated changes in one commit (split with `git add -p`).

## Releases

Out of scope for MVP. We ship from `main` to a single demo terminal.
