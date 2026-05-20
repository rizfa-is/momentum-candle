# Major support/resistance — algorithm spec

The `mt5_mvp.strategies.support_resistance` module finds major S/R
levels for a symbol using a 3-component hybrid plus one-sided
escalation across timeframes.

## Three components

### 1. Swing-pivot detection (fractal-based)

A bar at index `i` is a pivot high when:
```
high[i] > max(high[i - pivot_left .. i - 1])
   AND
high[i] > max(high[i + 1 .. i + pivot_right])
```
Strict `>` comparison so a flat plateau is **not** a pivot. Mirror
logic for pivot lows.

Default `pivot_left = pivot_right = 10` on M5 — meaning a level needs
10 bars on either side to be confirmed. The most recent 10 bars
cannot host a pivot (fractal-confirmation lag).

### 2. Cluster + touch-count

After detecting raw pivots, group nearby ones into "zones":

```
cluster_radius = cluster_atr_mult * ATR(14)
greedy-merge pivots within cluster_radius of the cluster's mean price
weight = number of pivots merged into this cluster
```

Defaults:
- `cluster_atr_mult = 0.5` (e.g. 1.5 USD on XAUUSD when ATR ≈ 3 USD)
- `min_touches = 3` (clusters with weight < 3 are discarded)

The cluster's reported `price` is the arithmetic mean of its pivots.
`first_touch_time` and `last_touch_time` track the time span the
cluster has been active.

### 3. Static levels (always included)

Two categories of "always real" levels are injected regardless of
swing-pivot scan results:

#### Multi-timeframe extremes (from D1 fetch)
- `day_high`, `day_low` — today's UTC range so far
- `prior_day_high`, `prior_day_low` — yesterday's range
- `week_high`, `week_low` — last 5 D1 bars

These are tier-tagged `D1` and weight=1.

#### Round-number levels
Multiples of `round_step` (default 50.0 USD) within ~20 ATRs of the
current price. Tier-tagged `static`, weight=1.

## One-sided escalation

The classical use case for escalation: M5 only shows S/R above the
current price (or only below). The algorithm needs to know "where will
price find a floor" but the M5 history doesn't show one.

### Trigger
```python
def has_both_sides(levels, price, min_touches):
    has_above = any(L.price > price and L.weight >= min_touches for L in levels)
    has_below = any(L.price < price and L.weight >= min_touches for L in levels)
    return has_above and has_below
```

### Ladder
```
M5 -> M15 -> H1 -> H4 -> D1
```

When the start tier (typically M5) does NOT have both-sides coverage,
the next tier is fetched and merged. The function returns levels from
**all** tiers attempted, not just the deepest one.

### Cap
`max_tier` (default 5 = D1) limits how far to climb. Set to 1 to
disable escalation entirely.

## Dedupe (cross-tier)

After merging tiers, levels at the same price keep the **lowest tier**
(M5 < M15 < H1 < H4 < D1 < static). Rationale: lower tiers are more
recent/specific. A swing low from M5 that aligns with a swing low from
H1 is more interesting as an M5 entry signal than as an H1 macro
level.

The dedupe radius is the same `cluster_atr_mult * ATR` used for the
within-tier clustering, so cross-tier merging respects the same
proximity rule.

## Result schema

```python
{
    "current_price": 4555.20,
    "current_time_utc": 1716207000,
    "atr14": 3.12,
    "tiers_scanned": ["M5", "M15"],
    "escalation_triggered": True,
    "levels": [
        {
            "price": 4555.50,
            "weight": 4,
            "type": "swing",
            "tier": "M5",
            "first_touch_time": 1716100000,
            "last_touch_time":  1716200000,
            "distance_pts": +0.30,
            "side": "resistance"
        },
        ...
    ]
}
```

Levels are sorted nearest-first by `abs(price - current_price)`.

## Calling from MCP

```
get_major_sr(symbol="XAUUSD", timeframe="M5")
```

Returns the dict above. AI agents can then ask follow-up questions
like "what's the nearest support" by reading the first entry with
`side == "support"`.

## Common parameter tweaks

| Goal | Adjust |
|---|---|
| Fewer, stronger levels | raise `min_touches` to 4 or 5 |
| More fine-grained zones | lower `cluster_atr_mult` to 0.3 |
| Bigger-picture S/R | raise `cluster_atr_mult` to 1.0 |
| Skip escalation | set `use_escalation=false` |
| Ignore round numbers | set `include_round=false` |
| Force higher TF | set `timeframe="H1"` |

## Limitations

1. **Pivot-confirmation lag.** A level is only confirmed
   `pivot_right` bars after the actual high/low. For real-time
   trading, the most recent levels are stale by ~50 minutes on M5.

2. **Volume profile not included.** True auction theory uses volume
   per price level. Forex CFDs lack reliable real volume; we omit it.
   Tick volume is too noisy on this broker (proven during eye-tag
   analysis).

3. **Self-fulfilling-prophecy levels.** Round numbers are real
   because retail traders cluster orders there. The detector will
   include them — but they tend to break with low residual reaction
   compared to swing-pivot levels.

4. **Newly-formed all-time highs/lows.** When a symbol just made a
   new range extreme, escalation will exhaust all tiers and return
   only one-sided coverage. This is correct behavior, not a bug.

5. **Computational cost.** Worst case is 5 tier scans of 500 bars =
   ~1 second per query. Fine for an interactive MCP tool, **not**
   fine for an MQL5 indicator without per-TF caching (Phase 2).

## Testing

`tests/test_support_resistance.py` covers:
- pivot detection on synthetic candles with known pivot at index 15
- cluster merge of three pivots within radius into one level
- min_touches rejection of singletons
- escalation fires when M5 is one-sided
- escalation does NOT fire when M5 has both sides
- dedupe keeps the lower tier when same price appears in M5 + H1

Run: `uv run pytest tests/test_support_resistance.py -v`

## Roadmap (post Phase 1)

- **Phase 2** — `MajorSupportResistance.mq5` indicator with line + zone
  rendering and hot-cold tier coloring
- **Phase 3** — `multi_month_backtest.py` extension comparing
  `optimized + pullback_236` performance with vs without S/R
  confluence filter
- **Phase 4** (conditional on Phase 3) — add `InpUseSrConfluence` to
  `MomentumCandle_OptimizedEA.mq5`
