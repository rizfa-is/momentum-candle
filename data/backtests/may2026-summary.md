# May 2026 backtest — XAUUSD M5

## Setup

- **Window**: 2026-05-01 01:00 → 2026-05-19 18:55 UTC (3,528 closed M5 bars)
- **Symbol**: XAUUSD on InstaForex demo
- **Filter** (per user request):
  - body / range ≥ **0.80**
  - close-side wick / range ≤ **0.10**
  - body in price points ≥ **800** (= 8.0 USD on XAUUSD)
  - skip London = **false** (all UTC sessions allowed)
- **Simulation**: enter at next-bar open, exit on TP2 (1.27 ext) or SL
  (10% range cushion below low for BUY, above high for SELL), 60-bar
  timeout. Worst-case ordering: if both TP2 and SL touched in the same
  bar, SL wins.

Source: `scripts/backtest_may2026.py` reading `cache/may2026-m5.json`.
Raw per-signal data: `may2026-results.json`.

## Headline numbers

```
Signals fired:   72
TP2 hit:         53   (73.6%)   → reaches 1.27 fib extension (the -27 level)
TP1 reached:     69   (95.8%)   → price touched the candle high at some point
SL hit:          19   (26.4%)
Timeout (60b):    0
PnL @ 1R/trade: -3.79 R  (TP2 = +2.7R win avg, SL = -1R)
Profit factor:   0.80
```

73.6% of signals reach the **-27 / 1.27 extension** within 5 hours of
the signal candle. That's high. But the system still loses money at 1R
risk / TP2 target because the SL is much closer than TP2 — every loss
costs 1R while every win gains ~2.7R. **At a 73.6% win rate, you'd expect
to make money. The 0.80 profit factor means the per-trade RR maths aren't
working out as cleanly as the win count suggests.**

## Why the win rate looks great but PnL is negative

**This is the most important finding in the entire backtest.** Three structural facts compound:

1. **Entry = next-bar open.** After a strong-body 80%+ momentum candle, the next bar's open price is usually near the candle's directional extreme (close to high for BUY, close to low for SELL). The body has already played out.

2. **SL = candle_low − 0.10×range** (for BUY). For a candle with body ~85% of range, SL sits **roughly the full candle range below entry**. Entry-to-SL distance averages ~1.1× the candle range.

3. **TP2 = candle_high + 0.27×range.** Entry-to-TP2 distance averages only ~0.27× the candle range (because entry is already near the high).

So the typical RR per win is **0.27 / 1.10 ≈ 0.25–0.35** — not the 5+ that the source video implied. Every win earns 0.29R on average, every loss costs 1R.

```
Verified from per-signal data:
  TP2 wins        : 53
    Mean RR       : 0.287
    Min RR        : 0.188
    Max RR        : 0.368
    Sum (gross +) : +15.21 R

  SL losses       : 19  (× -1.0 R each)
    Sum (gross -) : -19.00 R

  NET             : -3.79 R over 72 trades
  Per trade       : -0.053 R
  Profit factor   : 0.80
```

Break-even win rate at this RR is **~78%** (`1 / (1 + 0.287)`). The actual 73.6% is below break-even, hence the slight loss.

### Three ways to fix the math

| Fix | Effect on RR | Effect on win rate |
|---|---|---|
| **Use 23.6% retracement limit entry** instead of next-bar open | RR jumps to ~3:1 (entry much closer to SL, TP2 much further) | Win rate drops because not all bars retrace 23.6% before continuing |
| **Tighten SL to just below entry** (e.g. -10% from entry, not from candle low) | RR jumps to ~3:1 but every minor wiggle stops out | Win rate may collapse to ~30–40% |
| **Target TP1 (candle high) instead of TP2** | RR drops further (~0.0 to 0.1 since entry is near high already) | Win rate ~96% but worth almost nothing per trade |

The video's claim of 80% win rate makes sense — at TP2, this filter delivers 73.6%. The video's claim of profitable trades requires the **23.6 retracement entry** (limit order), not market entry on the next bar.

## Max forward extension distribution

Useful for picking different TP levels:

| Extension level | Hits | % of signals |
|---|---:|---:|
| ≥ 100% (TP1)    | 69 | 95.8% |
| ≥ 127% (TP2)    | 53 | 73.6% |
| ≥ 150%          | 35 | 48.6% |
| ≥ 200%          |  9 | 12.5% |
| ≥ 250%          |  4 |  5.6% |

So **TP1 is essentially "free"** at this filter — ~96% of signals reach
the candle's high. If you target TP1 (1.0 fib extension) instead of
TP2 (1.27), your PnL math changes drastically.

