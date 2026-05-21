# Session notes — momentum-candle project

Living checkpoint. Loaded automatically via `opencode.json` at every
session start. Read this before deriving anything from scratch.

Last updated: 2026-05-21

## Current state — at-a-glance

```
main branch:                origin/main @ 043990b
deployable strategy tag:    v0.5.0-deployable
S/R toolset tag:            v0.6.0-sr-aware

Backtest verdict: v0.5.0 is the only strategy with multi-month edge.
Five backtest phases attempted; four rejected; one adopted.
Next step:        30-day demo forward-test of v0.5.0 OR more research.
```

## What works (deployed)

### v0.5.0 momentum-candle strategy

```
File:          mql5/Experts/MomentumCandle_OptimizedEA.mq5
Filter:        7-rule "optimized_no_round"
                 body% >= 0.86
                 close-wick% <= 0.10
                 far-wick% <= 0.05
                 body in points >= 1000   (10 USD on XAUUSD)
                 range >= 11 USD
                 session != London (skip 08-12 UTC)
                 trend_monotonic_prior_7 <= 4
Entry:         pullback_236  (limit at 23.6 fib retracement of signal candle)
Position cap:  1 (one trade at a time, magic-namespaced)
Time stop:     30-min hard exit
Risk:          1% account per trade (configurable)

5-month backtest (Jan-May 2026 M5 XAUUSD):
  189 trades, WR 72.5%, PF 1.54, mean RR/win 0.586
  +0.149 R per trade gross
  After ~80pt InstaForex spread: ~+0.05 R per trade net
  ~38 trades/month average, 1 losing month per 5 expected

Per-month stability:
  2026-01:  44t  WR 59%  PF 0.85   ← losing month
  2026-02:  42t  WR 74%  PF 1.65
  2026-03:  63t  WR 79%  PF 2.25
  2026-04:  30t  WR 70%  PF 1.37   ← OOS validation
  2026-05:  10t  WR 90%  PF 5.27   ← in-sample, lucky variance
```

Spec doc: `docs/deployment.md`
Strategy doc: `docs/strategies/momentum-candle.md`

## What's been rejected (do NOT re-litigate)

| Phase | Tested | Verdict |
|---|---|---|
| 3 | Add S/R confluence filter on top of v0.5.0 | REJECTED — hurts PF (1.54 → 1.22) |
| 4 | 3WS/3BC + S/R combined strategy, 6 variants | ALL 6 LOST money |
| 5 | Fade failed 3WS/3BC at S/R | HYPOTHESIS FALSIFIED, only 3 trades in 5 months |

Reports: `data/backtests/phase{3,4,5}-report.md`

These rejections are evidence-backed. **Don't re-test them without
fundamentally new approach** (different timeframe, different signal
class, etc).

Specifically, the May factor analysis "donut zone" finding
(`dist_to_round_50` rule) was confirmed as curve-fit by April OOS
and Phase 3. It's permanently dropped.

## Codebase map

```
src/mt5_mvp/                         Python MCP server (8 + 2 tools)
  client.py                            ensure_initialized
  account.py / market.py / trade.py    8 base tools
  strategies/
    momentum_candle.py                 scan_momentum_setups tool
    support_resistance.py              get_major_sr tool
  server.py                            FastMCP wiring
  cli.py                               --transport stdio|sse|http

mql5/                                 MQL5 indicators + EAs
  Include/MomentumCandleCommon.mqh    shared helpers
  Indicators/
    MomentumCandle_Simple.mq5          minimal 3-filter arrows
    MomentumCandle_Video.mq5           video-faithful local-N filters
    MomentumCandle_Proxy.mq5           ATR/SMA proxy variant
    MomentumCandle_Visualizer.mq5      baseline + threshold whiskers
    ThreeSoldiersCrows.mq5             3WS/3BC pattern, all toggles off
    MajorSupportResistance.mq5         S/R lines + zones, hot-cold tiers
  Experts/
    MomentumCandleBacktest.mq5         iCustom + market orders
    MomentumCandle_OptimizedEA.mq5  ★  THE DEPLOYABLE EA

tests/                               29 + 6 = 35 unit tests, all green
scripts/                             10 backtest + analysis scripts
data/
  eye-tags/                            5 days tagged by user, 16 YES / 134 NO
  backtests/                           5 phase reports + raw JSON
docs/
  architecture.md
  deployment.md                        v0.5.0 deployment guide
  strategies/momentum-candle.md
  strategies/support-resistance.md
  mql5-indicators.md
.claude/
  SESSION-NOTES.md                     this file
  skills/                              7 skills (mt5-python-api, fastmcp,
                                       trading-safety, momentum-candle,
                                       support-resistance, mql5-ea-patterns,
                                       pytest-mt5, uv-python-tooling)
  agents/, commands/, hooks/, rules/
```

## Eye-tag dataset (3 / 5 days tagged, model converged)

