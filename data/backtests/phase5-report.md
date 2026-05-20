# Phase 5 backtest -- FADE failed 3WS/3BC at major S/R

Phase 4 found 3WS at support has WR 21% on 1.27-extension targets;
3BC at resistance was similar. Hypothesis: market makers run liquidity
sweeps below obvious support before letting price continue. The failure
itself is the signal -- fade it instead of trade it.

## Strategy

```
1. Detect 3WS at major support (Phase 4's `sr_at_level` filter)
2. Wait FAILURE_WINDOW=3 bars for failure: close < anchor - 0.10*ATR
3. SHORT the breakdown:
   SL = pattern_high + 0.20*ATR  (above the bull thesis's strongest point)
   TP = next major support below (or fixed 2R for the *_2r variant)
4. Mirror for 3BC at resistance: failure = close above anchor; LONG
```

## Three variants

| Variant | Entry | TP target |
|---|---|---|
| `fade_market` | next-bar open after failure bar | next major level |
| `fade_retest` | limit at the broken anchor (price retest) | next major level |
| `fade_2r` | next-bar open after failure bar | fixed 2R |

## Pooled aggregate (Jan-May 2026)

```
variant         detect   qual   fail%     n      WR   meanRR      PF      net    per-tr
--------------------------------------------------------------------------------------------------------------
fade_market         72     32   12.5%     3   33.3%    0.260    0.13    -1.74    -0.580
fade_retest         72     32   12.5%     3   33.3%    0.307    0.15    -1.69    -0.564
fade_2r             72     32   12.5%     3   33.3%    2.000    1.00     0.00    +0.000
```

Column key:
- detect: total 3WS+3BC patterns detected
- qual: patterns at a major S/R level (anchor found)
- fail%: % of qualified patterns that failed within 3 bars
- n: filled fade trades
- WR: win rate of the fade

## Per-month detail

```
config                        detect   qual   fail     n      WR      PF      net
------------------------------------------------------------------------------------------
2026-01 | fade_market         21      9      1     1    0.0%    0.00    -1.00
2026-01 | fade_retest         21      9      1     1    0.0%    0.00    -1.00
2026-01 | fade_2r             21      9      1     1    0.0%    0.00    -1.00

2026-02 | fade_market         17      7      2     1    0.0%    0.00    -1.00
2026-02 | fade_retest         17      7      2     1    0.0%    0.00    -1.00
2026-02 | fade_2r             17      7      2     1    0.0%    0.00    -1.00

2026-03 | fade_market         16      6      0     0    0.0%    0.00     0.00
2026-03 | fade_retest         16      6      0     0    0.0%    0.00     0.00
2026-03 | fade_2r             16      6      0     0    0.0%    0.00     0.00

2026-04 | fade_market         12      6      1     1  100.0%     inf     0.26
2026-04 | fade_retest         12      6      1     1  100.0%     inf     0.31
2026-04 | fade_2r             12      6      1     1  100.0%     inf     2.00

2026-05 | fade_market          6      4      0     0    0.0%    0.00     0.00
2026-05 | fade_retest          6      4      0     0    0.0%    0.00     0.00
2026-05 | fade_2r              6      4      0     0    0.0%    0.00     0.00

```

## Honest verdict: HYPOTHESIS FALSIFIED

The fade hypothesis was: "3WS at support fails 80% of the time per Phase 4, so fading the failure should have edge."

The data refutes the premise that motivated this experiment.

### Finding 1: Patterns don't fail nearly as often as Phase 4 implied

```
                                Phase 4              Phase 5 (this run)
qualified at S/R                    29 (sr_at_level)         32
WR on 1.27 target                   20.7%                     n/a
failure rate (close beyond anchor)  ~80% (assumed)            12.5% actual
```

**Phase 4 measured "did the trade reach 1.27 extension."** Phase 5 measures "did the bar close beyond the anchor on the wrong side." These are very different.

A 3WS at support can:
- Fail to reach 1.27 extension (the Phase 4 loss): WR ~21%
- Actually break the support level (close below it): only **12.5%** of the time

So most of Phase 4's losses weren't "support broke." They were **stuck in the middle** -- the rally stalled, ground sideways, and stopped out at the pattern low without ever cleanly breaking the support. That's not a fadable structure -- there's no clear failure signal to trigger from.

### Finding 2: Sample size is the killer

12.5% failure rate × 32 qualified patterns = **only 4 actual failures across 5 months** (one ended up rejected for other reasons; we got 3 trades).

```
n_filled across all 5 months: 3 trades
WR: 33.3% (= 1 win out of 3)
```

You cannot deploy a strategy that fires 3 times in 5 months. The 95% confidence interval on WR with n=3 is roughly [1%, 91%]. **The data tells us nothing.**

### Finding 3: fade_2r breaks even on 3 trades by sheer luck

```
fade_2r: 1 win at +2.0R, 2 losses at -1.0R each = 0.0R net
```

The single winning trade was the April fade. With more data this could go any direction. The 2R variant is mathematically attractive (33% WR × 2R = +0.33R minus 67% × 1R = -0.34R, basically break-even by design) but with 3 trades it's noise.

## Why the original Phase 4 theory was wrong

I claimed "stop hunters sweep below support before letting price continue." That was an inference from the 21% WR on 1.27 target. The actual failure rate in this dataset is 12.5% -- patterns at support mostly DON'T break, they just fail to extend.

What's actually happening: 3WS at major support is not a high-quality reversal signal at all on M5 XAUUSD. It's a coin flip on whether price extends or stalls. The high Phase 4 SL hit rate was driven by **stalled trades drifting back to pattern_low**, not by clean rejections at the level.

This is more boring than "stop hunting" but more accurate. The pattern simply lacks edge on this timeframe and symbol.

## What stays decided

- **Fade failed 3WS/3BC: REJECTED** (insufficient signal frequency, no statistical evidence of edge)
- **Phase 4's 3WS/3BC variants: still rejected** (Phase 4 stands)
- **v0.5.0 momentum-candle: remains the deployable strategy** -- the only thing in this codebase with multi-month evidence of edge

## What this experiment cost

About 30 minutes of code + 1 minute of compute. Worth doing because:
1. The hypothesis was specific and falsifiable
2. The result tells us 3WS/3BC isn't fadable either, closing the loop on this signal
3. We learned WHY Phase 4 failed (stalled drifts, not clean breakdowns) which is more useful than the original theory

## What's next

Five backtest phases now confirm: **the v0.5.0 momentum-candle filter is the only thing here with edge.** Continued backtesting at the same M5 XAUUSD level is increasingly likely to surface noise, not real lifts.

Three honest options:

1. **30-day demo forward-test of v0.5.0** — start the live observation phase
2. **Pull 2025 H2 data** to extend OOS to 11 months, then demo
3. **Different research direction** — Telegram listener, multi-symbol expansion, or H1 timeframe study

Pick one or all (1) and (2) in parallel.
