---
name: mql5-ea-patterns
description: MQL5 indicator and Expert Advisor patterns used by the momentum-candle project. Use when editing files under mql5/, debugging .mq5 compile errors, wiring iCustom buffers, working with CTrade, or backtesting in the Strategy Tester.
---

# MQL5 patterns for this project

## Repo layout

```
mql5/
├── Include/MomentumCandleCommon.mqh   shared helpers (TR, ATR, SMA, Setup, scoring, classifier)
├── Indicators/
│   ├── MomentumCandle_Video.mq5       video-faithful filters (local-N range/volume)
│   └── MomentumCandle_Proxy.mq5       ATR(14) + SMA(20) variant
└── Experts/
    └── MomentumCandleBacktest.mq5     reads either indicator's buffers, opens trades
```

Files have to land in the MT5 terminal's data folder (`File → Open Data Folder`) under `MQL5/Include`, `MQL5/Indicators`, `MQL5/Experts`. See `docs/mql5-indicators.md` for the copy commands and full Strategy Tester walk-through.

## Compile cycle

1. Edit the `.mq5` or `.mqh` in the repo.
2. Copy to the MT5 data folder (PowerShell snippet in `docs/mql5-indicators.md`).
3. Open in MetaEditor (`F4` from MT5).
4. Press `F7`. Goal: "0 errors, 0 warnings".
5. Reload chart / restart Strategy Tester to pick up the new `.ex5`.

## Indicator fundamentals (what we use)

- `#property indicator_chart_window` — overlay on the price chart (where setups belong).
- 4 buffers: `Buy`, `Sell`, `Direction`, `Confidence`. The first two are price-anchored arrow plots, the second two are calculation buffers exposed through `iCustom`.
- `ArraySetAsSeries` everywhere — index 0 is the newest bar. The shared helpers in `MomentumCandleCommon.mqh` assume this orientation.
- The forming bar (`shift=0`) is **never** evaluated. We always start at `shift=1`.

## Wilder ATR pitfall

`MathAbs(high[i] - close[i+1])` and `MathAbs(low[i] - close[i+1])` need the *previous* close — easy to off-by-one when arrays are series-indexed. The helper `MC_TrueRange(prev_close, high, low)` keeps that explicit.

Wilder smoothing seed = simple mean of TR over the first `period` bars; subsequent smoothing is `atr = (atr*(period-1) + tr) / period`. The helper `MC_WilderATR(...)` gives the value at any `shift`, returns 0 when there's not enough history.

## Reading buffers from an EA

```mq5
int h = iCustom(_Symbol, _Period, "MomentumCandle_Video",
                /* every input in declaration order */);

double dir[1], conf[1];
CopyBuffer(h, 2, /*shift*/ 1, /*count*/ 1, dir);
CopyBuffer(h, 3, 1, 1, conf);

if(dir[0] != 0 && conf[0] >= 0.5) { /* trade */ }
```

Buffer indices are part of the indicator's API. **Don't reorder** the `SetIndexBuffer` calls; doing so silently breaks every consumer EA.

## CTrade conventions

- `g_trade.SetExpertMagicNumber(magic)` once in `OnInit`.
- `g_trade.SetTypeFilling(ORDER_FILLING_FOK)` — InstaForex demo demands FOK or IOC; Buy/Sell go through.
- `g_trade.Buy(lot, _Symbol, ask, sl, tp, comment)` — pass `ask` explicitly so the EA logs the price it tried.
- Always check `SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(_Symbol, SYMBOL_POINT)` and reject SL/TP closer than that distance — broker rejects otherwise.
- Normalise volume against `SYMBOL_VOLUME_MIN`, `_MAX`, `_STEP`. `MathFloor(lot/step)*step` truncates instead of rounding up — safer.

## Once-per-bar guard

```mq5
const datetime t1 = iTime(_Symbol, _Period, 1);
if(t1 == 0 || t1 == g_last_seen_bar) return;
g_last_seen_bar = t1;
```

Use this at the top of `OnTick` for any signal-on-close strategy. Without it the EA spams entries during the live bar.

## Strategy Tester gotchas

- "Every tick based on real ticks" is the only realistic mode for SL/TP-driven strategies. Open-prices-only mode treats SL/TP as hits even if price never traded there.
- Match every indicator input on the EA's "Indicator parameters" group. Mismatches cause the indicator to compute different setups than the EA expects, but no error is raised.
- The Tester runs the indicator inside its own VM — the chart-side indicator is unaffected. Console output goes to the **Journal** tab, not the chart's experts log.

## Forbidden in this project

- Hard-coded paths inside `.mq5` files. Anything broker-specific belongs in inputs.
- Non-magic trades (no orders without an `Expert Magic`).
- Trade execution on the forming bar (`shift=0`).
- Touching `Comment()`, `Print()`, `Alert()` in tight inner loops — they kill tester throughput. Aggregate first.

## When extending

- **New filter** → add to `MomentumCandleCommon.mqh` and call from both indicators (and the Python detector). Keep them aligned or document the divergence.
- **New pattern** → extend `MC_Pattern` enum; update `MC_ClassifyPattern` and the confidence scorer's `pattern_score`.
- **Different exit policy** → don't fork the indicator; add a new EA that consumes the same buffers and applies its own exits.
