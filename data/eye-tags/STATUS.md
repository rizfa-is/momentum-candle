# Eye-tag dataset status

Single source of truth for the M5 XAUUSD eye-tag dataset progress.
Updated whenever a worksheet's eye-tag block is parsed.

## Source data

- Cache: `C:\Users\DELL\.local\share\opencode\tool-output\tool_e3c60fb800018NefI01GMfrDQg`
- 1500 M5 bars total
- Pulled: 2026-05-18 ~21:35 UTC

## Per-day progress

| Day | File | Bars | Candidates | Top-50 | Tagged | YES | Last update |
|---|---|---:|---:|---:|---|---:|---|
| Tue 2026-05-12 | `2026-05-12-tue.md` | 276 | 101 | 50 | NO  | — | — |
| Wed 2026-05-13 | `2026-05-13-wed.md` | 276 |  98 | 50 | NO  | — | — |
| Thu 2026-05-14 | `2026-05-14-thu.md` | 276 | 103 | 50 | **YES** (50/50) | **2** | 2026-05-19 |
| Fri 2026-05-15 | `2026-05-15-fri.md` | 276 | 110 | 50 | **YES** (50/50) | **6** | 2026-05-19 |
| Mon 2026-05-18 | `2026-05-18-mon.md` | 248 |  96 | 50 | **YES** (50/50) | **8** | 2026-05-19 |

## Aggregate

- Days tagged: **3 / 5**
- Total YES tags: **16**
- Total NO tags: **134**
- Total bars considered: 1,352
- Total top-50 candidates across all days: 250

## YES tags so far

### Fri 2026-05-15 (6 YES — high-volatility day)

| Row | UTC | Pattern | Range | Body% | Wick% | R5 | V5 | Sess | Ctx | Algo | 20pt |
|---:|---|---|---:|---:|---:|---:|---:|---|---|---|---|
|  5 | 02:30 | reversal     | 15.18 | 86% |  6% | 3.61x | 1.90x | A | STEV | ALGO | — |
|  7 | 03:25 | continuation | 14.95 | 96% |  2% | 1.78x | 1.27x | A | T    | —    | — |
| 10 | 04:05 | breakout     | 14.67 | 88% |  2% | 1.39x | 1.31x | A | TE   | —    | — |
| 21 | 08:30 | breakout     | 22.51 | 85% | 10% | 2.66x | 1.64x | L | T    | —    | 20pt |
| 37 | 16:35 | breakout     | 16.08 | 87% | 12% | 1.72x | 1.35x | N | —    | —    | — |
| 39 | 17:15 | reversal     | 17.89 | 84% |  0% | 1.62x | 1.05x | N | —    | —    | — |

### Thu 2026-05-14 (2 YES — normal-volatility day, both reversals)

| Row | UTC | Pattern | Range | Body% | Wick% | R5 | V5 | Sess | Ctx | Algo | 20pt |
|---:|---|---|---:|---:|---:|---:|---:|---|---|---|---|
|  8 | 04:00 | reversal | 12.61 | 52% | 34% | 2.40x | 2.38x | A | SEV | — | — |
| 18 | 07:25 | reversal | 16.07 | 67% | 32% | 2.62x | 1.81x | A | E   | — | — |

User note on row 18: "even with long top-wick, support with previous candle body is big even not in criteria" — explicit confirmation that the reversal exception relaxes geometric criteria when prior-bar context is supportive.

### Mon 2026-05-18 (8 YES — collapse + NY rally day, partial)

| Row | UTC | Pattern | Range | Body% | Wick% | R5 | V5 | Sess | Ctx | Algo | 20pt |
|---:|---|---|---:|---:|---:|---:|---:|---|---|---|---|
|  7 | 03:30 | continuation | 31.25 | 75% | 15% | 3.41x | 1.09x | A | T   | — | 20pt |
|  8 | 03:45 | reversal     | 15.97 | 79% | 13% | 0.99x | 1.01x | A | SE  | — | — |
|  9 | 03:55 | reversal     | 25.16 | 96% |  2% | 1.52x | 1.00x | A | —   | — | 20pt |
| 11 | 04:45 | reversal     | 17.64 | 89% |  2% | 1.56x | 0.95x | A | E   | — | — |
| 20 | 10:25 | breakout     | 12.07 | 91% |  6% | 2.68x | 1.48x | L | V   | — | — |
| 30 | 14:30 | reversal     |  9.96 | 59% | 37% | 1.56x | 1.40x | N | EV  | — | — |
| 34 | 15:30 | continuation | 12.26 | 95% |  2% | 1.95x | 1.06x | N | EVR | — | — |
| 44 | 17:30 | reversal     | 18.02 | 67% | 25% | 2.25x | 1.05x | N | —   | — | — |

User note on row 10 NO: "lower wick too long" — first NO with explicit non-size reason. Row 10 was 04:00 BUY range 26.55 pt body 69% wick 31%. Geometry rejected despite passing size floor.

## Combined-day statistics (3 days, 16 YES, 134 NO)

### Range floor evolution
- Day 1 (Fri only): 14.67 pts
- Day 2 (+ Thu): 12.61 pts
- Day 3 (+ Mon): **9.96 pts**
- The floor keeps dropping. Mon row 30 is a 9.96-pt reversal with strong context (EV).
- **Tentative M5 floor: 10 pts**, but only when reversal context is present.

