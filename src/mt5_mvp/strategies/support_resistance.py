"""Major support/resistance level detection.

Implements the 3-component hybrid described in
`docs/strategies/support-resistance.md`:

  1. Swing-pivot detection (fractal-based)
  2. Cluster + touch-count aggregation
  3. Static levels (multi-timeframe extremes + round numbers)

Plus one-sided escalation: when the current timeframe scan only
surfaces levels above (or below) the current price, the algorithm
escalates to higher timeframes (M5 -> M15 -> H1 -> H4 -> D1) until
both sides are covered or the ladder is exhausted.

Public API:
    Level                 dataclass for a single S/R level
    find_major_levels()   detect S/R for a symbol with auto-escalation
    levels_near_price()   filter levels within a band around a price

The module reads candle data via ``mt5_mvp.market.get_candles_latest``,
so it works the same in unit tests (mocked MetaTrader5) and in the
live MCP server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .. import market

log = logging.getLogger("mt5mcp")

# Tier ladder for one-sided escalation.
TIER_LADDER: list[str] = ["M5", "M15", "H1", "H4", "D1"]


# --- Level dataclass ------------------------------------------------------


@dataclass(slots=True)
class Level:
    """A single major support or resistance level."""

    price: float
    weight: int
    type: str
    tier: str
    first_touch_time: int | None = None
    last_touch_time: int | None = None

    def to_dict(self, current_price: float | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "price": round(self.price, 5),
            "weight": int(self.weight),
            "type": self.type,
            "tier": self.tier,
        }
        if self.first_touch_time is not None:
            out["first_touch_time"] = int(self.first_touch_time)
        if self.last_touch_time is not None:
            out["last_touch_time"] = int(self.last_touch_time)
        if current_price is not None:
            out["distance_pts"] = round(self.price - current_price, 5)
            out["side"] = "support" if self.price < current_price else "resistance"
        return out


# --- ATR helper -----------------------------------------------------------


def _wilder_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """Wilder ATR aligned to candles. None where ATR is undefined."""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out

    trs: list[float] = []
    for i in range(1, period + 1):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    atr = sum(trs) / period
    out[period] = atr

    for i in range(period + 1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        atr = (atr * (period - 1) + tr) / period
        out[i] = atr
    return out


def _last_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> float | None:
    series = _wilder_atr(highs, lows, closes, period)
    for v in reversed(series):
        if v is not None:
            return v
    return None


# --- Pivot detection ------------------------------------------------------


def _detect_pivots(
    candles: list[dict[str, Any]],
    pivot_left: int,
    pivot_right: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return (highs, lows) where each entry is (epoch_time, price).

    A bar is a pivot high if its high is >= max(prior pivot_left highs)
    AND >= max(next pivot_right highs). Mirror for lows.
    """
    n = len(candles)
    pivot_highs: list[tuple[int, float]] = []
    pivot_lows: list[tuple[int, float]] = []
    if n < pivot_left + pivot_right + 1:
        return pivot_highs, pivot_lows

    for i in range(pivot_left, n - pivot_right):
        h = candles[i]["high"]
        lo = candles[i]["low"]
        left_high = max(candles[j]["high"] for j in range(i - pivot_left, i))
        right_high = max(candles[j]["high"] for j in range(i + 1, i + 1 + pivot_right))
        left_low = min(candles[j]["low"] for j in range(i - pivot_left, i))
        right_low = min(candles[j]["low"] for j in range(i + 1, i + 1 + pivot_right))

        # Strict comparisons: a flat plateau is NOT a pivot.
        if h > left_high and h > right_high:
            pivot_highs.append((int(candles[i]["time"]), float(h)))
        if lo < left_low and lo < right_low:
            pivot_lows.append((int(candles[i]["time"]), float(lo)))
    return pivot_highs, pivot_lows


# --- Clustering -----------------------------------------------------------


def _cluster_pivots(
    pivots: list[tuple[int, float]],
    cluster_radius: float,
    min_touches: int,
    tier: str,
    level_type: str = "swing",
) -> list[Level]:
    """Greedy-merge pivots within ``cluster_radius`` of each other."""
    if not pivots or cluster_radius <= 0:
        return []

    # Sort pivots by price.
    by_price = sorted(pivots, key=lambda p: p[1])
    clusters: list[list[tuple[int, float]]] = []
    current: list[tuple[int, float]] = [by_price[0]]
    for t, p in by_price[1:]:
        # Compare against the cluster's running mean for stability.
        mean = sum(x[1] for x in current) / len(current)
        if abs(p - mean) <= cluster_radius:
            current.append((t, p))
        else:
            clusters.append(current)
            current = [(t, p)]
    clusters.append(current)

    levels: list[Level] = []
    for cluster in clusters:
        if len(cluster) < min_touches:
            continue
        prices = [p for _, p in cluster]
        times = [t for t, _ in cluster]
        levels.append(
            Level(
                price=sum(prices) / len(prices),
                weight=len(cluster),
                type=level_type,
                tier=tier,
                first_touch_time=min(times),
                last_touch_time=max(times),
            )
        )
    return levels


