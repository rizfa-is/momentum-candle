---
description: Parse a free-form trading signal and execute it via MCP. Always dry-run unless MT5_DRY_RUN=0 AND prompt contains CONFIRM_LIVE.
allowed-tools: mcp__mt5-mvp__get_account, mcp__mt5-mvp__get_symbol_price, mcp__mt5-mvp__get_positions, mcp__mt5-mvp__place_market_order
---

# /execute-signal

Parse the signal text in `$ARGUMENTS` and place it on the account.

## Recognised formats

```
BUY XAUUSD 0.01 SL 2340 TP 2360
SELL EURUSD 0.05 SL 1.0900 TP 1.0820 magic=900042
LONG XAUUSD 0.02 sl=2340.5 tp=2360.0
```

Aliases:
- `LONG` → `BUY`, `SHORT` → `SELL`.
- `sl=`, `SL`, `stop` all mean the stop-loss price.
- `tp=`, `TP`, `target` all mean the take-profit price.

## Steps

1. **Parse**. Extract `side`, `symbol`, `volume`, `sl`, `tp`, optional
   `magic`, optional `comment`. Default symbol is XAUUSD if missing.
   If parsing fails, ask the user for clarification — do NOT guess.
2. **Sanity check** with read-only tools:
   - `get_account` — verify `trade_allowed: true` and equity is non-zero.
   - `get_symbol_price` — confirm bid/ask are present.
   - For BUY: assert `sl < bid`. For SELL: assert `sl > ask`. If wrong,
     ask the user to fix the levels.
3. **Idempotency check**. Call `get_positions(symbol)`. If a position with
   the same `magic` and side already exists, report it and stop.
4. **Execute** via `place_market_order`. Pass `magic` and a `comment` of
   the form `mt5-mvp/manual:<short-id>` (use a short hash of the signal
   text).
5. **Report** the response. Highlight `dry_run`, `retcode`,
   `retcode_text`, `order`/`deal` IDs.

## Live trading

`place_market_order` is destructive. The `live-trade-guard` hook will
block the call unless **both**:

- `MT5_DRY_RUN=0` in `.env`, and
- this prompt contains the literal token `CONFIRM_LIVE`.

If the hook blocks the call, surface its message verbatim and stop.

## Output format

Three sections: `Parsed`, `Pre-flight`, `Result`. Keep each short.

```
Parsed
  side=BUY  symbol=XAUUSD  volume=0.01  sl=2340.00  tp=2360.00  magic=900001

Pre-flight
  bid=2350.10  ask=2350.50  trade_allowed=yes  duplicate=no

Result
  dry_run=true  retcode=10009  order=183927461  deal=183927462
```

## Refuse

- Volumes above `0.5` lots on a fresh demo without explicit user okay.
- SL absent on real-money signals — always require a stop loss.
- Unknown symbols — ask the user instead of mapping to a guess.
