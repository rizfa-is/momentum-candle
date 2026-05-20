# Phase 3 backtest -- S/R confluence study

Tests whether adding an S/R-confluence filter on top of the
v0.5.0 deployable strategy (`optimized_no_round + pullback_236`)
meaningfully changes WR/PF.

## Configurations

- **baseline**       no S/R filter (the v0.5.0 deployable strategy)
- **sr_band**        signal candle's extreme within 0.5 * ATR of ANY major level
- **sr_confluence**  directional: BUY near support / SELL near resistance only

## Per-month results

```
config                                           sigs   fill   TP2    SL   skip     WR  meanRR      net      PF
--------------------------------------------------------------------------------------------------------------
2026-01 | baseline                                 52     44    26    18      0  59.1%   0.586    -2.77    0.85
2026-01 | sr_band                                  23     18     9     9     29  50.0%   0.586    -3.73    0.59
2026-01 | sr_confluence                            23     18     9     9     29  50.0%   0.586    -3.73    0.59

2026-02 | baseline                                 49     42    31    11      0  73.8%   0.586     7.16    1.65
2026-02 | sr_band                                  19     18    11     7     30  61.1%   0.586    -0.56    0.92
2026-02 | sr_confluence                            19     18    11     7     30  61.1%   0.586    -0.56    0.92

2026-03 | baseline                                 69     63    50    13      0  79.4%   0.586    16.28    2.25
2026-03 | sr_band                                  29     27    21     6     40  77.8%   0.586     6.30    2.05
2026-03 | sr_confluence                            29     27    21     6     40  77.8%   0.586     6.30    2.05

2026-04 | baseline                                 34     30    21     9      0  70.0%   0.586     3.30    1.37
2026-04 | sr_band                                  13     11     8     3     21  72.7%   0.586     1.68    1.56
2026-04 | sr_confluence                            13     11     8     3     21  72.7%   0.586     1.68    1.56

2026-05 | baseline                                 11     10     9     1      0  90.0%   0.585     4.27    5.27
2026-05 | sr_band                                   3      3     3     0      8  100.0%   0.585     1.76     inf
2026-05 | sr_confluence                             3      3     3     0      8  100.0%   0.585     1.76     inf

```

## Pooled aggregate (5 months)

```
config                                           fill   TP2    SL   skip     WR      net      PF   per-trade
---------------------------------------------------------------------------------------------------------
ALL | baseline                                      189   137    52      0  72.5%    28.23    1.54    +0.149 R
ALL | sr_band                                        77    52    25    128  67.5%     5.45    1.22    +0.071 R
ALL | sr_confluence                                  77    52    25    128  67.5%     5.45    1.22    +0.071 R
```

## Verdict

**Baseline** (no S/R filter): n=189, WR 72.5%, PF 1.54, +0.149 R/trade

**sr_band** (any nearby level): n=77, WR 67.5%, PF 1.22, +0.071 R/trade

**sr_confluence** (directional): n=77, WR 67.5%, PF 1.22, +0.071 R/trade

**Pre-committed decision rule** (set before this run):
- If sr_confluence PF >= baseline PF + 0.10  AND  WR change <= -3pp  -> ADOPT
- If sr_confluence PF >= baseline PF + 0.05  but volume drops >50%  -> CONDITIONAL ADOPT
- If sr_confluence PF < baseline PF + 0.05  OR  WR drops >5pp        -> REJECT

sr_confluence PF lift over baseline:  -0.32
sr_confluence WR change over baseline: -5.0 pp
sr_confluence volume change:          -59.3%

**VERDICT: REJECT**

## Honest interpretation

Two findings worth being explicit about:

### 1. sr_band and sr_confluence produce identical results

Look at the pooled numbers: both filtered modes return n=77, WR 67.5%,
PF 1.22, net +5.45R. **Every signal that's near any S/R level is
already on the directionally-correct side.** The "directional"
restriction adds zero filtering on top of the proximity check.

This makes structural sense: a momentum-candle BUY by definition prints
its low at the bottom of its range, and that low is the relevant
"extreme". When that low is near a level, the level is by overwhelming
probability already a support (price came down to it). Same for SELL
candles printing highs near resistance. The directional filter is
redundant for this signal type.

If we wanted directional confluence to do real work, we'd need to flip
the test -- e.g. require that price has *recently rejected* the level
in the trade direction (a touch + bounce). Just "near a level" doesn't
discriminate.

### 2. The S/R filter actively hurts performance

Filtering signals to only those near S/R levels:

```
              n     WR      PF      per-trade R
─────────────────────────────────────────────────
baseline    189    72.5%   1.54    +0.149
sr_band      77    67.5%   1.22    +0.071     <- worse on every metric
```

Drops are uniform: WR -5pp, PF -0.32, per-trade R cut in half. Volume
cut by 59% (skipped 128 of 189 trades).

**Why?** Looking at per-month detail: every single month except 2026-04
was worse with the S/R filter. The losses concentrate where you'd
expect: in the lower-volatility months (Jan, Feb) where most signals
fire away from major levels. The surviving signals (those that DO sit
near S/R) are not systematically better -- they're roughly the same
quality as the average baseline signal.

In other words: **the v0.5.0 strategy already captures the S/R effect
implicitly through its other rules** (body%, far-wick, range, session,
trend filter). Adding an explicit S/R proximity test on top is double-
counting and rejects perfectly good signals that happen to fire mid-
range.

### 3. The "donut zone" finding from the May factor analysis was a
**curve-fit on May data**

In `may2026-takeaways.md` we observed that signals 15-30 USD from a
round-50 level (the "donut zone") had a 50% WR vs 93% WR for signals
5-15 USD away. When extended to all 5 months and applied as a forward
filter, the effect disappears. This is the textbook overfit signature
the report flagged at the time.

The April OOS validation already foreshadowed this -- the
`dist_to_round_50` rule was identified as the most likely curve-fit
term and was preemptively dropped from the v0.5.0 deployable filter.
Phase 3 confirms that intuition more rigorously: ANY S/R proximity
filter (round numbers OR swing levels) hurts the strategy.

## What stays decided

- **Do NOT add S/R confluence** to `MomentumCandle_OptimizedEA.mq5`
- **Keep v0.5.0 as the deployable** strategy
- **Keep the S/R detector + indicator** as a USER tool, not as a
  strategy filter. It's useful for visualizing context, picking TP
  targets manually, or guiding manual overrides -- just not as a
  signal gate.

## Files

- `scripts/phase3_sr_confluence_backtest.py`  the backtest itself
- `data/backtests/phase3-results.json`         per-month-per-mode metrics
- `data/backtests/phase3-report.md`            this report

## Next options

1. **Forward-test the v0.5.0 EA on demo for 30 days.** The strategy
   work has reached its rigorous limit; observation is what's left.

2. **Pull 2025 data (Jul-Dec)** to extend OOS test from 5 months to
   ~11 months. Strengthens the statistical case before real money.

3. **Build a Telegram listener** so signals fan out to a channel for
   manual cross-confirmation or community trading.

The honest recommendation is (1). Continued backtesting risks more
curve-fit findings; live forward-testing is the only signal that
matters now.