# --- Static levels --------------------------------------------------------


def _round_levels(
    current_price: float,
    step: float,
    radius: float,
) -> list[Level]:
    """Return round-number levels (multiples of ``step``) within
    ``radius`` USD of the current price."""
    if step <= 0:
        return []
    nearest = round(current_price / step) * step
    out: list[Level] = []
    k = 0
    while True:
        offsets = [nearest + k * step, nearest - k * step] if k > 0 else [nearest]
        any_in_band = False
        for p in offsets:
            if abs(p - current_price) <= radius:
                out.append(Level(price=p, weight=1, type="round_50", tier="static"))
                any_in_band = True
        if not any_in_band:
            break
        k += 1
        if k > 50:
            break
    return out


def _multi_tf_extremes(symbol: str, current_time: int) -> list[Level]:
    """Pull D1 candles to derive day_high/low, prior_day_high/low, and
    week_high/low. Best-effort; returns [] on failure."""
    out: list[Level] = []
    try:
        d1 = market.get_candles_latest(symbol=symbol, timeframe="D1", count=10)
    except Exception:
        log.exception("D1 fetch failed for multi-TF extremes")
        return out

    if isinstance(d1, dict) or not d1:
        return out

    # Newest first usage: get_candles_latest returns oldest-first per
    # MetaTrader5 convention, so the last entry is the most recent.
    d1_sorted = sorted(d1, key=lambda b: b["time"])
    today = d1_sorted[-1]
    out.append(Level(price=float(today["high"]), weight=1, type="day_high", tier="D1"))
    out.append(Level(price=float(today["low"]), weight=1, type="day_low", tier="D1"))

    if len(d1_sorted) >= 2:
        prior = d1_sorted[-2]
        out.append(
            Level(
                price=float(prior["high"]),
                weight=1,
                type="prior_day_high",
                tier="D1",
            )
        )
        out.append(
            Level(
                price=float(prior["low"]),
                weight=1,
                type="prior_day_low",
                tier="D1",
            )
        )

    if len(d1_sorted) >= 5:
        last5 = d1_sorted[-5:]
        out.append(
            Level(
                price=max(float(b["high"]) for b in last5),
                weight=1,
                type="week_high",
                tier="D1",
            )
        )
        out.append(
            Level(
                price=min(float(b["low"]) for b in last5),
                weight=1,
                type="week_low",
                tier="D1",
            )
        )
    return out


# --- Tier scan ------------------------------------------------------------


def _scan_tier(
    symbol: str,
    timeframe: str,
    lookback: int,
    cluster_atr_mult: float,
    min_touches: int,
    pivot_left: int,
    pivot_right: int,
    fetch_candles: Any = None,
) -> tuple[list[Level], float | None]:
    """Scan one timeframe. Returns (swing_levels, atr_value).

    ``fetch_candles`` lets tests inject a stub; defaults to
    ``mt5_mvp.market.get_candles_latest``.
    """
    fetch = fetch_candles or market.get_candles_latest
    candles = fetch(symbol=symbol, timeframe=timeframe, count=lookback)
    if isinstance(candles, dict) or not candles:
        return [], None
    candles = sorted(candles, key=lambda b: b["time"])

    highs = [float(b["high"]) for b in candles]
    lows = [float(b["low"]) for b in candles]
    closes = [float(b["close"]) for b in candles]
    atr = _last_atr(highs, lows, closes)
    if atr is None or atr <= 0:
        return [], None

    cluster_radius = cluster_atr_mult * atr
    pivot_highs, pivot_lows = _detect_pivots(candles, pivot_left, pivot_right)
    pivots = pivot_highs + pivot_lows

    levels = _cluster_pivots(
        pivots, cluster_radius, min_touches, tier=timeframe, level_type="swing"
    )
    return levels, atr


# --- Coverage / dedupe ----------------------------------------------------


def _has_both_sides(levels: list[Level], price: float, min_touches: int) -> bool:
    has_above = any(L.price > price and L.weight >= min_touches for L in levels)
    has_below = any(L.price < price and L.weight >= min_touches for L in levels)
    return has_above and has_below


