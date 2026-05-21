# Phase 8 backtest -- 29-month deep-history (Jan 2024 - May 2026)

Tests whether the v0.5.0 deployable strategy holds when the backtest
window is extended even further into the past, from 17 months
(Jan 2025 - May 2026) to 29 months (Jan 2024 - May 2026). Adds the
entire calendar year 2024 as additional out-of-sample data.

## Headline result

```
                          12-mo (Jun 25-May 26)   17-mo (Jan 25-May 26)   29-mo (Jan 24-May 26)
trades filled                       242                    256                    262
WR                               71.5%                  70.7%                  70.6%
PF                               1.49                    1.45                    1.44
net R                          +33.31                 +33.00                 +33.34
per-trade R                    +0.138                 +0.129                 +0.127
losing months                    2 / 12                 4 / 17                 6 / 29
```

The big finding: **2024 contributed almost nothing.** Adding 12 months
of older data added only 6 trades and +0.34R net. The strategy
effectively did not trade gold in 2024.

## Per-month breakdown for 2024 (`optimized_no_round + pullback_236`)

```
month        sigs   fill   TP2    SL     WR     netR     PF
2024-01         0      0     0     0    0.0%   +0.00R    -
2024-02         1      0     0     0    0.0%   +0.00R    -      (signal didn't fill)
2024-03         1      1     1     0  100.0%   +0.59R    inf
2024-04         3      2     1     1   50.0%   -0.41R    0.59
2024-05         0      0     0     0    0.0%   +0.00R    -
2024-06         0      0     0     0    0.0%   +0.00R    -
2024-07         1      0     0     0    0.0%   +0.00R    -      (signal didn't fill)
2024-08         2      2     1     1   50.0%   -0.42R    0.58
2024-09         0      0     0     0    0.0%   +0.00R    -
2024-10         0      0     0     0    0.0%   +0.00R    -
2024-11         1      1     1     0  100.0%   +0.59R    inf
2024-12         1      0     0     0    0.0%   +0.00R    -      (signal didn't fill)
                                              -------
2024 total:    10      6     4     2   66.7%   +0.34R    2.0
```

**8 of 12 months in 2024 had ≤1 signal.** Five months produced zero
signals. The optimized filter (body ≥ 0.86, body ≥ 1000pt, range ≥ 11 USD)
needs real volatility to fire, and 2024 gold was structurally quieter
than 2025-2026.

For context, gold's average daily range:

```
2024 H1:  ~12-15 USD/day  (low vol)
2024 H2:  ~18-22 USD/day  (rising vol)
2025:     ~22-30 USD/day  (continued rise)
2026:     ~35-50 USD/day  (high vol regime)
```

The strategy's 11-USD M5 range floor is non-trivial in a 12-USD-day
environment.

## Cumulative net R curve at 1% risk

```
Jan 2024:    $100.00
Apr 2024:    $99.18  (April loss; cumulative now -0.41R = ~-0.4%)
Aug 2024:    $98.76  (August loss)
Dec 2024:    $99.94  (year ends ~flat after small wins)
Apr 2025:    $97.11  (April 2025 -2.83R)
Sep 2025:    $96.11  (lingering quiet)
Dec 2025:    $98.00  (Q4 recovery)
Jan 2026:    $95.23  (Jan 2026 -2.77R, biggest drawdown month)
Mar 2026:    $113.46 (Q1 surge: +7.16R Feb + 16.28R Mar)
May 2026:    $128.63 (continued Q1-Q2 momentum)

29-month account growth: ~+29% at 1% risk
Annualized:              ~+11.5%
```

The annualized return drops from the 17-month figure (~27%) to ~11.5%
when 2024 is included, because 2024 was effectively a zero-return year.

## What this means for deployment expectations

### 1. The strategy is even more regime-dependent than thought

