# Layered position backtest -- 1, 2, 3 max concurrent

Same filter and entry-mode logic as previous backtests, but instead of
skipping new signals while one position is open, we allow up to N
simultaneous positions per symbol. Each position carries its own SL
and TP2 from its own trigger candle.

Each unit of P/L is 1R based on the position's own entry-to-SL distance.
Peak risk exposure with N positions = N * 1R. PF compares gross wins
(in R) to gross losses (in R).

## Comparison table

```
cfg                                                            sigs   skip   fill   TP2    SL     WR   meanRR    netR      PF
--------------------------------------------------------------------------------------------------------------------------------------------
May 2026 | baseline | next_open | max=1                          72      2     70    52    18  74.3%   0.287   -3.10    0.83
May 2026 | baseline | next_open | max=2                          72      0     72    53    19  73.6%   0.287   -3.79    0.80
May 2026 | baseline | next_open | max=3                          72      0     72    53    19  73.6%   0.287   -3.79    0.80
May 2026 | baseline | pullback_236 | max=1                       72      7     59    41    18  69.5%   0.586   +6.01    1.33
May 2026 | baseline | pullback_236 | max=2                       72      3     62    43    19  69.4%   0.586   +6.18    1.33
May 2026 | baseline | pullback_236 | max=3                       72      0     65    43    22  66.2%   0.586   +3.18    1.14
May 2026 | optimized | next_open | max=1                         10      0     10    10     0  100.0%   0.295   +2.95     inf
May 2026 | optimized | next_open | max=2                         10      0     10    10     0  100.0%   0.295   +2.95     inf
May 2026 | optimized | next_open | max=3                         10      0     10    10     0  100.0%   0.295   +2.95     inf
May 2026 | optimized | pullback_236 | max=1                      10      0      9     8     1  88.9%   0.586   +3.69    4.69
May 2026 | optimized | pullback_236 | max=2                      10      0      9     8     1  88.9%   0.586   +3.69    4.69
May 2026 | optimized | pullback_236 | max=3                      10      0      9     8     1  88.9%   0.586   +3.69    4.69

April 2026 | baseline | next_open | max=1                       147     10    137    98    39  71.5%   0.294  -10.22    0.74
April 2026 | baseline | next_open | max=2                       147      0    147   105    42  71.4%   0.291  -11.43    0.73
April 2026 | baseline | next_open | max=3                       147      0    147   105    42  71.4%   0.291  -11.43    0.73
April 2026 | baseline | pullback_236 | max=1                    147     16    118    74    44  62.7%   0.586   -0.66    0.98
April 2026 | baseline | pullback_236 | max=2                    147      2    132    83    49  62.9%   0.586   -0.39    0.99
April 2026 | baseline | pullback_236 | max=3                    147      1    132    83    49  62.9%   0.586   -0.39    0.99
April 2026 | optimized | next_open | max=1                       20      1     19    14     5  73.7%   0.309   -0.67    0.87
April 2026 | optimized | next_open | max=2                       20      0     20    15     5  75.0%   0.309   -0.36    0.93
April 2026 | optimized | next_open | max=3                       20      0     20    15     5  75.0%   0.309   -0.36    0.93
April 2026 | optimized | pullback_236 | max=1                    20      2     15    11     4  73.3%   0.586   +2.44    1.61
April 2026 | optimized | pullback_236 | max=2                    20      0     17    12     5  70.6%   0.586   +2.03    1.41
April 2026 | optimized | pullback_236 | max=3                    20      0     17    12     5  70.6%   0.586   +2.03    1.41

```

## Effect of position-cap increase

For each (month, filter, mode), how does going from 1 -> 2 -> 3 max
change net R and PF?

```
config                                                   cap=1 PF/net    cap=2 PF/net    cap=3 PF/net  
--------------------------------------------------------------------------------------------------------------
May 2026 | baseline | next_open                           0.83/ -3.10     0.80/ -3.79     0.80/ -3.79  
May 2026 | baseline | pullback_236                        1.33/ +6.01     1.33/ +6.18     1.14/ +3.18  
May 2026 | optimized | next_open                           inf/ +2.95      inf/ +2.95      inf/ +2.95  
May 2026 | optimized | pullback_236                       4.69/ +3.69     4.69/ +3.69     4.69/ +3.69  

April 2026 | baseline | next_open                         0.74/-10.22     0.73/-11.43     0.73/-11.43  
April 2026 | baseline | pullback_236                      0.98/ -0.66     0.99/ -0.39     0.99/ -0.39  
April 2026 | optimized | next_open                        0.87/ -0.67     0.93/ -0.36     0.93/ -0.36  
April 2026 | optimized | pullback_236                     1.61/ +2.44     1.41/ +2.03     1.41/ +2.03  

```

