# MQL5 Indicators — Momentum Candle (Video vs. Proxy)

Two MetaEditor indicators ship with this project so you can validate the
strategy directly in the MT5 Strategy Tester before promoting any change
to the Python detector. Both indicators share the same OHLCV scoring,
Fibonacci levels, and pattern classifier, but differ in how they answer
"is this candle bigger and louder than its neighbours?".

| File | Variant | Range filter | Volume filter |
|---|---|---|---|
| `MomentumCandle_Video.mq5` | **Video-faithful** | `range >= 1.5x mean(range, last 5)` | `tick_volume >= 1.5x mean(tick_volume, last 5)` |
| `MomentumCandle_Proxy.mq5` | ATR / SMA proxy | `range >= 1.0x ATR(14)` | `tick_volume >= 1.5x SMA(tick_volume, 20)` |
| `MomentumCandle_Visualizer.mq5` | Visual aid (no signals) | `same as Video` | `same as Video` |

Plus a backtest harness EA:

| File | Purpose |
|---|---|
| `MomentumCandleBacktest.mq5` | Reads either indicator's `Direction`/`Confidence` buffers via `iCustom` and opens market orders in the Strategy Tester. Tagged with magic number for clean run isolation. |

The two scoring indicators draw on the chart and expose four buffers
(`Buy`, `Sell`, `Direction`, `Confidence`). The EA only consumes
`Direction` and `Confidence` — pure mechanical execution. The
visualizer is read-only and exists to close the gap between what your
eye sees and what the algorithm decides.

## Visualizer — close the eye-vs-algorithm gap

`MomentumCandle_Visualizer.mq5` answers the question "why did the
algorithm reject this candle that I clearly see as a momentum bar?"

For every closed bar, it draws two horizontal "whiskers" centered on
the bar's midpoint:

- **Gray whisker** — width = `mean(range, last N)`. The local baseline.
  This is what "normal-sized" looks like right now.
- **Colored whisker** — width = `baseline x InpRangeMult`. The
  threshold the candle must exceed to pass the range filter.
  - **Lime** — bar passes all four filters.
  - **Gold** — bar passes 3 of 4 (borderline).
  - **Crimson** — bar fails 2 or more filters.

If the candle's high–low pokes outside the colored whisker on the
vertical axis, it cleared the range filter. If it sits inside, range
was insufficient.

A small text tag prints above each interesting bar (3+ filters pass)
showing per-filter PASS/FAIL flags and the actual numbers, e.g.
`BWRv 87% 1.8xR 1.4xV` (capital letter = pass, lowercase = fail).

A top-left **HUD** prints the same data live for the most recently
closed bar:

```
==== MC Visualizer ====
Inputs: N=5  body>=70%  wick<=10%  range>=1.50x  vol>=1.50x

Last closed bar (2026.05.18 15:00):  BULL  range=12.40
  body  =  82.0%   PASS  (need >= 70%)
  wick  =   6.0%   PASS  (need <= 10%)
  range =  1.62x   PASS  (need >= 1.50x)
  vol   =  1.31x   FAIL  (need >= 1.50x)

Verdict: BORDERLINE (3 of 4 passed)
  Failing: volume
```

That's the answer to "why was that candle rejected?" — explicit,
quantitative, and tied to the same five inputs the scoring indicators
use.

The visualizer is purely a learning / diagnostic tool. It writes no
signal buffers, never triggers an alert, never feeds the EA. Drag it
on the chart whenever you want to understand *why*; remove it when you
just want clean signals.

## Install on Windows

MetaEditor only loads code from inside the terminal's data folder. Find
the path from MT5: **File → Open Data Folder**. You will see a
`MQL5/` directory with subfolders.

Copy the project's `mql5/` files into the matching subfolders:

```text
<MT5 data folder>/
└── MQL5/
    ├── Include/
    │   └── MomentumCandleCommon.mqh           ← from this repo
    ├── Indicators/
    │   ├── MomentumCandle_Video.mq5           ← from this repo
    │   └── MomentumCandle_Proxy.mq5           ← from this repo
    └── Experts/
        └── MomentumCandleBacktest.mq5         ← from this repo
```

PowerShell helper (run from the project root):

```powershell
$src = "D:\CODING\Trading\mt5-mcp\momentum-candle\mql5"
$dst = "$env:APPDATA\MetaQuotes\Terminal\<TERMINAL_INSTANCE_ID>\MQL5"
# Replace <TERMINAL_INSTANCE_ID> with the long hex string under
# %APPDATA%\MetaQuotes\Terminal\ — usually one folder per MT5 install.

Copy-Item "$src\Include\MomentumCandleCommon.mqh"          "$dst\Include\"      -Force
Copy-Item "$src\Indicators\MomentumCandle_Video.mq5"       "$dst\Indicators\"   -Force
Copy-Item "$src\Indicators\MomentumCandle_Proxy.mq5"       "$dst\Indicators\"   -Force
Copy-Item "$src\Indicators\MomentumCandle_Visualizer.mq5"  "$dst\Indicators\"   -Force
Copy-Item "$src\Experts\MomentumCandleBacktest.mq5"        "$dst\Experts\"      -Force
```

Open MetaEditor (F4 from MT5), open each `.mq5` file, press **F7** to
compile. You should see "0 errors" in the toolbox. The compiled `.ex5`
files appear next to the source.

## Use on a chart

