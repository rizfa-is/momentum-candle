# momentum-candle — project memory

This file is loaded at the start of every Claude/opencode session. Read it
before doing anything in this repo.

## Mission

Build an MCP server + signal-automation toolkit that lets AI agents (Claude
Desktop, opencode) and downstream signal sources (Telegram, custom MQL5 EA)
drive a MetaTrader 5 terminal. Strategy focus: **momentum-candle on XAUUSD**.

## Stack (locked)

- **Python 3.12** managed by **uv** (system Python is 3.14 — never use it).
- **FastMCP 2.x** for the MCP server (stdio + SSE + streamable-http).
- **MetaTrader5** (PyPI) — official MetaQuotes integration, Windows-only.
- **ruff** for lint + format. **pytest** for tests.
- No `pip`, `venv activate`, or system-Python invocations. Always use
  `uv run …` so the project venv resolves correctly.

## Account & broker

- Demo account on **InstaForex-Server** (server name has no trailing space).
- Default symbol: **XAUUSD** (gold). All examples and strategy work assume it.
- InstaForex demos commonly require `ORDER_FILLING_RETURN`. The code
  auto-detects via `symbol_info.filling_mode` — do not hardcode.

## Critical safety rules

1. **`MT5_DRY_RUN=1` is the default** in `.env.example`. Destructive tools
   simulate when this is on.
2. To go live the user must:
   - set `MT5_DRY_RUN=0` in `.env`, **and**
   - include the literal token `CONFIRM_LIVE` in the prompt.
   The `live-trade-guard.sh` hook enforces the second condition.
3. Every trading order **must** carry a magic number and comment so signals
   are idempotent. Default magic comes from `MT5_MAGIC` (env).
4. Never call `print()` in stdio-mode code — it corrupts the JSON-RPC
   stream. Use `logging` against stderr (configured in `cli.py`).
5. Never commit `.env`. Investor & trader passwords stay out of git.

## Repo map

```
src/mt5_mvp/        — MVP package (8 MCP tools)
  __init__.py
  constants.py      — TIMEFRAME / ORDER_TYPE / FILLING / TIME maps
  _utils.py         — to_dict, dry-run flag, retcode helpers
  client.py         — ensure_initialized + thread-timeout guard
  account.py        — get_account
  market.py         — get_symbol_price, get_candles_latest
  trade.py          — market orders, modify, close, close_all
  server.py         — FastMCP wiring + global instructions
  cli.py            — entrypoint w/ --transport stdio|sse|http

tests/              — unit tests; MetaTrader5 stubbed in conftest.py
docs/               — architecture + strategy docs
.claude/            — agents, commands, hooks, skills, rules
.mcp.json           — registers mt5-mvp server for Claude/opencode
.env.example        — copy to .env, fill credentials
```

## Key commands

```powershell
# bootstrap deps (Windows)
uv sync

# run the MCP server (stdio for local clients)
uv run mt5-mvp --transport stdio

# run remote-style for VPS testing
uv run mt5-mvp --transport sse --host 127.0.0.1 --port 8765

# tests + lint
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Out of scope for MVP

- Pending orders, history queries, ticks, Telegram listener, MQL5 EA
  bridge, WebSocket quote streamer, TradingView webhook,
  `/ingest-video`, scheduled GitHub workflows. All planned for later
  phases (see `docs/architecture.md`).

## When generating code

- Type hints are mandatory (`ruff` rule ANN). `Any` is allowed.
- Tests must mock `MetaTrader5` via `tests/conftest.py` — never connect
  to a live terminal in unit tests.
- Imports order: stdlib → third-party → local. Ruff handles this.
- Branch names: `feat/<scope>`, `fix/<scope>`, `strat/<name>`,
  `ea/<name>`. Conventional commits.
- Never edit on `main` — the `branch-guard.sh` hook will block the tool.
