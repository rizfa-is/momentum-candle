---
name: support-resistance
description: Major support/resistance level detection. Use when discussing S/R, key levels, pivots, swing highs/lows, round numbers, or anything in src/mt5_mvp/strategies/support_resistance.py. Auto-escalates from M5 to higher timeframes when only one side of price has coverage.
---

# Major support/resistance — what we use

## The 3-component hybrid

| Component | What it captures |
|---|---|
| Swing-pivot detection (fractal) | Local highs/lows that confirmed N bars later |
| Cluster + touch-count | Multiple pivots near the same price = stronger level |
| Static levels | Day/week extremes from D1, plus round-number levels |

## One-sided escalation

The clever bit: if the M5 scan only finds levels above (or below) the
current price, the algorithm escalates through the timeframe ladder
**M5 → M15 → H1 → H4 → D1** until both sides are covered or the
ladder is exhausted.

Trigger:
```python
def has_both_sides(levels, price, min_touches):
    has_above = any(L.price > price and L.weight >= min_touches for L in levels)
    has_below = any(L.price < price and L.weight >= min_touches for L in levels)
    return has_above and has_below
```

Cap with `max_tier` (default 5 = D1, set to 1 to disable).

## Dedupe across tiers

When a level appears in both M5 and H1 at near-identical price, keep
the **M5** entry (lower tier wins). M5 is more recent and more
specific to the current market structure.

## Calling from chat

> "What are the major S/R levels on XAUUSD right now?"

The agent calls:
```python
get_major_sr(symbol="XAUUSD", timeframe="M5")
```

Returns a dict with `current_price`, `atr14`, `tiers_scanned`,
`escalation_triggered`, and `levels` sorted by distance from price.

Each level has:
- `price` — the level value
- `weight` — touch count (3+ for swings, 1 for static levels)
- `type` — `swing` / `day_high` / `prior_day_low` / `week_high` /
  `round_50` / etc.
- `tier` — `M5` / `M15` / `H1` / `H4` / `D1` / `static`
- `distance_pts` — signed distance from current price
- `side` — `support` (below) or `resistance` (above)

## Default parameters

```
lookback              = 500     bars per tier
cluster_atr_mult      = 0.5     cluster radius = 0.5 × ATR(14)
min_touches           = 3       minimum pivots in cluster
pivot_left            = 10
pivot_right           = 10      fractal-confirmation lag
use_escalation        = true
max_tier              = 5       up to D1
include_round         = true
round_step            = 50.0    XAUUSD $50 multiples
include_multi_tf      = true
```

## When to tweak defaults

| Goal | Adjust |
|---|---|
| Fewer, stronger levels | raise `min_touches` to 4 or 5 |
| More fine-grained zones | lower `cluster_atr_mult` to 0.3 |
| Bigger-picture S/R | raise `cluster_atr_mult` to 1.0 |
| Skip escalation | set `use_escalation=false` |
| Force higher TF | set `timeframe="H1"` |
| Ignore round numbers | set `include_round=false` |

## What this does NOT do

- **Volume profile** — out of scope; forex/CFD volume is unreliable.
- **ML-based scoring** — premature; no labeled training data.
- **Real-time level updates** — pivots have a `pivot_right` bar
  confirmation lag (default 10 bars = ~50 min on M5). The most
  recent levels are stale.

## Phase boundary

Phase 1 (this skill): Python module + MCP tool. AI agents query
levels via chat. Tested with synthetic candles.

Phase 2 (deferred): `MajorSupportResistance.mq5` chart indicator
with lines + zones, hot-cold tier coloring.

Phase 3+ (deferred): backtest study comparing
`optimized + pullback_236` with/without S/R confluence filter; if
positive, add `InpUseSrConfluence` to `MomentumCandle_OptimizedEA`.

## Reference

- Spec: `docs/strategies/support-resistance.md`
- Tests: `tests/test_support_resistance.py` (6 tests, synthetic data)
- Code: `src/mt5_mvp/strategies/support_resistance.py`
- MCP tool: `mt5_mvp.server.get_major_sr`