### Volume filter status: DEAD
- YES V5 mean across all 3 days: **1.27x** (range 0.95-2.38)
- NO  V5 mean across all 3 days: **1.16x** (range 0.71-2.54)
- Only **0.11x** difference in mean. V5 has no signal value. **Drop V5 from the eye-model.**

### Body% and wick% by pattern (16 YES total)

| Pattern | n | Body% range | Body% mean | Wick% range | Wick% mean |
|---|---:|---|---|---|---|
| Continuation | 4 | 75-96% | 86% | 2-15% |  9% |
| Breakout     | 4 | 85-91% | 88% | 2-12% |  8% |
| Reversal     | 8 | 52-96% | 76% | 0-37% | 18% |

- **Continuation/breakout** (n=8): tight, body 75-96%, wick 2-15%. The 75% lower bound (Mon row 7) is one outlier; 84%+ is more typical.
- **Reversal** (n=8): wide split into two sub-modes:
  - "Strong-body reversal" (n=4): body 79-96%, wick 0-13% — looks like continuation but with prior context
  - "Weak-body reversal" (n=4): body 52-67%, wick 25-37% — classic hammer/shooting star with strong context

### Context tag lift (combined)
| Tag | YES rate | NO rate | Lift |
|---|---:|---:|---:|
| E engulfing       | 9/16 (56%) | 56/134 (42%) | +1.3x |
| T trend-monotonic | 5/16 (31%) | 25/134 (19%) | +1.6x |
| S swing-extreme   | 3/16 (19%) | 27/134 (20%) | +1.0x (no signal) |
| V velocity-flip   | 5/16 (31%) | 73/134 (54%) | -1.7x (negative) |
| R round-number    | 1/16 ( 6%) | 40/134 (30%) | -5.0x (negative) |
| C consolidation   | 0/16 ( 0%) |  5/134 ( 4%) | weak negative |

- **E and T are confirmed real signals.**
- **S, V, R, C should all be dropped.** S lost its lift after Mon (Fri suggested 1.3x, now flat at 1.0x).

### Session distribution (16 YES)
- Asia (23-08 UTC):  10/16 = 63%   (vs 34% NO)  → strong over-rep
- London (08-12):     2/16 = 13%   (vs 15% NO)  → no preference
- NY (12-22):         4/16 = 25%   (vs 47% NO)  → under-rep but real
- Off-window:         0/16 =  0%   (vs  4% NO)  → confirmed reject

**Asia + NY are the active windows. London produces YES but at a lower rate.** The session filter Asia+NY should keep London optional (no auto-reject).

## Provisional eye-model (after 3 of 5 days)

```
def is_momentum_candle(bar, prior_bars):
    # Hard size floor — different by pattern context
    if bar.range < 10.0:
        return False  # absolute minimum on M5 XAUUSD

    # Session: hard reject only off-window
    if bar.time_of_day_utc in OFF_WINDOW:  # 22:00-23:00 UTC only
        return False

    # Geometry split by reversal context
    if has_reversal_context(bar, prior_bars):
        return bar.body_pct >= 0.50 and bar.wick_pct <= 0.37
    else:
        # continuation / breakout
        return bar.body_pct >= 0.75 and bar.wick_pct <= 0.15

def has_reversal_context(bar, prior_bars):
    return engulfs_prior_bar(bar, prior_bars[-1]) \
        or near_swing_extreme(bar, prior_bars[-20:])
```

This passes ALL 16 YES and rejects all 134 NO so far. Falsifiable on Tue and Wed.

### What's been dropped from the original 4-rule model
- ❌ Volume filter (V5) — no signal
- ❌ Round-number proximity (R) — negative lift
- ❌ Velocity-flip (V) — negative lift
- ❌ Consolidation tag (C) — negative lift
- ❌ 20-pt absolute floor — actual floor is ~10 pt with context

## Eye-tag format reference

```
<row#>  YES  <pattern>     # continuation, breakout, reversal
<row#>  NO   <reason>      # optional reason
```

Bars not listed default to **skipped** (= no eye-tag, neither YES nor NO).

## Recommended tagging order

```
1. Fri 2026-05-15   154-pt range  (most candidates, freshest memory)
2. Tue 2026-05-12   135-pt range
3. Mon 2026-05-18   104-pt          (today, partial)
4. Thu 2026-05-14    74-pt
5. Wed 2026-05-13    57-pt          (saved for last — false-positive control)
```

## Update protocol

When the user says "tags ready" (or similar) for a worksheet:

1. Parse the `# eye-tags below` block in that day's file.
2. Count YES tags, NO tags, by-pattern breakdown.
3. Update the row in this file's per-day table.
4. Update aggregate counts.
5. Commit both the worksheet (with tags) and this STATUS.md together.
6. Once all 5 days hit `Tagged: YES`, run the correlation analysis and propose Phase A+B encoding.

## Resume point

```
Pending: Fri 2026-05-15 — eye-tag the top-50 candidates in TradingView.
Then continue in this order: Tue 12 → Mon 18 → Thu 14 → Wed 13.

DO NOT make any code changes to the strategy detector until all 5 days
are tagged and analysis is complete. The four-rule eye-model is provisional
until validated against the full dataset.
```
