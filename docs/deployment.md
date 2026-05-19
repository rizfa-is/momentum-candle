# Deployment guide — MomentumCandle_OptimizedEA

The EA implements the deployable strategy from the 5-month backtest
study. It runs unattended on a single XAUUSD M5 chart and trades the
optimized 7-rule filter with a 23.6% pullback entry, 1.27 fib TP, and
a 30-minute hard time-stop. One position at a time.

## Backtest support (Jan-May 2026)

```
Filter:        optimized_no_round (7 rules)
Entry mode:    pullback_236 (limit at 23.6 retracement, 10-bar fill window)
Position cap:  1 (one trade at a time)
Time stop:     30 minutes hard exit

Aggregate (5 months, 189 trades):
  WR:           72.5%
  PF:           1.54
  Mean RR/win:  0.586
  Net:          +28.23 R
  Per trade:    +0.149 R gross / +0.05 R after ~80pt spread

Per-month stability (pullback_236 + optimized_no_round):
  2026-01: 44t, WR 59.1%, PF 0.85    <- losing month
  2026-02: 42t, WR 73.8%, PF 1.65
  2026-03: 63t, WR 79.4%, PF 2.25
  2026-04: 30t, WR 70.0%, PF 1.37
  2026-05: 10t, WR 90.0%, PF 5.27    <- in-sample, lucky
```

Trade frequency: ~38 trades per month average.

After spread costs on InstaForex demo (~80 points round-trip), expected
net per-trade is ~+0.05R. At 1% account risk per trade on $10k, that's
~$5/trade, ~$190/month, ~22% annualized at fixed risk.

**Realistic expectation, not a guarantee.** Live conditions may differ
from backtest assumptions (worst-case intra-bar SL ordering, no slippage
modeled, news events not filtered).

## Install

The `.mq5` file lives in this repo at `mql5/Experts/MomentumCandle_OptimizedEA.mq5`.
Copy to your MT5 data folder and compile:

```powershell
$src = "D:\CODING\Trading\mt5-mcp\momentum-candle\mql5"
$dst = "$env:APPDATA\MetaQuotes\Terminal\<TERMINAL_INSTANCE_ID>\MQL5"

Copy-Item "$src\Experts\MomentumCandle_OptimizedEA.mq5" "$dst\Experts\" -Force
```

Open MetaEditor (F4 from MT5), open the file, press **F7**. Should report
`0 errors, 0 warnings`.

## Configure

In MT5, drag the EA onto a XAUUSD M5 chart. The defaults match the
backtest exactly:

| Input | Default | Notes |
|---|---:|---|
| `InpMinBodyPct` | 0.86 | body / range threshold |
| `InpMaxCloseWickPct` | 0.10 | close-side wick cap |
| `InpMaxFarWickPct` | 0.05 | opposite-side wick cap |
| `InpMinBodyPoints` | 1000 | $10 body minimum on XAUUSD |
| `InpMinRangeUsd` | 11.0 | candle range floor |
| `InpUseSessionFilter` | true | skip London 08-12 UTC |
| `InpMaxMonotonic` | 4 | skip mature trends |
| `InpPullbackBars` | 10 | wait up to 10 bars for limit fill |
| `InpMaxHoldMinutes` | 30 | hard time-stop |
| `InpRiskPercent` | 1.0 | % equity risked per trade (0 = fixed lot) |
| `InpFixedLot` | 0.10 | fallback when risk% = 0 |
| `InpMaxLotSize` | 1.00 | hard ceiling on calculated lot |
| `InpMagic` | 920001 | order magic number |
| `InpDebugLog` | false | turn on for verbose journal |

**Allow algorithmic trading**: `Tools → Options → Expert Advisors →
Allow algorithmic trading` (checkbox must be on).

**On the chart**: enable AutoTrading button on the toolbar, then drag
the EA. The "smiley face" should turn green in the top-right of the
chart.

## Run order — recommended sequence

### 1. Strategy Tester first (60 minutes)

Verify the EA reproduces the expected backtest numbers before any live
ticks:

1. **Tools → Strategy Tester** (`Ctrl+R`)
2. **Expert**: `MomentumCandle_OptimizedEA`
3. **Symbol**: `XAUUSD`
4. **Period**: `M5`
5. **Date**: 2026-04-01 to 2026-04-30 (April only)
6. **Modelling**: `Every tick based on real ticks`
7. Run. Compare to expected April-OOS:
   - 30 trades expected (~5% slack acceptable)
   - WR 70% expected (60-75% acceptable)
   - PF 1.37 expected (1.0-1.6 acceptable)

