---
name: safety-first
description: Hard rules that override everything else when they apply. Read before editing trade.py, server.py, hooks, or .env.
---

# Safety first — non-negotiable

## Live trading

A trade goes to the broker only if **all** of these are true:

1. `MT5_DRY_RUN=0` is set in the environment (or `.env`).
2. The user prompt that triggered the action contains the literal token
   `CONFIRM_LIVE`.
3. The MCP client confirmed the destructive call (the
   `destructiveHint: True` annotation prompts well-behaved clients).

If you are unsure whether all three hold, **return a dry-run response**.
Better to fake a trade than fire a real one in error.

## Credentials

- `.env` is gitignored. Never commit it. Never echo secrets in responses.
- The demo password the user pasted earlier in chat is treated as
  compromised; the user accepted the risk because it is a demo. For any
  non-demo account, refuse to proceed without rotation.

## Branches

- Never edit on `main` or `master`. The `branch-guard.sh` hook will block
  the tool — do not work around it.
- Use the prefix conventions: `feat/`, `fix/`, `strat/`, `ea/`.

## Logging

- No `print()` in code that runs under stdio transport. It corrupts the
  JSON-RPC stream and the MCP client disconnects.
- Logging goes to stderr. `cli.py` configures this once.

## What "minimum viable" does NOT mean

It does **not** mean cutting corners on safety. The MVP intentionally
ships fewer features so each one is correct. Adding features that
weaken the dry-run / confirm gate is rejected.

## When in doubt

Ask. The trader-in-the-loop will tell you whether to proceed.