1. Open a XAUUSD chart, e.g. M15.
2. Drag `MomentumCandle_Video` from `Navigator → Indicators → Custom`.
3. Defaults are sensible. Click OK.
4. Closed candles that pass all filters get an arrow (lime up / red
   down) and dashed lines for entry / SL / TP1 / TP2, plus a label with
   confidence and metrics.
5. Drag `MomentumCandle_Proxy` onto the same chart for side-by-side
   comparison. Its arrows are aqua / magenta so you can tell them apart.
6. To get a popup on each new closed setup, set `InpAlertOnNew=true`.

The forming bar (shift 0) is always skipped. New signals appear when
the bar closes.

## Strategy Tester

The Strategy Tester scores actual trades, not raw signals — that's why
`MomentumCandleBacktest.mq5` exists.

### Step-by-step

1. **Tools → Strategy Tester** (or Ctrl+R).
2. **Expert**: select `MomentumCandleBacktest`.
3. **Symbol**: `XAUUSD` (or whatever you trade).
4. **Period**: `M15` (the source video's preferred timeframe).
5. **Date**: pick a meaningful range — at minimum 6 months. 2 years is
   better. InstaForex demo gives you a few years of history.
6. **Modelling**:
   - "Every tick based on real ticks" — most accurate, slow.
   - "1-minute OHLC" — fast, approximate fills.
   - "Open prices only" — useless here; the EA enters on next bar open
     so this would still partly work, but TP/SL hits are too coarse.
7. **Inputs tab**:
   - `InpVariant = VIDEO` for the first run, then re-run with `PROXY`.
   - `InpUseTp1 = true` to test the high-WR conservative target, or
     `false` for the 1.27 extension (TP2).
   - All other "Indicator parameters" must match the values you'd use
     when running the indicator standalone.
8. **Start**. Watch the journal for any "iCustom failed" messages — if
   you see them, the indicator path or its inputs are mismatched.

### Comparing variants

Run the same window twice — once `VARIANT_VIDEO`, once `VARIANT_PROXY`,
identical other inputs. Compare:

- **Trades**: count of setups that produced fills.
- **Win rate %**: hits TP vs hits SL.
- **Profit factor**: gross profit / gross loss.
- **Max drawdown %**: worst equity dip.
- **Average RR realised**: profit-per-trade / risk-per-trade.

Save the screenshots / `.htm` reports of both runs into `reports/` (the
folder is gitignored under `cache/`-style rules; create it if you want
to commit specific reports). The decision criteria:

- If the **video variant** produces **>=20% more trades and a similar
  or better win rate**, that's strong evidence the ATR/SMA proxy was
  too restrictive on local context. Refactor the Python detector.
- If the **proxy variant** produces fewer but cleaner trades with
  noticeably higher profit factor, the ATR/SMA filter is acting like a
  useful noise-reducer. Keep it but document the trade-off.
- If both variants score similarly, prefer the simpler one — the video
  variant — because it has fewer parameters to overfit.

### Pitfalls to watch

- **First N bars dead** — the Wilder ATR variant needs `period+1` bars
  before it can produce a value. Don't compare runs whose start dates
  span that warm-up window.
- **InstaForex demo data quality** — XAUUSD on this broker has visible
  weekend candles (Saturday 00:00–03:00 UTC). The backtest will trade
  on those. Real-money sims should pick a broker without weekend gold
  pricing or filter the EA by session.
- **One-position guard** — `InpOnlyOnePos=true` (default) means a
  signal during an open trade is dropped. Turning it off gives more
  trades but introduces correlation noise.
- **Slippage / spread** — the Strategy Tester uses the broker's typical
  spread for the run. XAUUSD on InstaForex demo runs ~80 points; real
  ECN brokers will be tighter. Don't extrapolate the win rate to a
  different broker without re-running.

## Reading the buffers from another EA

If you want to drive your own EA from these signals (e.g. add risk
sizing, multi-symbol, a different exit policy):

```mq5
int handle = iCustom(_Symbol, _Period, "MomentumCandle_Video",
                     /* … all 11 indicator inputs in declaration order */);

double dir[1], conf[1];
CopyBuffer(handle, 2, /*shift*/ 1, /*count*/ 1, dir);   // Direction buffer
CopyBuffer(handle, 3, /*shift*/ 1, /*count*/ 1, conf);  // Confidence buffer

if(dir[0] > 0 && conf[0] >= 0.6) { /* buy logic */ }
```

The four buffer indices are stable: `0=BUY plot`, `1=SELL plot`,
`2=Direction`, `3=Confidence`. The plot buffers are price-anchored
arrows; only `Direction` and `Confidence` are useful for programmatic
consumers.

## Why the side-by-side?

The owner of this project (correctly) flagged that the Python detector
deviates from the source video's text in two places:

1. **ATR(14)** instead of "longer than the previous few candles".
2. **SMA(20)** instead of "small, small, small, suddenly a big one".

Both deviations are defensible smoothing choices, but they are choices.
Without empirical evidence on which filter pair generates better trades
on real XAUUSD data, the question of "which version is the strategy"
stays academic. The two indicators plus the backtest EA convert that
question into a number.

## Out of scope

- **Multi-symbol scans** — the indicator is per-chart by design.
  iterate manually.
- **Optimisation passes** — the EA is structured so Strategy Tester's
  optimiser *can* sweep `InpRangeMult`, `InpVolMult`,
  `InpMinConfidence`, but the project doesn't ship preset configs.
- **News-event filters** — the EA trades through anything. Use
  `iEconomicCalendar` if you build that on top.
- **Trade-management evolution** — break-even moves, trailing stops,
  partial closes. Out of scope; left for a future EA built on top of
  the indicator buffers.
