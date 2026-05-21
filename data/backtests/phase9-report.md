# Phase 9 backtest -- AMD (LSD) + FVG only

Tests whether FVG (Fair Value Gap) confluence lifts the AMD/LSD signal
above the deployment threshold. Phase 6 had LSD raw at break-even
(+0.66R / 12 months); Phase 8 confirmed that on 29 months. This phase
adds two FVG variants (FVGC = displacement creates FVG; FVGE = entry
inside unfilled FVG) and includes a strict-timing control variant (V6).

## Result: REJECTED — V2's apparent edge was look-ahead bias

```
V    config                              n     WR    PF      netR     losM/active   verdict
─────────────────────────────────────────────────────────────────────────────────────────────
V1   LSD raw                          440   63.9%  1.04   +5.57R    13/29           REJECT
V2   LSD + FVGC (idx+1 entry)         263   73.8%  1.65  +44.62R     7/29           CAVEATED *
V3   LSD + FVGE                         0     -      -      -                       REJECT
V4   LSD + FVGC + FVGE                  0     -      -      -                       REJECT
V5   LSD + FVGC + 1.5R fixed TP       263   41.1%  1.05   +8.00R    18/29           REJECT
V6   LSD + FVGC strict (idx+2 entry)  244   64.8%  1.08   +6.53R    14/29           REJECT
```

* V2 looks like edge but uses bar `idx+1` data to arm a limit *on bar idx+1*.
  The FVG isn't confirmed until `idx+1` closes. **V6 is the live-realistic
  version of V2** and shows no edge.

## The look-ahead bias explained

The FVGC filter requires inspecting bar `idx+1` to confirm the gap:

```
Bullish FVG at idx+1: candles[idx+1].low > candles[idx-1].high
```

V2 was checking this at `idx+1` close AND simultaneously arming a pullback
limit *starting on bar idx+1*. In real-time deployment:

```
Time          Live behavior                  V2 (with bias)
─────────────────────────────────────────────────────────────
idx close    LSD signal fires                LSD signal fires
idx+1        bar still forming                arms pullback limit immediately
idx+1 close  FVG confirmed; can act now       (already waiting for fill)
idx+2        first valid entry bar            already filled at idx+1 maybe
```

V6 enforces correct timing: pullback fill window starts at `idx+2`. The
filter still fires (289 signals match FVGC, same as V2), but moving entry
one bar later drops:

```
WR:    73.8% → 64.8%  (-9.0 pp)
PF:    1.65  → 1.08  (-0.57)
netR: +44.62R → +6.53R
losing months: 7 → 14
```

**The edge was entirely in the entry timing, not in the FVG filter.** Trades
that would fill at `idx+1` (because price moved into the limit fast)
disproportionately won. By `idx+2`, the favorable price action has already
happened or moved away.

## Per-variant detail

(See `phase9-results.json` for raw numbers per month.)

## Why the diagnostic split was misleading

A separate run split LSD raw trades into "kept by FVGC" (V2's 263) and
"dropped by FVGC" (177). Kept won 73.8%, dropped won 49.2%.

That correlation is real — but it's not a usable filter. The split is
based on whether bar `idx+1` happens to form an FVG, which we can only
know after `idx+1` closes. The kept/dropped distinction is therefore
a *retrospective* classification, not a *prospective* signal.

The 24-point WR gap reflects the fact that bars that gap in the trade
direction at `idx+1` are favoring the trade. But that's a description
of price already moving in our favor, not a way to select trades in
advance.

## Why FVGE returned zero hits

The FVGE filter looks for an unfilled FVG within 50 bars before the LSD
signal where the pullback entry price falls inside the gap.

Diagnostic:
```
FVGs found in 50-bar window before LSD signals: 5,194
LSD signals with raw zone overlap (no fill check):   92  (~20%)
LSD signals passing FVGE (with fill check):           0
```

FVGs near LSD signals exist, but every one is already filled by the time
the displacement bar prints. Physically: London sweep + NY displacement
together produce violent directional moves that close any nearby gaps.

## Honest verdict

**Phase 9 REJECTED.** LSD raw is break-even (PF 1.04). LSD+FVGC strict
timing is no better (PF 1.08). The `idx+1`-entry variant V2 looked like
edge but was a look-ahead artifact.

This is the cleanest negative result in the project. The strict-timing
control caught a bias that would have surfaced as live underperformance.
**The pre-committed rules + strict-timing variant prevented us from
deploying a non-existent strategy.**

## What stays decided

- v0.5.0 momentum-candle remains the only strategy with multi-month edge
- 3 confirmations / 6 rejections (Phase 9 added)
- ICT/AMD on M5 XAUUSD continues to lack deployable edge
- Strategy diversification via ICT signals: not available

## Files

- `scripts/phase9_amd_fvg_backtest.py` — backtest script with V6 control
- `scripts/phase9_diag.py` — kept/dropped diagnostic
- `scripts/phase9_compare_v05.py` — calendar overlap analysis (V2 numbers, look-ahead biased; preserved for the negative-result documentation)
- `data/backtests/phase9-results.json`
- `data/backtests/phase9-report.md` — this file

## What this taught us

The discipline that mattered:
1. **Pre-committed thresholds** — same n≥50, PF>1.40, losing_months<=7/29 used since Phase 6
2. **Strict-timing control variant** — V6 added explicitly to test V2 for look-ahead
3. **Diagnostic split test** — confirmed FVGC correlates with outcome but doesn't filter prospectively

The discipline to apply going forward:
- For any signal that requires inspecting bar `idx+k`, the next entry bar is `idx+k+1`, not `idx+k`
- Whenever a confluence filter shows large WR lift on entry-bar data, run a strict variant before believing the result
- Correlation between filter and outcome is not the same as a usable filter