def _dedupe_keep_lowest_tier(
    levels: list[Level],
    cluster_radius: float,
) -> list[Level]:
    """Two levels at near-identical prices keep the lower tier
    (more recent, more specific). Tier ranking: M5 < M15 < H1 < H4 < D1
    < static."""
    tier_rank = {"M5": 0, "M15": 1, "H1": 2, "H4": 3, "D1": 4, "static": 5}
    if cluster_radius <= 0:
        return levels

    by_price = sorted(levels, key=lambda L: (L.price, tier_rank.get(L.tier, 99)))
    kept: list[Level] = []
    for L in by_price:
        merged = False
        for K in kept:
            if abs(L.price - K.price) <= cluster_radius:
                if tier_rank.get(L.tier, 99) < tier_rank.get(K.tier, 99):
                    K.price = L.price
                    K.tier = L.tier
                    K.type = L.type
                    K.first_touch_time = L.first_touch_time
                    K.last_touch_time = L.last_touch_time
                K.weight = max(K.weight, L.weight)
                merged = True
                break
        if not merged:
            kept.append(L)
    return kept


# --- Public API -----------------------------------------------------------


def find_major_levels(
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    lookback: int = 500,
    cluster_atr_mult: float = 0.5,
    min_touches: int = 3,
    pivot_left: int = 10,
    pivot_right: int = 10,
    use_escalation: bool = True,
    max_tier: int = 5,
    include_round: bool = True,
    round_step: float = 50.0,
    include_multi_tf_extremes: bool = True,
    _fetch_candles: Any = None,
    _current_price: float | None = None,
    _current_time: int | None = None,
) -> dict[str, Any]:
    """Find major S/R levels with one-sided escalation.

    Returns a dict shaped like::

        {
            "current_price": 4555.20,
            "current_time_utc": 1716207000,
            "atr14": 3.12,
            "tiers_scanned": ["M5", "M15"],
            "escalation_triggered": True,
            "levels": [Level, ...]
        }
    """
    if timeframe not in TIER_LADDER:
        raise ValueError(f"timeframe must be one of {TIER_LADDER}, got {timeframe!r}")
    start_idx = TIER_LADDER.index(timeframe)
    cap_idx = max(start_idx, min(max_tier - 1, len(TIER_LADDER) - 1))

    fetch = _fetch_candles or market.get_candles_latest

    # Determine current price/time. If caller supplied them (used by
    # tests), trust those; else fetch the most recent bar of the start tier.
    current_price = _current_price
    current_time = _current_time
    if current_price is None or current_time is None:
        bootstrap = fetch(symbol=symbol, timeframe=timeframe, count=2)
        if isinstance(bootstrap, dict) or not bootstrap:
            return {
                "error": "could not bootstrap current price",
                "tiers_scanned": [],
                "levels": [],
            }
        last = sorted(bootstrap, key=lambda b: b["time"])[-1]
        current_price = float(last["close"])
        current_time = int(last["time"])

    tiers_scanned: list[str] = []
    swing_levels: list[Level] = []
    last_atr: float | None = None

    for idx in range(start_idx, cap_idx + 1):
        tf = TIER_LADDER[idx]
        tier_levels, tier_atr = _scan_tier(
            symbol=symbol,
            timeframe=tf,
            lookback=lookback,
            cluster_atr_mult=cluster_atr_mult,
            min_touches=min_touches,
            pivot_left=pivot_left,
            pivot_right=pivot_right,
            fetch_candles=fetch,
        )
        tiers_scanned.append(tf)
        swing_levels.extend(tier_levels)
        if tier_atr is not None:
            last_atr = tier_atr
        if not use_escalation:
            break
        if _has_both_sides(swing_levels, current_price, min_touches):
            break

    # Inject static levels (round + multi-TF extremes) once, after the
    # tier scan. These are always added regardless of escalation.
    if include_multi_tf_extremes:
        swing_levels.extend(_multi_tf_extremes(symbol, current_time))
    if include_round and last_atr:
        radius = last_atr * 20  # show round levels within ~20 ATRs of price
        swing_levels.extend(_round_levels(current_price, round_step, radius))

    # Dedupe: drop near-duplicate levels keeping the lower tier.
    cluster_radius = (last_atr or 0.0) * cluster_atr_mult
    deduped = _dedupe_keep_lowest_tier(swing_levels, cluster_radius)

    # Sort by absolute distance from current price.
    deduped.sort(key=lambda L: abs(L.price - current_price))

    return {
        "current_price": round(current_price, 5),
        "current_time_utc": int(current_time),
        "atr14": round(last_atr, 5) if last_atr else None,
        "tiers_scanned": tiers_scanned,
        "escalation_triggered": len(tiers_scanned) > 1,
        "levels": [L.to_dict(current_price) for L in deduped],
    }


def levels_near_price(
    levels: list[Level],
    price: float,
    band: float,
) -> list[Level]:
    """Filter ``levels`` to those within ``band`` price units of ``price``."""
    if band <= 0:
        return []
    return [L for L in levels if abs(L.price - price) <= band]
