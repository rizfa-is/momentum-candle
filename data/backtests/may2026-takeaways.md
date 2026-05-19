# May 2026 backtest — factor analysis takeaways

> Companion to `may2026-factor-analysis.md` (full numeric tables) and
> `may2026-summary.md` (the original 72-signal headline report).

The 72 May 2026 signals split sharply on a handful of factors. This
report identifies the strong predictors and tests an optimized filter
combining them.

## Strong WR-lifting factors (use as positive filters)

Sorted by lift on next_open WR (baseline 73.6%):

| Factor | Bucket | n | WR | lift |
|---|---|---:|---:|---:|
| **Range** | 14–18 USD | 13 | 92.3% | +18.7pp |
| **Body in points** | 1300–1700 (~13–17 USD) | 10 | 100.0% | +26.4pp |
| **Body %** | 0.90–0.95 | 18 | 88.9% | +15.3pp |
| **Distance to nearest $50** | 5–15 USD (the "fairway") | 29 | 93.1% | +19.5pp |
| **Close-wick %** | 5–8% (small but not zero) | 14 | 85.7% | +12.1pp |
| **Far-wick %** | 0–2% (clean marubozu) | 25 | 84.0% | +10.4pp |
| **Trend monotonic prior 7** | 0–2 (no prior trend, fresh leg) | 18 | 83.3% | +9.7pp |
| **Session** | NY (12-22 UTC) | 41 | 78.0% | +4.4pp |

## Strong WR-dragging factors (use as negative filters / skip)

| Factor | Bucket | n | WR | drag |
|---|---|---:|---:|---:|
| **Body %** | 0.80–0.85 (just-over-threshold) | 10 | 50.0% | -23.6pp |
| **Body in points** | 800–1000 (smallest tier) | 37 | 62.2% | -11.4pp |
| **Range** | 8–11 USD (smallest tier) | 34 | 61.8% | -11.8pp |
| **Distance to nearest $50** | 15–30 USD ("donut zone") | 26 | 50.0% | -23.6pp |
| **Far-wick %** | 10–20% (long opposite wick) | 15 | 53.3% | -20.3pp |
| **Session** | London (8-12 UTC) | 10 | 60.0% | -13.6pp |
| **Trend monotonic prior 7** | 5–6 (exhausted trend) | 12 | 66.7% | -6.9pp |

## Surprising findings

### 1. Body 0.80–0.85 is a trap

The bottom 14% of body% bars (just barely passing the 0.80 floor) win
only 50% of the time. The rest of the body% spectrum wins 70–89%. **A
small body% bump from 0.80 to 0.86 cuts 10 trades and raises
aggregate WR meaningfully.**

### 2. The "donut zone" — 15-30 USD from a round number

This is the strongest individual factor. Bars whose extreme sits 15–30
USD from the nearest $50 multiple win **50%**. Bars 5–15 USD away win
**93.1%**. Bars within 5 USD win 76.5%.

Interpretation: when price is between round-number magnets (no clear
support/resistance reference nearby), momentum bars are more likely to
reverse. When price is approaching or has just cleared a round number,
follow-through is much more reliable.

### 3. Body in absolute points dominates body %

Body 1300+ points (= $13+ body) won **100% of the time** in May 2026
(n=12). Body 800–1000 points won only 62%. **Raising the absolute
floor from 800 to 1000 points removes the worst-performing tier
without losing the best ones.**

### 4. Engulfing prior bar is a *negative* signal here

Counter to the eye-tag dataset finding (where engulfing showed +1.3x
lift in the YES rate), in the May trading data engulfing bars hit TP2
only 67.7% vs 78.0% for non-engulfing. Possible explanation: an
engulfing momentum candle may already represent a partial reversal
that's about to mean-revert, while a "fresh-leg" momentum candle
(not engulfing) has more room to run.

The eye-tag dataset measured "did the user think this looks like a
momentum candle". This backtest measures "did it actually reach TP2".
The two metrics are different. The eye sees pattern beauty; the market
rewards follow-through.

### 5. Trend monotonic count surprises

Bars with **0–2 monotonic prior closes** (i.e. no clear prior trend)
win 83.3%. Bars in established trends (5–6 monotonic) win only 66.7%.
This contradicts the "trend continuation" hypothesis. The signal works
*best* when it's surprising (trendless context, big bar appears) and
*worst* when the trend is mature (everyone already long, exhaustion
bar instead of continuation).

### 6. Far-wick filter is real and strong

Bars with far-side wick 10–20% win only 53.3%. The cleanest marubozus
(far-wick 0–2%) win 84%. **The user's earlier intuition that "wick
should be below 5%, both lower or higher" is empirically validated** —
the indicator's recently added `InpMaxFarWickPct=0.05` would catch all
the 25 best far-wick bars (84% WR) while excluding the 15 worst.

## Proposed optimized filter

Stacking the strongest positive selectors:

```
PASS only if ALL hold:
  body / range          >= 0.86         (was 0.80; cuts the 50% WR tier)
  close-side wick / range <= 0.10
  far-side wick / range  <= 0.05         (already in indicator)
  body in points        >= 1000          (was 800)
  range in points       >= 1100          (~11 USD; cuts the 8-11 tier)
  distance to $50 round  in [0, 15] USD  (avoid the donut zone)
  session               != London (skip 8-12 UTC)
  trend_monotonic_prior_7 in [0, 4]      (avoid exhausted trends)
```

Expected performance based on May 2026 data alone — to be verified by
a backtest run:

| Mode | Estimated n | Estimated WR | Estimated PF |
|---|---:|---:|---:|
| next_open | 25–35 | 85–90% | 1.6–2.0 |
| pullback_236 | 22–30 | 75–82% | 1.7–2.2 |

These are projections — overfit risk is high since the same dataset
was used to identify the filters and to estimate the result. A clean
out-of-sample test (e.g. April 2026) would tell us if the lift
survives.

## Action items

1. **Run the optimized filter** on the same May 2026 dataset to confirm
   the projected WR and PF (script: extend `backtest_may2026.py` with
   filter-config variants).
2. **Pull April 2026 data** as out-of-sample validation. If the
   optimized filter holds up, the system is meaningfully profitable
   on this broker even after spread.
3. **Update the MQL5 indicators** to include:
   - Tighter body % threshold (0.86)
   - Body-in-points input on Video/Proxy (already on Simple)
   - Distance-to-round-50 input
   - Trend-monotonic-prior-7 cap
4. **Refine the eye-model**. Today's data shows the *eye* favored
   engulfing (E) with +1.3x lift, but the *market* punishes engulfing
   with -10pp WR drag. The eye-model and the market-truth model are
   different. Both are worth keeping but they answer different
   questions:
   - Eye-model: "what looks like a momentum candle?"
   - Market-truth: "what reaches TP2?"

## What to ignore

- **Engulfing as a positive filter** — the eye-tag dataset said yes,
  the market backtest says no. Until we have more data, treat as
  ambiguous.
- **Trend-aligned context** — only +2.6pp lift, well within noise at
  n=42. Drop from filter consideration.
- **R5, V5 ratios** — moderate predictors but noisy. Keep at current
  thresholds.
- **At-day-low / at-day-high** — small-sample (n=12), inconsistent
  direction. Drop.

## Files

```
scripts/analyze_may2026_factors.py            the analysis script
data/backtests/may2026-factor-analysis.json   raw enriched per-signal data
data/backtests/may2026-factor-analysis.md     full numeric tables
data/backtests/may2026-takeaways.md           this report
```
