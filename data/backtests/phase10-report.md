# Phase 10 backtest -- MTF (H1 trend bias + M5 setup)

Tests user request: "capture downtrend in H1, then wait M5 setup for sell
confirmation" (and mirror for buy).

H1 trend definition (locked before running):
  Downtrend if BOTH:
    1. Last 3 H1 closes are each lower than the previous H1 close
    2. Current H1 close is below EMA(10) of H1 closes
  Uptrend: mirror.

Strict-timing safeguard (Phase 9 lesson applied):
  When an M5 candle closes at time T, only H1 bars whose close time + 1 minute
  is before T are eligible for trend evaluation. Prevents the EA from peeking
  at an in-progress H1 bar.

Pre-committed decision rules:
  1. n_filled         >= 50 across 29 months
  2. PF                >  1.40
  3. losing_months    <= 7 of 29 (~24%)
  4. mean_RR per win  >= 0.5
  5. PF lift          >= +0.05 over v0.5.0 baseline

## Result: REJECTED on n threshold; flagged as candidate

```
                                              n     WR     PF    netR    lift   losM
v0.5.0 baseline (29 months)                  262   70.6%  1.44  +33.3R     -    6/19

V1  H1 + v0.5.0 naive timing                  26   84.6%  3.22   +8.9R   +1.78   1/8
V2  H1 + v0.5.0 STRICT timing                 25   84.0%  3.07   +8.3R   +1.63   1/8
V3  H1 + relaxed M5 (strict)                 236   66.5%  1.19  +15.0R   -0.25   5/20
V4  Relaxed M5 only (control)               2040   67.7%  1.25 +162.8R   -0.19   7/28
V5  H1 + EMA pullback + v0.5.0                 6   83.3%  2.93   +1.9R   +1.48   1/4
```

By rule 1 (n >= 50), V2 is rejected. **But the result deserves more honest
discussion than that single number suggests.**

## Why V2 looks promising on the surface

Three things that make V2 different from prior rejected candidates:

### 1. Strict-timing-stable

```
V1 (naive):  PF 3.22  WR 84.6%  on 26 trades
V2 (strict): PF 3.07  WR 84.0%  on 25 trades
```

Phase 9's V2 collapsed from PF 1.65 to 1.08 when strict-timing was applied.
Here V1 -> V2 only drops PF by 0.15 and loses 1 trade. **No look-ahead
artifact.** H1 trend is mostly stable across 5-minute windows, so the
1-minute strict-timing buffer rarely changes the answer.

### 2. PF lift of +1.63 over baseline

If real, this is the largest PF improvement on top of v0.5.0 we've ever
measured. Phase 3 (sr_band) cut PF by 0.32. Phase 6 confluences hurt PF.
Phase 9 strict-timing FVG hurt PF. V2 is the first filter to lift PF
substantially.

### 3. Losing months: only 1 of 8 active months

When V2 fires, it usually wins. Single losing month: 2025-12 (-0.41R on
2 trades, 1W/1L).

## Why V2 fails the integrity check

### 1. n=25 is below the n>=50 threshold

That threshold exists to reject curve-fits like Phase 6's V3 (n=16, PF 8.78,
all variance). V2 is at the boundary. The 95% confidence interval on WR
with n=25 is roughly **65% to 95%**. With n=262 it's 65% to 76%. So V2's
"84%" is consistent with anything from "edge slightly better than v0.5.0"
to "spectacular edge." **We cannot tell from this sample.**

### 2. The trades are concentrated in 8 months, not 29

```
2024-01 to 2025-09:  21 months    1 V2 trade (April 2024)
2025-10 to 2026-04:   7 months   24 V2 trades  (winning streak)
2026-05:              1 month     0 V2 trades

V2 trades by month:
  2024-04:  1 trade   (1W/0L)  +0.59R
  2025-10:  5 trades  (4W/1L)  +1.34R
  2025-11:  1 trade   (1W/0L)  +0.59R
  2025-12:  2 trades  (1W/1L)  -0.41R    <-- only losing month
  2026-01:  2 trades  (2W/0L)  +1.17R
  2026-02:  7 trades  (5W/2L)  +0.93R
  2026-03:  6 trades  (6W/0L)  +3.51R    <-- best
  2026-04:  2 trades  (2W/0L)  +1.17R
```

Phase 8 already established that v0.5.0 is a high-vol-regime player. V2
amplifies this: it requires BOTH strong H1 momentum AND qualifying M5
candles -- a stricter regime filter. **V2 is essentially "v0.5.0 only in
strongly trending regimes."** That regime existed for 7 of 29 months.

