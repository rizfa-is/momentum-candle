# May 2026 backtest -- factor analysis
Investigates which features separate TP2 winners from SL losers in the 72-signal May 2026 dataset.
Baseline WR -- next_open: 73.6%, pullback_236: 66.1%
Break-even WR needed -- next_open: 77.7%, pullback_236: 63.1%

---

# Categorical / boolean factors

## Session (`session`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| Asia | 21 | 71.4% | -2.2pp | 18 | 66.7% | +0.5pp |
| London | 10 | 60.0% | -13.6pp | 9 | 55.6% | -10.6pp |
| NY | 41 | 78.0% | +4.4pp | 38 | 68.4% | +2.3pp |

## Engulfs prior bar (`engulfs_prior`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 41 | 78.0% | +4.4pp | 38 | 68.4% | +2.3pp |
| Yes | 31 | 67.7% | -5.9pp | 27 | 63.0% | -3.2pp |

## Trend aligned (prior 8 bars) (`trend_aligned`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 42 | 76.2% | +2.6pp | 39 | 69.2% | +3.1pp |
| Yes | 30 | 70.0% | -3.6pp | 26 | 61.5% | -4.6pp |

## Trend against (prior 8 bars) (`trend_against`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 30 | 70.0% | -3.6pp | 26 | 61.5% | -4.6pp |
| Yes | 42 | 76.2% | +2.6pp | 39 | 69.2% | +3.1pp |

## Near round 10 (within 2 USD) (`near_round_10`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 48 | 72.9% | -0.7pp | 43 | 62.8% | -3.4pp |
| Yes | 24 | 75.0% | +1.4pp | 22 | 72.7% | +6.6pp |

## Near round 50 (within 5 USD) (`near_round_50`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 55 | 72.7% | -0.9pp | 51 | 64.7% | -1.4pp |
| Yes | 17 | 76.5% | +2.9pp | 14 | 71.4% | +5.3pp |

## At day high (BUY) / day low (SELL) (`at_day_low`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 60 | 75.0% | +1.4pp | 55 | 67.3% | +1.1pp |
| Yes | 12 | 66.7% | -6.9pp | 10 | 60.0% | -6.2pp |

## Against day extreme (BUY at day high / SELL at day low) (`at_day_high`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 60 | 73.3% | -0.3pp | 55 | 65.5% | -0.7pp |
| Yes | 12 | 75.0% | +1.4pp | 10 | 70.0% | +3.8pp |

## Early session (first hour) (`early_session`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| No | 56 | 75.0% | +1.4pp | 51 | 68.6% | +2.5pp |
| Yes | 16 | 68.8% | -4.9pp | 14 | 57.1% | -9.0pp |

---

# Numeric factors

## Body % (`body_pct`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0.80-0.85 | 10 | 50.0% | -23.6pp | 9 | 44.4% | -21.7pp |
| 0.85-0.90 | 23 | 69.6% | -4.0pp | 21 | 61.9% | -4.2pp |
| 0.90-0.95 | 18 | 88.9% | +15.3pp | 17 | 88.2% | +22.1pp |
| 0.95-1.00 | 21 | 76.2% | +2.6pp | 18 | 61.1% | -5.0pp |

## Close-wick % (`close_wick_pct`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0-2% | 22 | 68.2% | -5.4pp | 20 | 55.0% | -11.1pp |
| 2-5% | 27 | 74.1% | +0.5pp | 22 | 68.2% | +2.0pp |
| 5-8% | 14 | 85.7% | +12.1pp | 14 | 78.6% | +12.4pp |
| 8-10% | 9 | 66.7% | -6.9pp | 9 | 66.7% | +0.5pp |

## Far-wick % (`far_wick_pct`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0-2% | 25 | 84.0% | +10.4pp | 23 | 73.9% | +7.8pp |
| 2-5% | 14 | 71.4% | -2.2pp | 13 | 69.2% | +3.1pp |
| 5-10% | 18 | 77.8% | +4.2pp | 16 | 68.8% | +2.6pp |
| 10-20% | 15 | 53.3% | -20.3pp | 13 | 46.2% | -20.0pp |
| >20% | 0 | 0.0% | +0.0pp | 0 | 0.0% | +0.0pp |

## Body in points (`body_points`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 800-1000 | 37 | 62.2% | -11.4pp | 35 | 54.3% | -11.9pp |
| 1000-1300 | 23 | 78.3% | +4.7pp | 20 | 70.0% | +3.8pp |
| 1300-1700 | 10 | 100.0% | +26.4pp | 8 | 100.0% | +33.9pp |
| >1700 | 2 | 100.0% | +26.4pp | 2 | 100.0% | +33.9pp |

## Range (`range`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 8-11 | 34 | 61.8% | -11.8pp | 32 | 53.1% | -13.0pp |
| 11-14 | 23 | 78.3% | +4.7pp | 21 | 71.4% | +5.3pp |
| 14-18 | 13 | 92.3% | +18.7pp | 10 | 90.0% | +23.9pp |
| >18 | 2 | 100.0% | +26.4pp | 2 | 100.0% | +33.9pp |