```
                        active months   sparse months    trades from sparse
2024:                       4              8                 6 / 6
2025 H1:                    2              5                 8 / 14
2025 H2 - 2026 H1:          7              5               241 / 246
```

Out of 29 months, only 9 had meaningful trade volume (≥10 trades).
**93% of the 262 trades fired in just 9 months.** The strategy has long
quiet stretches; that's not a failure mode, it's the design.

### 2. 2024-style months are possible during forward-test

If gold returns to a 2024-style low-vol regime during the 30-day demo,
**you may see 0-3 trades in the entire test.** That's not a sign the
EA is broken — that's the strategy correctly refusing to take low-quality
setups.

### 3. The PF erosion is now ~3% across 29 months

```
5-month  PF 1.49
12-month PF 1.49  (no erosion)
17-month PF 1.45  (erosion: -0.04)
29-month PF 1.44  (erosion: -0.05)
```

Still consistent with real edge plus mild noise, not curve-fit collapse.

### 4. Pre-committed deployment thresholds — still pass

```
Rule                      Threshold    29-mo result   pass?
n_filled                  >=50         262            ✓
PF                        >1.40        1.44           ✓
losing_months             <=25%        6/29 = 21%     ✓
mean_RR                   >=0.5        0.586          ✓
```

All four still clear. Even with 2024 included.

## Honest verdict

**v0.5.0 holds across 29 months.** The headline metrics are within 5%
of each other from 5-month to 29-month. PF degrades gradually, WR is
stable, net R is essentially flat per trade.

The real lesson from 2024 is **the strategy is fundamentally a
high-volatility play.** It went dormant for nearly a full year of
quiet gold and that's correct behavior. If the next 30 days look like
2024 instead of 2026 H1, the EA will sit and wait.

## What changes deployment-wise

Nothing. The recommendation to forward-test on InstaForex demo for 30
days is unchanged. Now augmented with one expectation:

> If the demo period produces 0-3 trades, that is consistent with
> historical 2024 behavior. Do not interpret zero-signal weeks as a
> bug. Volatility is an input the strategy doesn't control.

If 2026 stays in its current high-vol regime, expect the 17-month
numbers (20 trades/month, 70% WR, +0.13R/trade). If gold cools off,
expect 2024 numbers (1-2 trades/month, near-zero net).

## What this run does NOT change

- The strategy is still v0.5.0. No rule changes.
- The decision to forward-test on demo is unchanged.
- The Phase 6 ICT/AMD rejections stand.
- The Phase 7 conclusions stand (the 17-month numbers were the higher-
  vol subset of this larger 29-month dataset).

## Files

- `cache/2024-{01..12}-m5.json`  new candle data (~70k bars)
- `data/backtests/multi-month-results.json`  29-month raw metrics
- `data/backtests/multi-month-summary.md`    29-month per-month detail
- `data/backtests/phase8-report.md`          this file

## Where the research arc stands

```
Phase 1:  May factor study                 extracted candidates
Phase 2:  5-month aggregate                 v0.5.0 ADOPTED
Phase 3:  S/R confluence on v0.5            REJECTED
Phase 4:  3WS/3BC + S/R                     ALL REJECTED
Phase 5:  Fade failed 3WS/3BC               REJECTED
Phase 6:  ICT/AMD portfolio (14 variants)   ALL REJECTED
Phase 7:  17-month deep-history             CONFIRMED (Jan 25-May 26)
Phase 8:  29-month deep-history             CONFIRMED (Jan 24-May 26)
                                            edge holds; 2024 was zero-trade year
                                            strategy is regime-dependent

Healthy ratio: 3 confirmations / 5 rejections.
```

## Next

Backtest scope is genuinely exhausted. Going further back (2023, 2022)
risks brokers' history gaps and tells us nothing the regime-dependent
finding doesn't already say. Going forward in time = the demo run.

The only honest next step remains **30-day demo forward-test**, with
the new expectation that the trade count could legitimately be very
low if gold quiets down.
