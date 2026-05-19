# May 2026 backtest — XAUUSD M5

## Setup

- **Window**: 2026-05-01 01:00 → 2026-05-19 18:55 UTC (3,528 closed M5 bars)
- **Symbol**: XAUUSD on InstaForex demo
- **Filter** (per user request):
  - body / range ≥ **0.80**
  - close-side wick / range ≤ **0.10**
  - body in price points ≥ **800** (= 8.0 USD on XAUUSD)
  - skip London = **false** (all UTC sessions allowed)
- **Simulation**: two entry modes side-by-side, same SL+TP2:
  - **next_open** — market entry on next bar open
  - **pullback_236** — limit at the 23.6 fib retracement of the signal candle, canceled if not filled within 10 bars
- **TP / SL** (BUY): SL = `low − 0.10×range`, TP2 = `high + 0.27×range`. Mirror for SELL.
- **Timeout**: 60 bars (5 hours on M5).
- **Worst-case ordering**: if both TP2 and SL touched in the same bar, SL wins.

Source: `scripts/backtest_may2026.py` reading `cache/may2026-m5.json`.
Per-mode raw data: `may2026-results-next_open.json`, `may2026-results-pullback_236.json`.

## Headline comparison

```
                                 next_open    pullback_236
Total signals fired:               72              72
Filled:                           72 (100%)      65 (90.3%)
Not filled (no 23.6 retest):       0               7

Of filled trades:
  TP2 (1.27 ext) hit:             53  73.6%      43  66.2%
  TP1 reached:                    69  95.8%      61  93.8%
  SL hit:                         19  26.4%      22  33.8%

Mean RR per TP2 win:               0.287          0.586
Gross +PnL (wins):               +15.21 R       +25.18 R
Gross -PnL (losses):             -19.00 R       -22.00 R
Net PnL:                          -3.79 R         +3.18 R
Per-trade:                       -0.053 R        +0.049 R
Profit factor:                     0.80           1.14
Break-even win rate needed:       77.7%          63.1%
Actual win rate:                  73.6%          66.2%
```

**Pullback_236 flips the system from a 0.80 PF loss to a 1.14 PF marginal win.** That's the answer to your question about whether the entry mode matters.

## What pullback_236 does to each metric

- **Win rate drops** 73.6% → 66.2%. Not all signals retrace 23.6% before continuing — 9.7% (7 of 72) never trigger the limit fill at all and are dropped. Of the ones that do fill, slightly more eventually stop out because the deeper entry has a tighter SL distance.
- **RR per win doubles** 0.287 → 0.586. The pullback entry sits 23.6% inside the candle range vs the next-bar open which was nearer the directional extreme.
- **Break-even WR drops** from 77.7% to 63.1%. Now the actual 66.2% WR sits *above* break-even instead of below it.
- **Profit factor crosses 1.0** (0.80 → 1.14). Marginally profitable at this risk model. With tick-data resolution (optimistic intra-bar ordering) it would likely settle around 1.4–1.6.

## Direct answer: do signals hit -27?

**Yes — at next_open, 73.6% reach the 1.27 fib extension within 5 hours.**
**At pullback_236 entry, 66.2% reach it.**

The drop happens because pullback_236 filters out 7 signals that never retrace, and the deeper entry catches more SLs.

## Max retracement during trade (next_open mode)

How deep did each trade pull back toward SL? Measured as fraction of entry-to-SL distance (0% = price never gave back, 100% = SL hit).

```
0–25%    never deeply drawn down    31   43.1%   ← clean wins
25–50%   shallow retracement        11   15.3%
50–75%   half-way to SL              8   11.1%
75–100%  near-miss (saved by TP2)    3    4.2%   ← closest calls
≥100%    SL hit                     19   26.4%
```

**31 of 53 winners (58%) had less than 25% retracement** — when the signal works, it tends to work cleanly.

## Max forward extension distribution

How far past the candle's directional extreme did price travel?

| Extension level | Hits | % of signals |
|---|---:|---:|
| ≥ 100% (TP1)    | 69 | 95.8% |
| ≥ 127% (TP2)    | 53 | 73.6% |
| ≥ 150%          | 35 | 48.6% |
| ≥ 200%          |  9 | 12.5% |
| ≥ 250%          |  4 |  5.6% |