```
Days tagged:   3 (Fri 15 / Thu 14 / Mon 18)
YES tags:      16 (4 continuation, 4 breakout, 8 reversal)
NO tags:       134

Final eye-model:
  range >= 10 (M5 XAUUSD absolute floor)
  off-window 22-23 UTC reject
  reversal context (engulfing OR swing extreme):
    body >= 0.50 AND wick <= 0.37
  else (continuation/breakout):
    body >= 0.75 AND wick <= 0.15

Passes ALL 16 YES, rejects ALL 134 NO.
This model encodes how the user's eye classifies. The MARKET
backtest then refined this further into v0.5.0 (body 0.86, etc.).

KEY INSIGHT documented: eye and market disagree on engulfing context.
Eye-tag data: engulfing +1.3x lift on YES rate.
May backtest: engulfing -5.9pp drag on TP2 outcomes.
The eye predicts what looks significant; the market rewards what
follows through. Different questions.

Worksheets: data/eye-tags/2026-05-{12,13,14,15,18}-*.md
Status:     data/eye-tags/STATUS.md  (Tue 12 + Wed 13 deferred)
```

## MCP tools currently exposed

```
Read-only (8):
  get_account, get_symbol_price, get_candles_latest, get_positions,
  scan_momentum_setups, get_major_sr

Destructive (4):
  place_market_order, modify_position, close_position,
  close_all_positions

Wrapped by:  opencode.json registers mt5-mvp via uv.exe absolute path
Config:      .env (gitignored) holds InstaForex demo credentials
Safety:      MT5_DRY_RUN=1 default; CONFIRM_LIVE token required for
             live trades via .claude/hooks/live-trade-guard.sh
```

## Workflow rules

- **uv path on Windows:**
  `C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`
- **MetaEditor compile path:** `C:\Program Files\MetaTrader\MetaEditor64.exe`
- **MT5 terminal path:** `C:\Program Files\MetaTrader\terminal64.exe`
- **MT5 data folder:**
  `C:\Users\DELL\AppData\Roaming\MetaQuotes\Terminal\F762D69EEEA9B4430D7F17C82167C844`
- **Cached data files:**
  `cache/2026-{01,02,03,04,05}-m5.json` (5 months M5 XAUUSD, ~28k bars total, gitignored)
- **Cached candle dump from MCP:**
  `C:\Users\DELL\.local\share\opencode\tool-output\tool_e3c60fb800018NefI01GMfrDQg`
  (used for the eye-tag dataset; 1500 M5 bars)

## Critical decisions made (do not relitigate)

1. **Engulfing context is NOT a positive filter** despite eye-tag dataset suggesting it. Market backtest disagreed.
2. **Round-number proximity / "donut zone" was curve-fit on May.** Don't reintroduce `dist_to_round_50` rule.
3. **S/R confluence does NOT lift the optimized strategy.** Phase 3 verdict.
4. **3WS/3BC pattern lacks edge on M5 XAUUSD** (Phase 4) AND fading the pattern doesn't work either (Phase 5).
5. **One position at a time (cap=1) outperforms layered positions.** Phase 2.5 layered backtest.
6. **Pullback_236 entry > next-bar-open** for RR balance. Universal across phases.
7. **Volume filter (V5) is dead.** Across 5 months, V5 mean YES 1.27x vs NO 1.16x — no signal.

## Five-phase research summary

```
Phase 1 (May factor study)         12 features tested              extracted candidates
Phase 2 (5-month aggregate)        Jan-May 2026 OOS                v0.5.0 ADOPTED
Phase 3 (S/R confluence on v0.5)   sr_band, sr_confluence          REJECTED
Phase 4 (3WS/3BC + S/R)            6 variants × 5 months           ALL REJECTED
Phase 5 (fade failed 3WS/3BC)      3 fade variants                 REJECTED (n=3, no edge)

Healthy ratio: 1 win / 4 losses = we know what works AND what doesn't.
```

## Resume point — next session can pick from these

The strategy work has reached its honest endpoint. Continued
backtesting on M5 XAUUSD risks more curve-fits than real lifts.

Three options ranked by impact:

1. **30-day demo forward-test of `MomentumCandle_OptimizedEA`**
   on InstaForex demo. The EA is built, compiled, deployed.
   Real-fill conditions vs backtest assumptions is the only
   remaining unknown. Drag on a XAUUSD M5 chart, walk away,
   log daily. Decision after 30 days: real money or diagnose.

2. **Pull 2025 H2 data (Jul-Dec)** to extend OOS from 5 to 11
   months. ~10 min of compute via `scripts/pull_month.py`.
   Strengthens statistical case before any real money.

3. **Manual-trade logger MCP tool** (~80 LOC) — record user's
   manual trades alongside algo's, compare eye vs algo over
   the 30-day demo period. Builds the data for the next
   research cycle.

User's last conversation point (2026-05-21): philosophical
discussion about the gap between manual eye-trading and
algorithmic. Conclusion: both are needed, they encode different
slices of judgment, the algo is "math doing the bookkeeping for
an opinion the human had."

Recommended path: **(1) and (2) in parallel.** Demo runs
unattended; pull more data when convenient.

## Composite score formula (used in eye-tag worksheets)

```
score = body_pct * 0.4
      + min(R5/3, 1.0) * 0.3
      + min(V5/3, 1.0) * 0.2
      + min(range/30, 1.0) * 0.1
```

R5 = range / mean(prior 5 ranges).  V5 = tick_volume / mean(prior 5 tick_volumes).
