---
name: momentum-candle
description: Momentum-candle strategy on XAUUSD. Use when discussing setups, scanning gold for trade ideas, body% / ATR / volume filters, Fibonacci-based SL/TP, breakout/pullback/trend patterns, or anything in src/mt5_mvp/strategies/.
---

# Momentum-Candle Strategy

Source: Indonesian masterclass video https://www.youtube.com/watch?v=Utj8qRwNtgE
Full spec: `docs/strategies/momentum-candle.md`.
Implementation: `src/mt5_mvp/strategies/momentum_candle.py`.
MCP tool: `scan_momentum_setups(symbol="XAUUSD", timeframe="M15", ...)`.

## Trigger — when a candle qualifies

All four must hold on a *closed* candle:

| Filter | Default | Why |
|---|---|---|
| body / range | ≥ 70% | strong directional pressure |
| close-side wick / range | ≤ 10% | close near the extreme |
| range / ATR(14) | ≥ 1.0× | range expansion vs recent vol |
| tick_volume / SMA(20) | ≥ 1.5× | volume confirms intent |

Direction: `BUY` if close > open, else `SELL`.
The current forming bar is **always excluded** (its close is provisional).

## Three patterns (priority order)

1. **breakout** — prior 5 bars in a tight range (avg range ≤ 1.2× ATR), momentum candle closes beyond it. Highest confidence.
2. **trend** — at least 5 of prior 10 closes monotonic in the trade direction, momentum candle's close is a 5-bar extreme.
3. **pullback** — momentum candle's low (BUY) or high (SELL) near a recent 10-bar swing point within 0.382× ATR.

Detector picks the strongest matching pattern. If none match, defaults to `pullback` with weakest confidence weight.

## Fibonacci levels (BUY example with low=L, high=H)

```
range = H − L
sl  = L − 0.10 × range          (cushion below low)
tp1 = H                          (the candle high — high WR)
tp2 = H + 0.27 × range           (1.27 extension — aggressive)
entry (next_open):    next bar's open price
entry (pullback_236): H − 0.236 × range  (limit order)
```

SELL is mirror: `sl = H + 0.10×range`, `tp1 = L`, `tp2 = L − 0.27×range`.

## Confidence scoring (0..1)

```
score = 0.30 × body_score
      + 0.30 × range_score
      + 0.20 × volume_score
      + 0.10 × pattern_score   (1.0 breakout, 0.7 trend, 0.5 pullback)
      + 0.10 × wick_score
```

Each component clipped to [0, 1] using the headroom above its threshold. Default `min_confidence = 0.50`. Strong setups score ≥ 0.70.

## Anti-patterns (from the source video)

- **FOMO entries on normal-sized candles** — filter must pass.
- **Tight stops** — author insists on cushion (`0.10 × range` below low).
- **Multi-timeframe spaghetti** — pick one timeframe (M15 default, M5 faster).
- **Ignoring context** — body% alone is not enough; volume + ATR matter.

## Calling the tool from a chat

> "Any momentum setups on XAUUSD M15?"

The agent calls:

```
scan_momentum_setups("XAUUSD", "M15", lookback=200)
```

Returns newest-first list of setup dicts with `entry`, `sl`, `tp1`, `tp2`, `rr_tp1`, `rr_tp2`, `confidence`, `reason`. To execute one:

```
place_market_order(symbol, direction, volume=0.01, sl=setup["sl"], tp=setup["tp1"], comment="mt5-mvp/momentum:<id>")
```

(Defaults to dry-run; live needs `MT5_DRY_RUN=0` AND `CONFIRM_LIVE` in the prompt.)

## When to relax the defaults

- **Low-volatility session (Asia)** — spreads widen, fewer setups; lower `vol_mult` to 1.2.
- **News-driven session** — keep defaults, expect higher rejection rate.
- **Backtesting** — set `min_confidence=0.0` to see the full output and inspect false positives.

## Out of scope

- Auto-execution loops.
- Fake-out invalidation (price returning to range after breakout).
- Multi-symbol scans — call once per symbol.
- Alternative fib levels (38.2, 50, 61.8) — currently only 23.6 and 1.27 are used per the source video.