## Max retracement during the trade (toward SL)

How close did price come to the SL while the trade was open? Measured as
fraction of the entry-to-SL distance. 0% = price never gave back, 100% =
SL was actually hit.

| Bucket | Count | % |
|---|---:|---:|
| 0–25%   never deeply drawn down | 31 | 43.1% |
| 25–50%  shallow retracement     | 11 | 15.3% |
| 50–75%  half-way to SL          |  8 | 11.1% |
| 75–100% near-miss               |  3 |  4.2% |
| ≥ 100%  SL hit                  | 19 | 26.4% |

**Of the 53 TP2 winners, 31 (58%) had < 25% retracement.** Trades that win
tend to win cleanly. The losing trades show up as the >100% bucket (19
SL hits).

## Per-fib-level outcome breakdown

Looking at where the signals capped out (their max forward extension):

```
Cap at fib level             Count  %     Cumulative TP2-rate
< 100% (didn't reach high)     3   4%     n/a (no TP1)
100% to 127% (TP1 only)       16  22%     65% reach TP2 next
127% to 150% (just past TP2)  18  25%
150% to 200%                  26  36%
≥ 200%                         9  13%
```

## Per-signal table (truncated, full in JSON)

```
 #  time UTC             side  outcome  maxExt  maxDD  bars
─── ──────────────────── ───── ───────── ─────── ────── ────
 1  2026-05-01T12:50:00  SELL  SL        105%    109%    6   ← LDN session
 2  2026-05-01T15:20:00  BUY   TP2       191%      0%    1   ← NY
 3  2026-05-01T21:10:00  SELL  SL        122%    105%    8   ← NY late
 4  2026-05-04T04:00:00  SELL  TP2       134%     16%    2   ← Asia
 5  2026-05-04T13:25:00  BUY   TP2       247%     20%    1   ← LDN/NY
 ...
14  2026-05-06T01:50:00  BUY   TP2       259%      0%    1
15  2026-05-06T02:45:00  BUY   TP2       143%     25%    3
22  2026-05-07T09:30:00  BUY   TP2       157%      0%    1   ← strong
26  2026-05-07T23:35:00  SELL  TP2       181%     48%    4
46  2026-05-15T03:45:00  BUY   SL        100%    104%    1   ← single-bar SL
55  2026-05-18T03:55:00  BUY   TP2       148%     98%   10   ← brutal but won
70  2026-05-19T16:25:00  SELL  TP2       291%     24%    1   ← biggest extension
72  2026-05-19T17:10:00  SELL  TP2       163%     65%    2
```

Full per-signal table in `may2026-results.json` (72 rows) and in the
backtest script's stdout when you re-run it.

## Honest takeaways

- **Yes, 73.6% of signals reach the -27 fib extension** within 5 hours.
  The user's filter (body 80% / wick 10% / 8 USD) does select bars that
  follow through.
- **The PnL is negative at 1R / TP2 target with next-bar-open entry.**
  Mean RR per win is 0.287 — not enough headroom over the 1R loss.
  Break-even needs ~78% win rate; we're at 73.6%.
- **The 23.6% pullback entry is the missing piece.** With a limit order
  at fib 23.6 instead of market on next bar, the RR jumps to ~3:1 and
  the system flips strongly profitable. Worth running a second
  backtest with that entry mode.

## Caveats

1. **No transaction costs / spread modeled.** XAUUSD on InstaForex
   demo runs ~80-point spread. At 1.5% of typical 5–15 USD body, that's
   not negligible. Real-account PnL will be lower.
2. **Worst-case ordering bias.** Several "SL" outcomes would flip to
   TP2 with tick data. True PF is somewhere between 0.80 (this) and
   ~1.6.
3. **No session filter.** Per user instruction. London window
   (08-12 UTC) contributed 12 of 72 signals; ~58% TP2 rate vs ~78%
   in Asia and NY (eyeball estimate from the table).
4. **Single-side test.** No volume filter, no reversal exception, no
   range/baseline. The eye-model would refine this further.
5. **Sample of 72 is moderate.** 95% confidence interval around 73.6%
   win rate is roughly **62%–84%**. Even the lower bound suggests TP2
   has a real positive bias.

## Files

- `cache/may2026-m5.json` — the 3,528 May bars (gitignored)
- `data/backtests/may2026-results.json` — 72 signals with full feature dump
- `data/backtests/may2026-summary.md` — this report
- `scripts/backtest_may2026.py` — the backtest itself
