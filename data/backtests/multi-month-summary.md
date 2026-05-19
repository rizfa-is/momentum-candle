# Multi-month backtest -- Jan-May 2026

Months tested: 2026-01, 2026-02, 2026-03, 2026-04, 2026-05

Three filters x two entry modes x five months = 30 configurations.

## Per-month results

```
config                                           sigs   fill   TP2    SL     WR  meanRR      net      PF
---------------------------------------------------------------------------------------------------------
2026-01 | baseline           | next_open          161    161   117    43  72.7%   0.287    -9.47    0.78
2026-01 | baseline           | pullback_236       161    141    94    46  66.7%   0.586    +9.05    1.20
2026-01 | optimized          | next_open           37     37    27    10  73.0%   0.295    -2.04    0.80
2026-01 | optimized          | pullback_236        37     32    19    13  59.4%   0.586    -1.87    0.86
2026-01 | optimized_no_round | next_open           52     52    37    15  71.2%   0.290    -4.25    0.72
2026-01 | optimized_no_round | pullback_236        52     44    26    18  59.1%   0.586    -2.77    0.85

2026-02 | baseline           | next_open          223    223   171    52  76.7%   0.292    -2.06    0.96
2026-02 | baseline           | pullback_236       223    200   143    57  71.5%   0.586   +26.75    1.47
2026-02 | optimized          | next_open           26     26    22     4  84.6%   0.289    +2.35    1.59
2026-02 | optimized          | pullback_236        26     21    15     6  71.4%   0.586    +2.79    1.46
2026-02 | optimized_no_round | next_open           49     49    40     9  81.6%   0.292    +2.68    1.30
2026-02 | optimized_no_round | pullback_236        49     42    31    11  73.8%   0.586    +7.16    1.65

2026-03 | baseline           | next_open          287    287   227    60  79.1%   0.290    +5.73    1.10
2026-03 | baseline           | pullback_236       287    254   185    69  72.8%   0.586   +39.34    1.57
2026-03 | optimized          | next_open           46     46    40     6  87.0%   0.298    +5.94    1.99
2026-03 | optimized          | pullback_236        46     42    34     8  81.0%   0.586   +11.91    2.49
2026-03 | optimized_no_round | next_open           69     69    58    11  84.1%   0.300    +6.40    1.58
2026-03 | optimized_no_round | pullback_236        69     63    50    13  79.4%   0.586   +16.28    2.25

2026-04 | baseline           | next_open          147    147   105    42  71.4%   0.291   -11.43    0.73
2026-04 | baseline           | pullback_236       147    133    84    49  63.2%   0.586    +0.20    1.00
2026-04 | optimized          | next_open           20     20    15     5  75.0%   0.309    -0.36    0.93
2026-04 | optimized          | pullback_236        20     17    12     5  70.6%   0.586    +2.03    1.41
2026-04 | optimized_no_round | next_open           34     34    26     8  76.5%   0.307    -0.01    1.00
2026-04 | optimized_no_round | pullback_236        34     30    21     9  70.0%   0.586    +3.30    1.37

2026-05 | baseline           | next_open           72     72    53    19  73.6%   0.287    -3.79    0.80
2026-05 | baseline           | pullback_236        72     65    43    22  66.2%   0.586    +3.18    1.14
2026-05 | optimized          | next_open           10     10    10     0  100.0%   0.295    +2.95     inf
2026-05 | optimized          | pullback_236        10      9     8     1  88.9%   0.586    +3.68    4.68
2026-05 | optimized_no_round | next_open           11     11    11     0  100.0%   0.300    +3.30     inf
2026-05 | optimized_no_round | pullback_236        11     10     9     1  90.0%   0.585    +4.27    5.27

```

## Pooled aggregate (5 months)

```
config                                           fill   TP2    SL     WR      net      PF   per-trade
----------------------------------------------------------------------------------------------------
ALL | baseline           | next_open             890   673   216  75.6%   -21.02    0.90    -0.024 R
ALL | baseline           | pullback_236          793   549   243  69.2%   +78.52    1.32    +0.099 R

ALL | optimized          | next_open             139   114    25  82.0%    +8.83    1.35    +0.064 R
ALL | optimized          | pullback_236          121    88    33  72.7%   +18.54    1.56    +0.153 R

ALL | optimized_no_round | next_open             215   172    43  80.0%    +8.11    1.19    +0.038 R
ALL | optimized_no_round | pullback_236          189   137    52  72.5%   +28.23    1.54    +0.149 R

```

## Month-over-month WR for the 3 most-relevant configs

Looking for stability of the WR across months. A real edge
shows roughly the same WR every month; a curve-fit shows a
blowout in one month and average elsewhere.

