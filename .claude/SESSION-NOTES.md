# Session notes — momentum-candle project

Living checkpoint. Updated whenever a decision is made or a phase ships.
Read this at the start of any new session before deriving anything from scratch.

## Current state — 2026-05-18

### Tags & versions on origin/main

- `v0.2.0-python-mvp` — Python MCP MVP (8 tools, 16 tests passing)
- `bb8eee5` — MQL5 indicators compile clean (Video + Proxy + Backtest EA)
- `53c3786` — MomentumCandle_Visualizer indicator + docs

### Live evidence collected

1. **Live MT5 connection working** via opencode `.mcp.json`
   - InstaForex demo `94682256`, server `InstaForex-Server`, USD, leverage 1:1000
   - Filling mode auto-detect resolves to FOK on this account
2. **Eye-vs-algo walkthrough** of today's M5 (12 candidates examined)
   - 4 disagreements out of 12 (33%)
   - 2 misses by absolute size floor (algo too loose on small marubozu)
   - 1 miss by volume threshold (B: snap-back)
   - 1 miss by reversal context (I/V: 67% body, 25% wick — algo too strict)

Strategy-tester results explicitly out of scope per user direction. Focus
is the candle-classification function itself.

### Eye-model — extracted rules

User's mental classification function decomposes into 4 orthogonal rules:

1. **Geometric purity** — body ≥ 70%, close-side wick ≤ 10%
   - Reversal exception: body ≥ 60%, wick ≤ 25%
2. **Absolute size floor** — M5 XAUUSD: ≥ 20 pts (calibrated from today)
3. **Dominance / "left side empty"** — range > max(prior N same-direction ranges)
4. **Session filter** — Asia 23:00–08:00 UTC, NY 12:00–22:00 UTC; skip London chop

### Rules locked

- Session window: Asia 23-08 UTC + NY 12-22 UTC
- Absolute size floor (M5 XAUUSD): 20 pts default, calibrate later
- Dominance check: range > max(prior 5 same-direction ranges)
- Volume filter: deprioritized (false rejects on Bars B, J)
- 30-min hard time-stop: applied in EA + Python `place_market_order`

### Pending — needs more evidence

- Reversal-context detection: 4 hypotheses to test
  - **A** Pause-and-reject: bars within 0.6×ATR of swing high/low for 3+ bars
  - **B** Round-number rejection: distance to nearest 50 or 100 ≤ 5 pts
  - **C** Engulfing: open ≥ prior.close AND close < prior.low (SELL); mirror BUY
  - **D** Velocity-flip: rate_recent sign != rate_now sign AND |rate_now| ≥ 2 × |rate_recent|
- Best M5 size floor (20pt is hypothesis, needs cross-day validation)
- Per-timeframe floor (M15, H1) — untested

### 5-day candle dataset cached

- Source: `C:\Users\DELL\.local\share\opencode\tool-output\tool_e3c60fb800018NefI01GMfrDQg`
- 1500 M5 bars total
- Days covered:
  - Tue 2026-05-12  276 bars  range 135 pts (volatile)
  - Wed 2026-05-13  276 bars  range  57 pts (quiet)
  - Thu 2026-05-14  276 bars  range  74 pts (normal)
  - Fri 2026-05-15  276 bars  range 154 pts (volatile, top priority)
  - Mon 2026-05-18  248 bars  range 104 pts (today, partial)
- Eye-tagging order: **Fri 15 → Tue 12 → Mon 18 → Thu 14 → Wed 13**
- Density: top 50 candidates per day by composite score
- Eye-tag format: `<n> YES <pattern>` or `<n> NO <reason>`
  - Patterns: continuation, breakout, reversal
  - Bars not mentioned = skipped (not eye-flagged)

### Stats from current algo against the dataset

- 1,352 total bars across 5 days
- 508 candidates (body≥0.65 OR R5≥1.4 OR range≥18)
- Only 5 (0.37%) pass all 4 algo filters
- Only 5 pass the proposed 20-pt size floor
- Algo-pass and size-floor overlap on **just 1 bar** in 5 days (Fri 02:30 SELL)
  → Major eye-vs-algo gap: algo flags small marubozus, misses 20+pt bars on geometry

### Two-phase plan

```
Phase A — Eye-aligned momentum core (HOLD until eye-tag dataset complete)
  1. Add session filter to MQL5 + Python
  2. Add absolute size floor to MQL5 + Python
  3. Add dominance check (max prior N same-dir range) to MQL5 + Python
  4. Add 30-min hard time-stop to EA + Python place_market_order
  → Bump v0.3.0-eye-aligned

Phase B — Reversal exception (after Phase A + eye-tag dataset analysis)
  1. Compute correlation of 4 hypotheses against eye-tags
  2. Pick smallest set that explains ≥80% of YES with ≤10% false positives
  3. Encode reversal-context detector with body ≥ 60%, wick ≤ 25% relaxation
  → Bump v0.4.0-reversal

Strategy-tester optimizer phase explicitly DROPPED per user direction.
```

## Workflow rules

- **Hold all code changes** until eye-tag dataset across 5 days is collected and analyzed.
- **uv path on Windows:**
  `C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`
- **MetaEditor compile path:** `C:\Program Files\MetaTrader\MetaEditor64.exe`
- **MT5 terminal path:** `C:\Program Files\MetaTrader\terminal64.exe`
- **MT5 data folder:**
  `C:\Users\DELL\AppData\Roaming\MetaQuotes\Terminal\F762D69EEEA9B4430D7F17C82167C844`

## Composite score formula

Used to rank "interesting" candidates per day:

```
score = body_pct * 0.4
      + min(R5/3, 1.0) * 0.3
      + min(V5/3, 1.0) * 0.2
      + min(range/30, 1.0) * 0.1
```

R5 = range / mean(prior 5 ranges).  V5 = tick_volume / mean(prior 5 tick_volumes).

## Resume point

**Next step on `continue`:** deliver Fri 2026-05-15 candidate table for eye-tagging,
top 50 by composite score, both UTC and broker (UTC+2) timestamps. User replies with
`<n> YES <pattern>` per bar.

After all 5 days tagged: build correlation table, run hypothesis selection,
propose Phase A+B encoding.
