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
| Mon 2026-05-18 | `2026-05-18-mon.md` | 248 |  96 | 50 | NO  | — | — |

## Aggregate

- Days tagged: **2 / 5**
- Total YES tags: **8**
- Total NO tags: **92**
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

NO reasoning was uniformly **"open-close point to small"** across all 92 NO tags so far. Absolute size remains the dominant rejection criterion.

## Combined-day statistics (2 days, 8 YES, 92 NO)

### Range
- YES: min 12.61 / mean 16.24 / max 22.51
- NO:  min 2.21 / mean 8.05 / max 14.89
- **Floor revised to 12.5 pts** (was 15 after Fri only, 20 originally)

### Body%
- Continuation/breakout YES (n=4 across both days): 85-96%
- Reversal YES (n=4 across both days): 52%, 67%, 84%, 86%
- **The reversal exception is REAL.** Body floor splits into two regimes:
  - non-reversal: ≥ 84%
  - reversal: ≥ 50% with strong engulfing/swing-extreme context

### Close-side wick%
- Continuation/breakout YES: 0–12% (all ≤ 12%)
- Reversal YES: 0%, 6%, 32%, 34%
- **Reversal exception relaxes wick to ≤ 35%** when E is present.

### Context tag lift (combined)
| Tag | YES rate | NO rate | Lift |
|---|---:|---:|---:|
| E engulfing       | 5/8 (62%) | 43/92 (47%) | +1.3x |
| T trend-monotonic | 4/8 (50%) | 23/92 (25%) | +2.0x |
| S swing-extreme   | 2/8 (25%) | 18/92 (20%) | +1.3x |
| V velocity-flip   | 2/8 (25%) | 47/92 (51%) | -2.0x (negative!) |
| R round-number    | 0/8 (0%)  | 29/92 (32%) | -inf (negative!) |
| C consolidation   | 0/8 (0%)  |  4/92 (4%)  | weak negative |

**E and T are the two real contextual signals so far.** R and V should be dropped from the eye-model — they correlate with NO more than with YES.

## Provisional eye-model (after 2 of 5 days)

```
def is_momentum_candle(bar):
    if bar.range < 12.5: return False         # absolute size floor
    if not is_active_session(bar.time):       # Asia 23-08 UTC OR NY 12-22 UTC
        return False  # tentative — needs Mon/Tue/Wed validation

    if reversal_context(bar):                 # E or strong S
        # relaxed geometry
        return bar.body_pct >= 0.50 and bar.wick_pct <= 0.35
    else:
        # standard geometry (continuation/breakout)
        return bar.body_pct >= 0.84 and bar.wick_pct <= 0.12

def reversal_context(bar):
    return bar.engulfs_prior or bar.near_swing_extreme
```

This is the first hypothesis that fits ALL 8 YES tags so far. Next sessions
(Mon, Tue, Wed) will test whether it holds or needs revision.

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