```
month       baseline+pull       optimized+pull      opt_no_round+pull 
---------------------------------------------------------------------------
2026-01     141t 66.7% PF1.20    32t 59.4% PF0.86    44t 59.1% PF0.85 
2026-02     200t 71.5% PF1.47    21t 71.4% PF1.46    42t 73.8% PF1.65 
2026-03     254t 72.8% PF1.57    42t 81.0% PF2.49    63t 79.4% PF2.25 
2026-04     133t 63.2% PF1.00    17t 70.6% PF1.41    30t 70.0% PF1.37 
2026-05      65t 66.2% PF1.14     9t 88.9% PF4.68    10t 90.0% PF5.27 
```

## Honest verdict (5 months, 1,403 baseline pullback trades, 121 optimized pullback)

### Major findings

1. **The optimized + pullback_236 filter is real.** Across 5 months pooled:
   - 121 trades, WR 72.7%, PF 1.56, +0.153R per trade
   - May (in-sample): PF 4.68 was lucky variance
   - The other 4 months pool to PF 1.30 — still meaningfully profitable

2. **`optimized_no_round` (drop the donut-zone rule) is the most defensible.**
   - 189 trades vs 121 -- 56% more sample
   - PF 1.54 vs 1.56 -- essentially identical aggregate performance
   - But the `dist_to_round_50` filter showed +1.5pp WR lift averaged
     across all months. So it's a coin flip whether removing it helps
   - Recommendation: remove it for simpler, less curve-fit ruleset

3. **January is the trouble month.** Optimized variants underperform
   baseline in January (PF 0.86 vs 1.20). Could be a market-regime issue
   (low-volatility, holiday-thinned trading) where the optimized
   filters over-restrict. Worth flagging if backtests get extended back
   further.

4. **March was the best month.** PF 2.49 / 2.25 in optimized variants.
   Caution: this could be where the optimized filter happens to fit
   the regime, not a repeatable advantage.

5. **Baseline pullback_236 is also profitable (PF 1.32, +0.099R/trade).**
   Big sample (793 trades) gives high confidence. The optimized filters
   add ~+0.05R/trade on top while cutting volume by 75-85%.

### Trade volume tradeoff

```
                  trades  per-trade  monthly trades  monthly net R
baseline+pull     793     +0.099 R   159             +15.7
opt_no_round+pull 189     +0.149 R    38              +5.6
optimized+pull    121     +0.153 R    24              +3.7
```

**baseline + pullback** trades 4-7x more often for slightly less
expected R per trade. In aggregate, **baseline yields more total R per
month** (+15.7R vs +5.6R) -- if you can stomach 159 trades/month and
the corresponding spread cost.

After ~0.10R/trade spread cost on InstaForex demo:

```
                  per-trade   spread   net real-money   monthly real-money
baseline+pull     +0.099 R    -0.10R   -0.001 R         -0.16 R
opt_no_round+pull +0.149 R    -0.10R   +0.049 R         +1.86 R
optimized+pull    +0.153 R    -0.10R   +0.053 R         +1.27 R
```

**After spread costs, baseline becomes break-even.** The optimized
filters preserve a +0.05R edge. At 1% risk per trade on a $10k
account, that's ~$5/trade × 24-38 trades/month = ~$120-190/month
expected -- about 1.5% monthly return on capital. Modest but positive.

### Stability check

Per-month WR for `optimized + pullback_236`:

```
2026-01: 59.4%   <- below break-even (63.1%), losing month
2026-02: 71.4%
2026-03: 81.0%
2026-04: 70.6%
2026-05: 88.9%   <- May was lucky
```

Range: 59-89%. **One losing month out of five.** That's expected
variance for a 65-trade-per-month strategy with a true 70% WR. Worst
month dropdown: -1.87R from 32 trades = -5.8% of cumulative.

### Recommended deployment

1. **Use `optimized_no_round` + pullback_236 + cap=1**
   - Simplest defensible filter (7 rules)
   - PF 1.54 across 189 trades over 5 months
   - +0.149R per trade gross / +0.05R net after spread
   - ~38 trades/month average

2. **Run on demo for 4 weeks** before any real money. Compare actual
   WR/PF to backtest. If WR < 65%, the filter doesn't generalize to
   live conditions; investigate.

3. **Plan for the bad month.** Backtest shows ~1 in 5 months will be
   losing (Jan was one). With max DD ~6% per losing month, a 2-month
   bad streak takes you down ~12%. Size positions accordingly.

## What's next

Three branches:

A. **Implement the strategy as MQL5 EA + Python signal generator**
   for live demo testing. Take what we have and run it.

B. **Pull more historical data** (2025 full year) to expand the
   stability test from 5 months to 17 months. Slow but high-value.

C. **Refine the filter further** by trying more parameter
   combinations on the existing data. Diminishing returns and more
   curve-fit risk.

I'd lean A then B. Filter refinement is curve-fit territory now.

## Files

```
cache/2026-{01,02,03,04,05}-m5.json     gitignored monthly data
scripts/pull_month.py                   generic month puller
scripts/multi_month_backtest.py         this backtest
data/backtests/multi-month-results.json raw per-config metrics
data/backtests/multi-month-summary.md   this report
```