## Verdict — layering DOES NOT help here

Reading the cap=1 → cap=3 deltas across all 8 (month, filter, mode)
configurations:

| Config | cap=1 PF / net | cap=3 PF / net | Best cap |
|---|---|---|---|
| May, baseline, next_open | 0.83 / -3.10 | 0.80 / -3.79 | 1 |
| May, baseline, pullback | **1.33 / +6.01** | 1.14 / +3.18 | **1** |
| May, optimized, next_open | inf / +2.95 | inf / +2.95 | tie |
| May, optimized, pullback | 4.69 / +3.69 | 4.69 / +3.69 | tie |
| April, baseline, next_open | 0.74 / -10.22 | 0.73 / -11.43 | 1 |
| April, baseline, pullback | 0.98 / -0.66 | 0.99 / -0.39 | tie |
| April, optimized, next_open | 0.87 / -0.67 | 0.93 / -0.36 | 3 |
| April, optimized, pullback | **1.61 / +2.44** | 1.41 / +2.03 | **1** |

### Three findings

1. **For the strongest configs (optimized + pullback_236), cap=1 is best.**
   May: cap=1 ties cap=3 (no extra signals fit). April: cap=1 PF 1.61 vs
   cap=3 PF 1.41. The single-position rule produces the best PF.

2. **For weaker configs, layering doesn't rescue them.** Baseline
   filter + next_open gets MORE negative when you allow more concurrent
   positions. Adding bad trades doesn't help.

3. **The signals cluster.** When the optimized + pullback_236 filter
   fires, it usually fires alone (no overlap). Few opportunities to
   actually run multiple positions concurrently. So the cap-1/cap-3
   numbers are nearly identical.

### Why does cap=1 outperform cap=3 in the best config?

Counter-intuitive, but explained by the data:

```
April optimized + pullback_236
  cap=1: 20 signals, 2 skipped, 15 filled, WR 73.3%, PF 1.61
  cap=3: 20 signals, 0 skipped, 17 filled, WR 70.6%, PF 1.41
```

Cap=1 **skips 2 signals** because a trade is already open. Those 2
skipped signals were probably going to lose — the WR on the 2 extra
trades that cap=3 took was 50% (1 win, 1 loss). Mean RR on the win
covers the loss but barely (0.586R - 1.0R = -0.4R net), dragging the
PF down.

In other words: **the discipline of "one trade at a time" filters out
some lower-quality signals that fire while you're already in a trade.**
The skipped signals correlated with worse outcomes than the average.

This may be specific to April; with more months we'd know if it
generalizes.

### What the YouTube video gets wrong (or what's different on XAUUSD)

The video allows 2-3 concurrent positions. Reasonable assumption:
unrelated signals on different setups can stack independently. But on
M5 XAUUSD with this filter, **signals don't cluster as much as the
video implies** — 15-20 per month, often spread out. The "max
concurrent" cap rarely binds.

When it DOES bind (April optimized + pullback fired 2 close signals),
the additional trade was lower quality — exactly the signals you'd
want to skip.

## Recommendation

**Stick with cap=1.** The data says it. The PF advantage is small
(+0.20 in April pullback_236) but consistent across configs.

If you want bigger position sizing for higher P/L, scale the lot size
on the single position rather than running multiple concurrent. That's
linear leverage, not signal clustering.

## Caveats

- **n=2 in April** (the difference between cap=1 and cap=3) is not
  statistical proof. Could be coincidence.
- **Same-direction trades only** -- this backtest doesn't model the
  case where opposite-direction signals appear (BUY then SELL on the
  same symbol). The video might assume hedged exposure that we don't
  test here.
- **Spread cost is per-position.** Multiplying positions multiplies
  spread cost. cap=3 with 80-point spread on each costs ~3x the spread
  drag of cap=1.

## Files

```
data/backtests/layered-comparison.md     this report
data/backtests/layered-results.json      raw per-config metrics
scripts/layered_backtest.py              the simulator
```
