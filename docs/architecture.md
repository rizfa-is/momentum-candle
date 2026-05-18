# Architecture

## Goal

Let AI agents and downstream signal sources drive a MetaTrader 5 terminal
through a small, safe surface area. Strategy focus is the
**momentum-candle** pattern on **XAUUSD**.

## Layered design

```
┌──────────────────────────────────────────────────────────────────┐
│  AI client (Claude Desktop, opencode, Claude Code)               │
└──────────────────────────────────────────────────────────────────┘
                              │ MCP (stdio | sse | http)
┌──────────────────────────────────────────────────────────────────┐
│  src/mt5_mvp/server.py     FastMCP — 8 tools                     │
│      ├─ readOnlyHint:  get_account, get_symbol_price,            │
│      │                 get_candles_latest, get_positions          │
│      └─ destructiveHint: place_market_order, modify_position,    │
│                          close_position, close_all_positions     │
├──────────────────────────────────────────────────────────────────┤
│  src/mt5_mvp/{account,market,trade}.py                           │
│  Domain handlers — return plain dicts; honour MT5_DRY_RUN.       │
├──────────────────────────────────────────────────────────────────┤
│  src/mt5_mvp/client.py     ensure_initialized + thread-timeout   │
│  src/mt5_mvp/constants.py  TIMEFRAME / ORDER_TYPE / FILLING maps │
│  src/mt5_mvp/_utils.py     to_dict, retcode helpers, dry-run     │
├──────────────────────────────────────────────────────────────────┤
│  MetaTrader5 (PyPI)        official Python ↔ MT5 terminal bridge │
├──────────────────────────────────────────────────────────────────┤
│  MetaTrader 5 terminal     logged into InstaForex demo           │
└──────────────────────────────────────────────────────────────────┘
```

## Safety model — defense in depth

Three independent guards must align for a live trade:

1. **Code-level dry-run** — `_utils.is_dry_run()` reads `MT5_DRY_RUN`. If
   set to `1` (the default), `place_market_order`, `modify_position`,
   `close_position`, `close_all_positions` return a synthetic
   `{"dry_run": true, "request": {...}}` and never touch
   `mt5.order_send`.
2. **MCP annotations** — every destructive tool is tagged
   `destructiveHint: True`. Well-behaved MCP clients prompt the user
   before executing them.
3. **Claude hook** — `.claude/hooks/live-trade-guard.sh` runs as a
   `PreToolUse` hook and blocks destructive tool calls when both
   `MT5_DRY_RUN!=1` and the user prompt does **not** contain the literal
   token `CONFIRM_LIVE`.

Bypassing one layer is usually a slip; bypassing all three requires intent.

## Idempotency model

- Every order request carries a `magic` and `comment`. Default magic comes
  from `MT5_MAGIC` (env). Telegram / EA-bridge signals will pass per-signal
  magics in the form `9XXXX<signal_id>`.
- Comment format: `mt5-mvp[/source][:signal-<id>]`.
- `place_market_order` returns the broker-assigned `order` and `deal`
  IDs in addition to the `magic`, so the caller can record + dedupe.

## Connection management

`client.ensure_initialized()` runs before every tool. Three checks, each
wrapped in `_run_with_timeout` (default 15s):

1. `terminal_info()` reachable → terminal is alive.
2. `account_info().login != 0` → we're logged in.
3. If not logged in *and* credentials are provided in env, run
   `mt5.login()`.

Every blocking MT5 call is run in a daemon thread with timeout, so a hung
terminal cannot freeze the MCP server.

## InstaForex-specific notes

- Server name: `InstaForex-Server` (no trailing space).
- Default symbol: `XAUUSD`. Cent accounts use suffixes — not a concern for
  this demo.
- Filling mode: auto-detected from `symbol_info.filling_mode` flags. For
  XAUUSD on this demo it usually resolves to IOC; falls back to RETURN.
- Volume min/step usually `0.01`. `_normalize_volume` reads these live
  rather than hardcoding.

## Phasing

| Phase | Scope | Status |
|---|---|---|
| **1 — MVP MCP server** | Core package + 8 tools + `.claude/` Phase-1+2 + tests | **in this branch** |
| 2 — Live-trade hardening | Real-account dry runs, retcode telemetry, magic-namespaced signals | next |
| 3 — Signal ingestion | Telegram listener (aiogram), `/execute-signal` parser, risk-sizing | planned |
| 4 — Strategy automation | YouTube transcript ingestion (`/ingest-video`), strategy harness, walk-forward backtests | planned |
| 5 — VPS deploy | NSSM service, SSE transport, monitoring | planned |
| 6 — MQL5 EA bridge | Tiny EA emits signals over file/socket; Python executes | optional |

## Out of scope for MVP

- Pending orders (BUY_LIMIT / SELL_STOP / etc.).
- Trade history (`history_orders_get`, `history_deals_get`).
- Tick-level data, WebSocket quote streamer.
- TradingView webhook receiver.
- GitHub Actions scheduled workflows.

## Testing strategy

- Unit tests stub `MetaTrader5` via `tests/conftest.py` — no real terminal.
- Integration tests (`@pytest.mark.integration`) gated by `MT5_INTEGRATION=1`
  env flag, run only against a demo account.
- The dry-run path of every destructive tool has at least one unit test.
