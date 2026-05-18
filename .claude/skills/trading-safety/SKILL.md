---
name: trading-safety
description: Dry-run discipline, magic numbers, idempotency, CONFIRM_LIVE token. Use whenever destructive trade tools, MT5_DRY_RUN, or live-trade gates are involved.
---

# Trading safety — the rules

## Three-layer guard for live trades

A destructive call only goes live when **all three** align:

1. **Code check** — `_utils.is_dry_run()` must return False.
   That requires `MT5_DRY_RUN=0` in the environment.
2. **MCP annotation** — every destructive tool is `destructiveHint: True`,
   so well-behaved clients ask for confirmation.
3. **Hook check** — `.claude/hooks/live-trade-guard.sh` blocks the call
   unless the user prompt contains the literal token `CONFIRM_LIVE`.

Bypassing any one is sloppy. Bypassing all three is intent.

## Default is dry-run

`.env.example` ships `MT5_DRY_RUN=1`. The shipped tool responses include:

```json
{
  "dry_run": true,
  "request": { ...what we WOULD send... },
  "note": "MT5_DRY_RUN is active. ..."
}
```

When you see this, surface it to the user verbatim — do not silently retry.

## Magic numbers and comments

- Every order **must** carry a `magic` and `comment`.
- Default magic comes from `MT5_MAGIC` (env, default `900001`).
- Per-signal magics use the form `9XXXX<short_id>` so a retry of the same
  signal can be deduped by checking `positions_get()` for matching magic +
  comment.
- Comment format: `mt5-mvp[/source][:signal-<id>]`, e.g.
  `mt5-mvp/telegram:signal-2147`.

## Idempotent signal execution

When ingesting Telegram or EA signals, dedupe before sending:

```python
existing = mt5.positions_get()
if any(p.magic == magic and p.comment == comment for p in (existing or [])):
    return {"skipped": "already_open", "magic": magic}
```

## Volume safety

- Always normalise volume against `symbol_info` (see
  `trade._normalize_volume`).
- Reject zero volume early — broker returns retcode 10014.
- Default deviation for XAUUSD on InstaForex demo is 30 points; spreads
  can be wide.

## Stop loss / take profit

- Use **absolute prices**, not points or pips, in `place_market_order`.
- Pass through to `mt5` only after sanity check: `sl < bid` for BUY,
  `sl > ask` for SELL.

## What is **not** safe yet

- We do not yet support pending orders, partial-fill recovery, trailing
  stops, or break-even moves. Phase 2+.
- No max-positions or daily-loss circuit breaker. Phase 2.
- No retry-with-different-filling-mode on retcode 10030 (invalid filling).
  Add only after we have telemetry from the demo.
