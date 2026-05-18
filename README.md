# momentum-candle

> **MT5 MCP server + signal-automation toolkit**
> Strategy focus: **momentum-candle on XAUUSD**.
> AI agents (Claude, opencode) and downstream signal sources (Telegram, MQL5 EA)
> drive a MetaTrader 5 terminal through a small, safe set of tools.

## What this gives you

- An MCP server (`mt5-mvp`) that any MCP-compatible client can talk to.
- **8 tools**: `get_account`, `get_symbol_price`, `get_candles_latest`,
  `get_positions`, `place_market_order`, `modify_position`, `close_position`,
  `close_all_positions`.
- Two layers of trade safety: `MT5_DRY_RUN=1` by default, plus a
  `CONFIRM_LIVE` Claude hook that blocks live orders without explicit intent.
- Auto-detected filling mode (works on InstaForex demo out of the box).
- A `.claude/` directory with agents, commands, hooks, and skills tailored
  to MT5 + Python work.

## Prerequisites

| Need | Tested with |
|---|---|
| Windows 10/11 | required (MetaTrader5 lib is Windows-only) |
| MetaTrader 5 terminal, logged into a demo account | InstaForex-Server, demo `94682256` |
| Algorithmic trading enabled in MT5 | `Tools → Options → Expert Advisors → Allow algorithmic trading` |
| `uv` | 0.11+ — `winget install astral-sh.uv` |
| Python 3.12 | installed via `uv python install 3.12` |

## Install

```powershell
# Clone or open this folder, then:
uv sync

# Copy env template and fill in your demo credentials
copy .env.example .env
notepad .env       # set MT5_LOGIN / MT5_PASSWORD; keep MT5_DRY_RUN=1 for now
```

## Run the MCP server

```powershell
# stdio — for Claude Desktop / opencode (default)
uv run mt5-mvp

# remote SSE (for VPS scenarios)
uv run mt5-mvp --transport sse --host 127.0.0.1 --port 8765
```

## Wire to opencode / Claude Desktop

`.mcp.json` (committed) registers this server. opencode picks it up
automatically when run from the project root. For Claude Desktop, copy the
relevant block into `%APPDATA%\Claude\claude_desktop_config.json`.

## Smoke test

With MT5 open and logged in:

```powershell
uv run pytest                # unit tests, mocked MT5
uv run ruff check .          # lint
```

Then in opencode/Claude:

> `What's my account balance?`
> `Show me the last 30 H1 candles for XAUUSD.`
> `Place a 0.01 BUY on XAUUSD with SL 30 points away.`  # dry-run by default

## Going live (when ready)

1. Set `MT5_DRY_RUN=0` in `.env`.
2. Include the token `CONFIRM_LIVE` in the prompt that issues the trade.
3. The hook in `.claude/hooks/live-trade-guard.sh` blocks any destructive
   tool call that does not satisfy both conditions.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the layered design,
phase plan, and roadmap (Telegram listener, MQL5 EA bridge, YouTube
strategy ingestion, scheduled workflows).

## Project layout

```
src/mt5_mvp/         core + MCP server (8 tools)
tests/               pytest with mocked MetaTrader5
docs/                architecture + strategy notes
.claude/             agents, commands, hooks, skills, rules
.mcp.json            project-level MCP registration
.env.example         copy to .env, fill credentials
```

## License

MIT.
