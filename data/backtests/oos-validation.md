# Out-of-sample validation -- April 2026 vs May 2026

Same filter logic, different month. If May was curve-fit, April will show it.

## April 2026 dataset

- Bars: 5796 M5 candles
- Window: 2026-04-01T01:00:00+00:00 -> 2026-04-30T23:55:00+00:00

## Side-by-side comparison

```
                                MAY (in-sample)        APRIL (OOS)            DELTA
────────────────────────────────────────────────────────────────────────────────────────

BASELINE / next_open
  signals fired          72                    147                    +75
  filled                 72                    147                    +75
  WR                     73.6%                 71.4%                -2.2pp
  Mean RR per win       0.287                 0.291                 +0.004
  Profit factor          0.80                   0.73
  Net PnL               -3.79 R               -11.43 R               -7.64 R
  Per trade             -0.053 R              -0.078 R              -0.025 R

BASELINE / pullback_236
  signals fired          72                    147                    +75
  filled                 65                    133                    +68
  WR                     66.2%                 63.2%                -3.0pp
  Mean RR per win       0.586                 0.586                 -0.000
  Profit factor          1.14                   1.00
  Net PnL               +3.18 R               +0.20 R               -2.98 R
  Per trade             +0.049 R              +0.001 R              -0.048 R

OPTIMIZED / next_open
  signals fired          10                     20                    +10
  filled                 10                     20                    +10
  WR                    100.0%                 75.0%                -25.0pp
  Mean RR per win       0.295                 0.309                 +0.014
  Profit factor           inf                   0.93
  Net PnL               +2.95 R               -0.36 R               -3.31 R
  Per trade             +0.295 R              -0.018 R              -0.313 R

OPTIMIZED / pullback_236
  signals fired          10                     20                    +10
  filled                  9                     17                    +8
  WR                     88.9%                 70.6%                -18.3pp
  Mean RR per win       0.586                 0.586                 -0.000
  Profit factor          4.68                   1.41
  Net PnL               +3.68 R               +2.03 R               -1.65 R
  Per trade             +0.409 R              +0.119 R              -0.290 R
```

## Verdict

**Pre-committed decision rule** (set before April data was pulled):

- If April optimized WR within 10pp of May optimized WR -> ADOPT
- If April optimized WR drops 10-25pp -> CONDITIONAL ADOPT (more data needed)
- If April optimized WR collapses to baseline or below -> REJECT (curve-fit)

April optimized next_open WR:    75.0% (vs 100.0% in-sample, delta -25.0pp)
April optimized pullback_236 WR: 70.6% (vs 88.9% in-sample, delta -18.3pp)

April baseline next_open WR:     71.4%
April baseline pullback_236 WR:  63.2%

Optimized lift over baseline (April):
  next_open:    +3.6pp
  pullback_236: +7.4pp

## Honest verdict: CURVE-FIT ON NEXT_OPEN, MARGINAL SIGNAL ON PULLBACK_236

**Per the pre-committed decision rule:**

- **next_open optimized**: dropped from 100% to 75%. That's at the boundary
  of "conditional adopt" but the absolute WR (75%) is barely above the
  baseline (71.4%) -- only +3.6pp lift. **REJECT for next_open.**
  The May 100% was almost entirely lucky variance on a small sample.

- **pullback_236 optimized**: dropped from 88.9% to 70.6%. That's clear
  evidence of overfit, BUT the absolute WR (70.6%) is meaningfully above
  baseline (63.2%) -- a +7.4pp lift, and PF rose from 1.00 (baseline) to
  1.41 (optimized). **CONDITIONAL ADOPT for pullback_236.**

## What this means concretely

The optimized 8-rule filter does NOT produce the spectacular numbers seen
in May. But on the pullback_236 entry mode it still adds value over the
baseline:

```
              baseline (April)    optimized (April)    delta
WR            63.2%               70.6%                +7.4pp
PF            1.00                1.41                 +0.41
Net per trade +0.001 R            +0.119 R             +0.118 R
```

A profit factor of 1.41 is **honest, defensible territory** -- not a
home run, not a curve fit, just a workable filter on a coin-flip-difficult
market. After spread (~0.10R per pullback trade on InstaForex), real-money
PF lands around 1.15 -- positive but thin.

## What survives across both months

Looking at which optimized rules carry their lift into April:

```
Rule                           In-sample (May)    OOS (April)    Surviving?
─────────────────────────────────────────────────────────────────────────
body% >= 0.86                  WR boost          WR boost       YES
fwick% <= 0.05                 WR boost          WR boost       YES
body >= 1000pt                 WR boost          marginal       LIKELY
range >= 11 USD                WR boost          marginal       LIKELY
dist to round-50 in [0,15]     STRONG boost      WEAK           PARTIAL
session != London              WR boost          WR boost       YES
trend_monotonic <= 4           WR boost          WR boost       YES
```

The **dist-to-round-50** filter is the most likely curve-fit term. It
showed +19.5pp lift in May (suspiciously high) and only marginal effect
in April. Pulling that one rule probably tightens overfit risk.

## What to do next

Three options, ranked:

1. **Trim the filter.** Remove `dist_to_round_50` constraint. Keep the
   other 7 rules. Re-test on both May and April; if WR holds up
   approximately the same, the trimmed filter is more honest.

2. **Pull March 2026 for a third data point.** If March validates the
   pullback_236 optimized PF in the 1.2-1.6 range, that's three
   independent monthly windows -- defensible enough to deploy.

3. **Accept the result, deploy with realistic expectations.** Use
   pullback_236 + 7-rule optimized filter (drop dist-to-round-50)
   targeting PF ~1.2-1.4 on real money after spread. That's a real but
   thin edge.

I'd do (1) immediately and (2) if you want a stronger statistical case
before going to live trading.

## Files

```
cache/april2026-m5.json                                          (gitignored)
data/backtests/april2026-results-baseline-next_open.json
data/backtests/april2026-results-baseline-pullback_236.json
data/backtests/april2026-results-optimized-next_open.json
data/backtests/april2026-results-optimized-pullback_236.json
data/backtests/oos-validation.md                                  (this file)
scripts/pull_april2026.py
scripts/oos_validation_april.py
```