### 3. The "lift" is mostly because the rejected v0.5.0 trades had high WR too

This deserves explicit math. v0.5.0 baseline is 262 trades at 70.6% WR.
V2 keeps 25 of them with 84% WR. The dropped 237 trades had:

```
237 dropped trades:  baseline 262 - kept 25 = 237
Baseline WR:         70.6% on 262 = 185 wins / 77 losses
V2 WR:               84% on 25 = 21 wins / 4 losses
Dropped trades:      164 wins / 73 losses on 237 = 69.2% WR
```

So the H1 filter retained signals winning at 84% and dropped signals winning
at 69%. That's a +15-point WR difference -- real, but on a small kept
sample. The dropped 69% trades still net positive R. The lift is from
selection, not from a per-trade quality boost large enough to be confident.

## Honest interpretation

V2 is the cleanest candidate signal we've seen, but it doesn't pass the
sample-size threshold. Three responses:

### Option A: reject by rule, move on

The n>=50 rule was set before the run for exactly this reason. Apply it.
V2 stays in the "interesting but unproven" file. v0.5.0 remains the
deployable strategy.

### Option B: pull more historical data

We have data from 2024-01. Going back to 2022-2023 would roughly double
the sample. Risk: gold's 2022-2023 regime was different (lower volatility,
different macro), so we'd be testing across regimes. The result might be
diluted or distorted.

### Option C: forward-test V2 as a candidate alongside v0.5.0

Build a V2 EA. Deploy on demo alongside the v0.5.0 EA with a separate
magic number. Run both for 30 days. Real fills + 30 more trade samples
are the only thing that can confirm or kill V2's edge.

## What V3, V4, V5 tell us

```
V3: H1 + relaxed M5 (strict)        n=236  PF 1.19   lift -0.25   REJECT
V4: Relaxed M5 only (control)       n=2040 PF 1.25   lift -0.19   REJECT
V5: H1 + EMA pullback + v0.5.0      n=6    PF 2.93   too small    REJECT
```

V3 and V4 confirm: **the strict v0.5.0 M5 filter is what produces edge.**
Relaxing the M5 filter drops PF below the deployable threshold whether or
not H1 alignment is added. The strict filter is non-negotiable.

V5 is too small to read.

## Verdict by pre-committed rules

**REJECTED on n threshold (n=25 < 50).**

Filed as: "candidate signal; would require either more data or forward-test
confirmation to be deployable."

## What stays decided

- v0.5.0 momentum-candle remains the only deployable strategy
- 3 confirmations / 7 rejections (Phase 10 added)
- MTF on its own does NOT unlock new signals (V3, V4 confirm)
- H1 alignment may genuinely improve v0.5.0 -- inconclusive, sample too small
- Strict v0.5.0 M5 filter is non-negotiable

## What this taught us

1. **Strict-timing safeguard generalizes.** It caught Phase 9's look-ahead
   and confirmed V2 is timing-stable. The variant pattern is now a core
   discipline.

2. **The n threshold matters more than ever.** Without it, V2's 84% WR
   on 25 trades would look like edge. The threshold exists precisely
   because variance can produce eye-catching numbers on small samples.

3. **Regime concentration is now expected.** Phase 8 found v0.5.0 fires
   93% of trades in 9 of 29 months. V2 is a stricter filter that amplifies
   this -- 96% of trades in 7 of 29 months. Adding more filters narrows
   the regime window.

## Files

- `scripts/phase10_mtf_backtest.py` -- backtest script
- `data/backtests/phase10-results.json`
- `data/backtests/phase10-report.md` -- this file

## Next

Three honest paths from here:

1. **Apply rule, move on.** v0.5.0 stays the deployable. Forward-test
   begins.

2. **Pull 2022-2023 M5 data** to extend window to 4-5 years. If V2 still
   has 80%+ WR on 60+ trades, it's a confirmed candidate. If it dilutes
   to 70%, baseline is the right call.

3. **Build V2 EA + dual deployment.** Deploy v0.5.0 + V2 EAs concurrently
   on demo, separate magic numbers. After 30 days, compare actual fills
   to backtest expectations. Real fills are the only honest signal at
   this sample size.

Recommended: option 1 + option 3 in parallel. v0.5.0 deploys with a
known edge. V2 deploys as a research candidate alongside it. Cost: zero
additional risk (each magic number runs its own positions, both at 1%
risk, both capped at 1 position simultaneously).

If V2 keeps printing 80%+ WR over the next 30 days of real fills, it
graduates from "candidate" to "deployable." If it drops below 70%, it's
shelved.