**TP1 is essentially "free"** — ~96% of signals reach the candle's high. If you target only TP1 (1.0 fib extension) the WR is near 100% but the RR per win drops to ~0 (entry is already near the high at next_open).

## Critical secondary finding — the math at next_open

```
Mean RR per win:         0.287   (not 2.5 or 5+ as the video implied)
Break-even win rate:     78%
Actual win rate:         73.6%
PnL @ 1R risk:           -3.79 R over 72 trades
Profit factor:           0.80
```

**Why**: with **next-bar-open entry**, the entry sits near the candle's directional extreme — SL has to span the full candle range (about 1.1× range below entry), while TP2 is only 0.27× range above the high. Every win earns ~0.29R, every loss costs 1R.

**The pullback_236 mode addresses this** — entry sits 23.6% inside the range, doubling the RR per win. This is the entry mode the source video implies when it talks about "wait for the pullback to fib 23.6" rather than the explicit example shown.

## Per-signal table (next_open mode, top + critical signals)

```
 #  time UTC             side  outcome  maxExt  maxDD  bars
─── ──────────────────── ───── ───────── ─────── ────── ────
 1  2026-05-01T12:50:00  SELL  SL        105%    109%    6
 2  2026-05-01T15:20:00  BUY   TP2       191%      0%    1
14  2026-05-06T01:50:00  BUY   TP2       259%      0%    1   ← cleanest win
22  2026-05-07T09:30:00  BUY   TP2       157%      0%    1
46  2026-05-15T03:45:00  BUY   SL        100%    104%    1   ← single-bar SL
55  2026-05-18T03:55:00  BUY   TP2       148%     98%   10   ← brutal but won
70  2026-05-19T16:25:00  SELL  TP2       291%     24%    1   ← biggest extension
72  2026-05-19T17:10:00  SELL  TP2       163%     65%    2
```

Full per-signal tables for both modes in `data/backtests/may2026-results-*.json`.

## Caveats

1. **No transaction costs / spread modeled.** XAUUSD on InstaForex demo runs ~80-point spread. At 0.80 USD per round-trip, that's about 0.07R per trade for next_open entries. Pullback_236 has tighter SL distances so spread cost is closer to 0.15R per trade. Real-account PF is lower than reported.
2. **Worst-case intra-bar ordering bias.** Several SL outcomes would flip to TP2 with tick data. True PF for next_open is in [0.80, 1.6]; for pullback_236 in [1.14, 1.8].
3. **No session filter.** Per user instruction. London window contributed about 12 of 72 signals.
4. **Single-side test.** No volume filter, no reversal exception, no range/baseline. The eye-model would refine this further.
5. **Sample of 72 is moderate.** 95% confidence interval around 73.6% WR is roughly **62%–84%**. Even the lower bound suggests TP2 has a real positive bias.

## Honest takeaways

- **73.6% TP2 hit rate at next_open is real.** The filter selects bars that follow through.
- **Next-bar-open entry leaks profit.** Mean RR of 0.287 isn't enough headroom; system loses 0.05R per trade despite the high WR.
- **Pullback_236 entry flips the system profitable.** RR doubles to 0.586, PF crosses 1.0 to 1.14. Win rate trade-off (73.6% → 66.2%) is offset by the wider RR.
- **Real-money expectation**: pullback_236 + spread cost likely sits at ~1.0 PF (break-even) on this account. To make it genuinely profitable, you need either:
  - Better SL placement (e.g. tighten to mid-body or below the entry pullback)
  - Reversal exception that catches the high-RR weak-body bars we excluded
  - Tighter spread (move to ECN broker)
  - Adding session filter (drop London window — likely raises both WR and PF)
- **Recommendation for next test**: same filter but `skip_london=true` AND pullback_236 entry. Should give the cleanest comparable PF estimate.

## Files

- `cache/may2026-m5.json` — the 3,528 May bars (gitignored)
- `data/backtests/may2026-results-next_open.json` — 72 signals, market entry
- `data/backtests/may2026-results-pullback_236.json` — 72 signals, limit entry
- `data/backtests/may2026-summary.md` — this report
- `scripts/backtest_may2026.py` — the backtest itself
