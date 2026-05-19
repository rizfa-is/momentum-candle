# May 2026 -- optimized filter results

Comparison of the 8-rule optimized filter (from `may2026-takeaways.md`) vs the original 3-rule baseline filter on the same May 2026 dataset.

## Filter rules applied

```
body / range            >= 0.86         (was 0.80)
close-side wick / range <= 0.10
far-side wick / range   <= 0.05         (NEW)
body in price points    >= 1000         (was 800)
range in USD            >= 11.0         (NEW)
distance to nearest $50 in [0, 15] USD  (NEW: avoid donut zone)
session                 != London       (NEW: skip 8-12 UTC)
trend_monotonic_prior_7 <= 4            (NEW: skip exhausted trends)
```

## Headline comparison

```
                                  baseline       optimized       delta
────────────────────────────────────────────────────────────────────────
NEXT_OPEN entry
  signals fired                   72             10             -62
  filled                          72             10             -62
  TP2 hit                         53 (73.6%)     10 (100.0%)     +26.4pp
  SL hit                          19 (26.4%)      0 (0.0%)     -26.4pp
  Mean RR per win                 0.287          0.295           +0.008
  Net PnL                         -3.79 R        +2.95 R         +6.74 R
  Per-trade                       -0.053 R       +0.295 R        +0.348 R
  Profit factor                   0.80           inf            +inf
  Break-even WR                   77.7%          77.2%          -0.5pp

PULLBACK_236 entry
  signals fired                   72             10             -62
  filled                          65              9             -56
  TP2 hit                         43 (66.2%)      8 (88.9%)     +22.7pp
  SL hit                          22 (33.8%)      1 (11.1%)     -22.7pp
  Mean RR per win                 0.586          0.586           -0.000
  Net PnL                         +3.18 R        +3.68 R         +0.50 R
  Per-trade                       +0.049 R       +0.409 R        +0.360 R
  Profit factor                   1.14           4.68            +3.54
  Break-even WR                   63.1%          63.1%          -0.0pp
```

## Caveats

- **Overfit risk is real.** The same dataset was used to identify the filters and now to test them. Out-of-sample (April 2026 or earlier) is needed to confirm the lift survives.
- **Sample size shrinks** under the optimized filter. Wider confidence interval on the WR.
- **Spread cost still applies.** ~80-point InstaForex spread takes ~0.10R per pullback trade. Net real-money PF is roughly the reported PF minus 0.1.
- **Trade frequency matters.** A higher PF with fewer trades may not be commercially better than a lower PF with more trades; depends on capital deployment goals.

## Per-signal pass list

Signals that survive the optimized filter, with their actual outcomes:

```
  #  time UTC             side  sess    body%  fwick%  body_pt  range  dist50  next_op  pullbk 
--------------------------------------------------------------------------------------------------------------
  1  2026-05-06T01:50:00  BUY   Asia      96%      2%     1106  11.52    3.19  TP2      no-fill
  2  2026-05-07T19:20:00  BUY   NY        98%      2%     1142  11.65    5.56  TP2      SL     
  3  2026-05-08T17:05:00  SELL  NY        92%      0%     1347  14.61   10.44  TP2      TP2    
  4  2026-05-11T05:40:00  SELL  Asia      93%      1%     1046  11.23    1.48  TP2      TP2    
  5  2026-05-15T13:05:00  BUY   NY        88%      2%     1191  13.52    4.39  TP2      TP2    
  6  2026-05-18T03:55:00  BUY   Asia      96%      2%     2412  25.16    9.16  TP2      TP2    
  7  2026-05-18T14:35:00  BUY   NY       100%      0%     1386  13.86    8.82  TP2      TP2    
  8  2026-05-18T15:30:00  BUY   NY        95%      3%     1159  12.26    0.37  TP2      TP2    
  9  2026-05-19T16:00:00  SELL  NY        89%      1%     1367  15.32   13.26  TP2      TP2    
 10  2026-05-19T17:10:00  SELL  NY        96%      0%     1136  11.80    3.42  TP2      TP2    
```