## R5 (range / mean prior 5) (`R5`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| <1.0 | 6 | 83.3% | +9.7pp | 6 | 83.3% | +17.2pp |
| 1.0-1.5 | 25 | 72.0% | -1.6pp | 23 | 60.9% | -5.3pp |
| 1.5-2.5 | 29 | 72.4% | -1.2pp | 26 | 65.4% | -0.8pp |
| >2.5 | 12 | 75.0% | +1.4pp | 10 | 70.0% | +3.8pp |

## V5 (volume / mean prior 5) (`V5`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| <0.9 | 8 | 75.0% | +1.4pp | 8 | 75.0% | +8.9pp |
| 0.9-1.2 | 38 | 76.3% | +2.7pp | 36 | 69.4% | +3.3pp |
| 1.2-1.6 | 23 | 65.2% | -8.4pp | 19 | 52.6% | -13.5pp |
| >1.6 | 3 | 100.0% | +26.4pp | 2 | 100.0% | +33.9pp |

## Range / ATR(14) (`range_over_atr`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| <1.0 | 2 | 100.0% | +26.4pp | 2 | 100.0% | +33.9pp |
| 1.0-1.5 | 28 | 67.9% | -5.8pp | 26 | 65.4% | -0.8pp |
| 1.5-2.5 | 38 | 73.7% | +0.1pp | 35 | 62.9% | -3.3pp |
| >2.5 | 4 | 100.0% | +26.4pp | 2 | 100.0% | +33.9pp |

## Trend monotonic count (prior 7 transitions) (`trend_monotonic`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0-2 | 18 | 83.3% | +9.7pp | 16 | 75.0% | +8.9pp |
| 3-4 | 42 | 71.4% | -2.2pp | 40 | 65.0% | -1.1pp |
| 5-6 | 12 | 66.7% | -6.9pp | 9 | 55.6% | -10.6pp |
| 7 | 0 | 0.0% | +0.0pp | 0 | 0.0% | +0.0pp |

## Distance to nearest 10 (`dist_to_round_10`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0-1 | 15 | 66.7% | -6.9pp | 14 | 64.3% | -1.9pp |
| 1-3 | 25 | 76.0% | +2.4pp | 23 | 69.6% | +3.4pp |
| 3-5 | 32 | 75.0% | +1.4pp | 28 | 64.3% | -1.9pp |
| >5 | 0 | 0.0% | +0.0pp | 0 | 0.0% | +0.0pp |

## Distance to nearest 50 (`dist_to_round_50`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| 0-5 | 17 | 76.5% | +2.9pp | 14 | 71.4% | +5.3pp |
| 5-15 | 29 | 93.1% | +19.5pp | 26 | 84.6% | +18.5pp |
| 15-30 | 26 | 50.0% | -23.6pp | 25 | 44.0% | -22.1pp |
| >30 | 0 | 0.0% | +0.0pp | 0 | 0.0% | +0.0pp |

## Dominance (range / max prior-5 same-dir range) (`dominance_max5`)

| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |
|---|---:|---:|---:|---:|---:|---:|
| <1.0 | 15 | 73.3% | -0.3pp | 14 | 64.3% | -1.9pp |
| 1.0-1.5 | 20 | 75.0% | +1.4pp | 18 | 66.7% | +0.5pp |
| 1.5-2.5 | 20 | 70.0% | -3.6pp | 19 | 68.4% | +2.3pp |
| >2.5 | 17 | 76.5% | +2.9pp | 14 | 64.3% | -1.9pp |

---

# Best 2-factor combinations

Looking for non-trivial interactions where two filters together produce a high TP2 rate at meaningful sample size (>=8 trades).

| Filter | next_open n / WR | pullback n / WR |
|---|---|---|
| session=Asia AND engulfs_prior=True | 8 / 50.0% | 7 / 42.9% |
| session=Asia AND near_round_10=False | 14 / 78.6% | 11 / 72.7% |
| session=NY AND trend_against=False | 16 / 75.0% | 15 / 66.7% |
| session=NY AND at_day_low=False | 36 / 80.6% | 33 / 69.7% |
| session=Asia AND at_day_low=False | 15 / 66.7% | 14 / 64.3% |
| session=London | 10 / 60.0% | 9 / 55.6% |
| session=Asia | 21 / 71.4% | 18 / 66.7% |
| session=NY | 41 / 78.0% | 38 / 68.4% |
| near_round_10=False | 48 / 72.9% | 43 / 62.8% |
| trend_against=False | 30 / 70.0% | 26 / 61.5% |
| engulfs_prior=True | 31 / 67.7% | 27 / 63.0% |
| at_day_low=False | 60 / 75.0% | 55 / 67.3% |
| session=Asia AND trend_against=False | 9 / 66.7% | 7 / 57.1% |
| session=NY AND near_round_10=False | 28 / 75.0% | 27 / 63.0% |
| session=Asia AND near_round_10=False AND trend_against=False | 6 / 83.3% | 4 / 75.0% |
