---
description: Show MT5 account state — balance, equity, margin, open positions on the default symbol.
allowed-tools: mcp__mt5-mvp__get_account, mcp__mt5-mvp__get_positions, mcp__mt5-mvp__get_symbol_price
---

# /account-status

Use the MT5 MCP server to assemble a one-screen account snapshot for
the user. Symbol focus is XAUUSD unless `$ARGUMENTS` overrides it.

## Steps

1. Call `get_account` and capture: `balance`, `equity`, `profit`,
   `margin_free`, `margin_level`, `leverage`, `currency`, `trade_allowed`.
2. Call `get_positions` (no symbol filter). Note the count and total
   floating P/L.
3. Call `get_symbol_price` for the default symbol (XAUUSD or whatever
   `$ARGUMENTS` provided). Capture bid/ask/spread.
4. If any call returns `{"error": ...}`, stop and surface the error
   verbatim with one line of guidance ("Is the MT5 terminal running and
   logged in?").

## Output format

Plain text, no markdown headers needed. One section each:

```
Account 94682256 (InstaForex-Server)
  Currency: USD   Leverage: 1:500   Trade allowed: yes
  Balance: 100000.00   Equity: 100123.45   Free margin: 99800.00   Margin level: 12345%

XAUUSD price
  Bid 2350.10   Ask 2350.50   Spread 40 points

Open positions: 2 (P/L +123.45)
  #12345 BUY 0.01 @ 2348.20  SL 2340.00  TP 2360.00  +18.30
  #12346 BUY 0.05 @ 2349.10  SL 2340.00  TP 2362.00  +105.15
```

If there are no open positions, say so on a single line.

## Constraints

- Do NOT place, modify, or close any positions from this command.
- All numbers come from the MCP responses — no fabricated values.
- Round prices to two decimals for XAUUSD; use four decimals for
  FX symbols.
