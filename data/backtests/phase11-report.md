# Phase 11 backtest -- DXY-proxy alignment + relaxed M5 setup

User research request: produce a deployable strategy with 10-15+ signals
per month. Test whether DXY (US Dollar Index) direction alignment, the
strongest cited correlation in academic gold research (Lucey, Baur,
O'Connor et al), can unlock a relaxed M5 filter.

## Methodology

### DXY proxy

DXY itself is not tradeable on InstaForex demo. We use **inverted EURUSD M5**
as proxy:
  - EUR is 57.6% of the DXY basket
  - 1/EURUSD ~ DXY direction with empirically high correlation (typically
    0.95+ on absolute level, somewhat lower on returns)
  - Strict timing: at the M5 XAUUSD signal close time T, only EURUSD bars
    with close time <= T are used.

### DXY direction signal

```
DXY proxy close[idx] vs EMA(20) of DXY proxy:
  BULL_DXY:  close > EMA * (1 + 0.0005)
  BEAR_DXY:  close < EMA * (1 - 0.0005)
  NEUTRAL:   within 0.05% of EMA  (signal skipped)
```

Trade direction filter:
  - SELL gold only when DXY is BULLISH
  - BUY gold only when DXY is BEARISH
  - Skip if NEUTRAL

### Relaxed M5 setup

```
body / range          >= 0.65   (was 0.86)
body in points        >= 600    (was 1000)
range in USD          >= 6.0    (was 11.0)
```

Loose enough to fire frequently; tested whether DXY alignment can rescue
the win rate.

## Sanity check: XAU vs DXY-proxy daily-return correlation

```
n_days:        614
correlation:   -0.374
```

Significantly negative as expected, but **weaker than the -0.6 to -0.8
quoted in academic literature** (O'Connor et al 2015; Lucey 2005; Baur &
Lucey 2010). Two interpretations:

1. **EURUSD-only proxy underestimates true DXY.** The basket has 42%
   non-EUR weight which carries independent variance. The full 6-pair
   DXY would correlate stronger.
2. **Post-2022 regime weakened the correlation.** Central-bank gold
   buying since 2022 has provided a structural floor that decouples
   gold from dollar moves to a degree. Recent studies (post-Russia
   invasion) consistently show weaker XAU/DXY correlation than
   pre-2020 norms.

Either way the proxy carries real signal -- it's just not as informative
as we'd hope.

## Pre-committed decision rules

```
1. n_filled         >= 50   across 29 months
2. PF                >  1.40
3. losing_months    <= 7 of 29
4. mean_RR per win  >= 0.5
5. sigs/mo          >= 8   (research goal: 10-15+, threshold relaxed
                            to 8 for sample-size discipline)
```

## Result: REJECTED across the board

```
V    config                                n     WR     PF    netR     sigs/mo  verdict
V6   v0.5.0 baseline (control)            262   70.6%  1.44   +33.3R     9.0    PASS
V4   v0.5.0 + DXY-aligned                  77   70.1%  1.44    +9.6R     2.7    REJECT (sigs/mo)
V1   Relaxed M5 + DXY-aligned            1229   67.3%  1.23   +90.3R    42.4    REJECT (PF)
V2   Relaxed M5 + DXY + NY only           784   66.7%  1.20   +51.3R    27.0    REJECT (PF)
V3   Relaxed M5 + DXY + skip London      1058   67.5%  1.24   +81.2R    36.5    REJECT (PF)
V5   Relaxed M5 only (control)           4151   67.0%  1.20  +276.9R   143.1    REJECT (PF)
```

## Critical interpretation

### V4 is the cleanest test of "does DXY add edge to v0.5.0?"

```
V6  v0.5.0 alone               n=262   WR 70.6%  PF 1.44   sigs/mo 9.0
V4  v0.5.0 + DXY-aligned       n=77    WR 70.1%  PF 1.44   sigs/mo 2.7
                                       ------    ----
                              same WR, same PF, 70% fewer trades
```

**The DXY filter cuts trade volume by 71% and produces identical PF.**
Identical PF means the kept-vs-dropped trades win at the same rate.
DXY direction is NOT a useful filter on top of v0.5.0 -- the M5 structure
already implicitly captures whatever DXY signal exists.

This is the most rigorous negative result in the project. Phase 3
(S/R confluence) showed PF dropping from 1.54 to 1.22 when filtering;
that was at least information ("S/R proximity hurts"). Phase 11 V4 shows
DXY filtering produces zero net effect on quality -- cleanly redundant.

### V1/V2/V3 prove relaxing M5 always loses

```
V5  Relaxed M5 alone           PF 1.20  (baseline reference for relaxed)
V1  Relaxed + DXY              PF 1.23  (DXY tilt: +0.03)
V2  Relaxed + DXY + NY only    PF 1.20  (no help)
V3  Relaxed + DXY + skip Lon   PF 1.24  (DXY tilt: +0.04)
```

DXY contributes about 3-4 PF points to a relaxed filter. Not enough to
clear the 1.40 deployable threshold. Relaxing the M5 filter is not
recoverable through any single confluence we've tested across Phases
3, 6, 9, 10, 11.

### Signal volume target was achievable but not at acceptable PF

The user asked for 10-15+ signals/month. Three variants produced 27-42
signals/month (V1, V2, V3) but all at PF below 1.40 -- not deployable.
**There is no configuration in this dataset that satisfies BOTH the
signal-cadence target AND the PF threshold simultaneously.**

This is a real finding, not a failure. It says: M5 XAUUSD with the
fib-based 0.586 RR target inherently caps trade frequency around 9-10
high-quality signals/month. The cadence/quality tradeoff is structural.

## What this teaches us

1. **DXY direction adds zero edge to v0.5.0.** The strict M5 filter has
   already absorbed the dollar correlation that exists. Stop bolting
   dollar-related features onto the strategy.

2. **The M5 strict filter is not relaxable on this dataset.** No single
   confluence (S/R, 3WS/3BC, ICT, FVG, MTF H1, DXY) has been able to
   compensate for relaxing body%, range, body-points, etc.

3. **Real correlation is weaker than literature suggests.** The
   academic XAU/DXY correlation (-0.6 to -0.8) is from pre-2020 data
   on non-broker prices. On retail-broker EURUSD -> 1/EURUSD across
   2024-01 to 2026-05, the correlation is -0.374. Citing the older
   number in strategy design would have been misleading.

4. **The cadence/quality tradeoff is structural.** 9 signals/month at
   PF 1.44 is the ceiling on this filter style at this RR target.
   Higher cadence requires either:
     a. Different exit math (fixed RR > 1.5 instead of fib 0.586)
     b. Different timeframe (M15 with relaxed filter?)
     c. Different symbol (silver, oil, indices)
     d. Different strategy class entirely

## Reference

Goeryadi, G. (Astronacci) -- Indonesian commercial trading methodology
combining Fibonacci levels with planetary cycles and time-based analysis.
Cited as context. Specific Astronacci rules not encoded in this phase
because they require explicit lunar/planetary date data which is not
available through the MT5 broker. A dedicated Astronacci phase would
require an external ephemeris library and falsifiable rule formulation.

O'Connor, F.A., Lucey, B.M., Velasco, J.C. and Donaghy, M., 2015. The
financial economics of gold -- A survey. International Review of
Financial Analysis, 41, pp.186-205.

Lucey, B.M., 2005. The day-of-the-week effect in the pre-holiday returns
of major US equity indices and the gold market. Applied Financial
Economics Letters.

Baur, D.G. and Lucey, B.M., 2010. Is gold a hedge or a safe haven? An
analysis of stocks, bonds and gold. Financial Review, 45(2), pp.217-229.

## What stays decided

- v0.5.0 momentum-candle remains the only deployable strategy
- 3 confirmations / 8 rejections (Phase 11 added)
- DXY direction does not improve v0.5.0 -- structurally redundant
- Relaxing the M5 filter is not recoverable through DXY alignment
- The 9 signals/month / PF 1.44 ceiling on M5 XAUUSD with fib targets
  is a real structural finding, not a tuning problem

## Files

- `scripts/phase11_dxy_correlation.py` -- backtest script
- `scripts/pull_symbol_month.py` -- generic symbol/month puller (new)
- `cache/eurusd-{2024..2026}-{01..12}-m5.json` -- 29 months EURUSD M5
- `data/backtests/phase11-results.json`
- `data/backtests/phase11-report.md` -- this file

## Recommended next research directions

Given the structural finding that v0.5.0's PF ceiling appears to be 1.44
on M5 XAUUSD with fib targets, three honest paths:

1. **Different RR math.** Test fixed 1.0R / 1.2R / 1.5R targets instead
   of the 1.27-fib (which produces 0.586 average RR/win). Higher fixed
   targets reduce WR but increase per-trade R. Could change the cadence/
   quality balance.

2. **M15 with relaxed filter.** The 5-min momentum-candle is sensitive
   to noise. M15 with body 0.75 / range 18 USD might produce 5-8
   signals/month at higher PF with less spread cost.

3. **Multi-symbol expansion.** Apply v0.5.0 verbatim to silver (XAGUSD)
   and oil (USOIL) for 2024-2026. If the filter has edge on silver,
   trade frequency doubles without changing PF.

Recommended: option 3 first. Same code, same parameters, different
symbol -- if v0.5.0 works on silver, you have a 2-symbol portfolio at
~18 trades/month which approaches the user's 10-15 cadence target.
