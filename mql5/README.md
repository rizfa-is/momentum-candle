# mql5/

MQL5 source for the momentum-candle indicators and the backtest harness.

| Path | Role |
|---|---|
| `Include/MomentumCandleCommon.mqh` | Shared enums, structs, indicators, classifier, scorer |
| `Indicators/MomentumCandle_Simple.mq5` | Minimal arrow-only indicator: body% + close-wick% + body in points (3 inputs, no baseline / no fib / no pattern) |
| `Indicators/MomentumCandle_Video.mq5` | Variant 1 — video-faithful (local-N range/volume) |
| `Indicators/MomentumCandle_Proxy.mq5` | Variant 2 — ATR(14) + SMA(20) proxy |
| `Indicators/MomentumCandle_Visualizer.mq5` | Visual aid — draws baseline + threshold whiskers per bar, top-left HUD with PASS/FAIL on each filter |
| `Indicators/ThreeSoldiersCrows.mq5` | Three White Soldiers (BUY) and Three Black Crows (SELL) classical pattern detector. Body%, wick%, optional body-points floor, strict/loose open mode, optional Asia+NY session filter, 0..1 strength score per pattern. |
| `Experts/MomentumCandleBacktest.mq5` | EA that reads either indicator's buffers and trades in the Strategy Tester |
| `Experts/MomentumCandle_OptimizedEA.mq5` | **Self-contained deployable EA**: 7-rule filter + pullback_236 entry + cap=1 + 30-min time-stop. 5-month backtest WR 72.5%, PF 1.54. See `../docs/deployment.md`. |

**Install + backtest walk-through:** see `../docs/mql5-indicators.md`.

## TL;DR

1. Copy `Include/MomentumCandleCommon.mqh` into your MT5 data folder
   under `MQL5/Include/`.
2. Copy each `.mq5` into the matching `MQL5/Indicators/` or
   `MQL5/Experts/` subfolder.
3. Open in MetaEditor (F4 from MT5), press F7 to compile.
4. Drop `MomentumCandle_Video` on a XAUUSD M15 chart. Add
   `MomentumCandle_Proxy` for side-by-side comparison.
5. Run `MomentumCandleBacktest` in **Strategy Tester** twice — once with
   `InpVariant=VIDEO`, once with `InpVariant=PROXY`. Compare reports.

## Why two indicators?

The Python detector (`src/mt5_mvp/strategies/momentum_candle.py`) uses
ATR(14) and SMA(20) as defensible-but-not-literal proxies for the
source video's "longer than recent candles" / "small small small
suddenly big" rules. The two MQL5 indicators let you measure, on real
broker data, whether that smoothing helps or hurts. Decide with
numbers, not opinions, before refactoring the Python side.