If results match, EA logic is sound. If results diverge significantly,
debug before live trading.

### 2. Demo forward-test (30 days minimum)

Attach the EA to a live XAUUSD M5 chart on your InstaForex demo. Let
it run for 30 calendar days (~22 trading days). Each evening, log:

- Number of trades that day
- Wins / losses
- Notable issues (rejected orders, slippage, etc.)

After 30 days:
- **Live WR ≥ 65% AND PF ≥ 1.2** → ship to small real money
- **Live WR 55-65% OR PF 1.0-1.2** → keep on demo, investigate
- **Live WR < 55% OR PF < 1.0** → backtest didn't generalize, stop and
  diagnose

### 3. Real money with reduced size

Start at half the calculated lot size or `InpRiskPercent = 0.5` for the
first 30 trades. Confirm the broker's behavior on real fills, slippage,
and stop placement matches the demo. Scale up only after.

## What the EA does and doesn't do

### Does
- Evaluates the closed M5 bar each new bar (once per bar)
- Filters using all 7 rules from the optimized backtest
- Arms a limit order at the 23.6% retracement
- Fills the limit on a live tick when price touches it
- Cancels the limit if not filled within 10 bars
- Places SL and TP at the broker
- Force-closes positions older than 30 minutes
- Logs to journal when `InpDebugLog = true`

### Doesn't
- Trail stops (TP is hard target, SL is hard stop)
- Move SL to break-even after partial movement
- Scale into positions (one cap=1 trade only)
- Take opposite-direction trades while one is open
- Filter news events (no economic calendar awareness)
- Adjust for spread automatically (uses raw broker prices)
- Trade other symbols or timeframes

## Risk model

The EA computes lot size to risk `InpRiskPercent` of account balance per
trade, calculated from the entry-to-SL distance:

```
risk_money = balance × InpRiskPercent / 100
money_per_lot = (sl_distance / tick_size) × tick_value
lots = risk_money / money_per_lot
```

Capped at `InpMaxLotSize` (default 1.0 lot).

If `InpRiskPercent = 0` it uses `InpFixedLot` instead (default 0.10).

## Sanity checks the EA performs

- Refuses if SL or TP is closer than `SYMBOL_TRADE_STOPS_LEVEL` from
  current price (broker minimum stop distance)
- Refuses if calculated lot is less than `SYMBOL_VOLUME_MIN`
- Floors lot to `SYMBOL_VOLUME_STEP`
- Aborts the pullback fill if a position is somehow already open

## Known limitations

1. **Time-stop uses position open-time.** A 30-minute clock starts
   when the trade fills. If the limit fills 10 bars after the signal,
   the time-stop only counts from the fill, not from the signal candle.

2. **Limit-pullback can miss a fast-moving signal.** If price gaps past
   the 23.6 retracement without a tick at that level, no fill happens.
   This was modeled in the backtest as a 9.7% miss rate — included in
   the WR/PF numbers.

3. **Worst-case backtest ordering.** The backtest counts SL hits
   pessimistically when a bar's high and low both cross SL and TP.
   Real-money fills with tick data may resolve some of these to TP.
   Live PF is likely slightly higher than backtest PF.

4. **Single symbol.** Don't run the same EA on multiple charts unless
   you change `InpMagic` per chart — they'll fight over the position
   cap.

## Files

```
mql5/Experts/MomentumCandle_OptimizedEA.mq5    EA source
docs/deployment.md                              this file
data/backtests/multi-month-summary.md           5-month aggregate
data/backtests/oos-validation.md                April OOS validation
data/backtests/may2026-takeaways.md             factor study
```

## Roadmap (post-deployment)

After 30 days of demo confirms the strategy:

1. **Real money** — small position size, monitor closely
2. **Pull 2025 historical** — extend OOS test from 5 months to 17 months
3. **Telegram listener** — broadcast EA's signals to a channel for
   manual cross-confirmation or community trading
4. **Multi-symbol** — test optimized filter on EURUSD, GBPUSD on M5
5. **Multi-timeframe** — test on M15 and H1 with adjusted thresholds
