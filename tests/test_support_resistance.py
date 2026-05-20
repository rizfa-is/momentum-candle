"""Tests for support_resistance.py.

Synthetic candles only, no live MT5. Uses a stub fetcher injected via
the private ``_fetch_candles`` parameter on ``find_major_levels``.
"""

from __future__ import annotations

from typing import Any

from mt5_mvp.strategies.support_resistance import (
    _cluster_pivots,
    _detect_pivots,
    find_major_levels,
)


def make_bar(
    t: int,
    o: float,
    h: float,
    lo: float,
    c: float,
    v: int = 1000,
) -> dict[str, Any]:
    return {
        "time": t,
        "open": o,
        "high": h,
        "low": lo,
        "close": c,
        "tick_volume": v,
        "spread": 80,
        "real_volume": 0,
    }


def baseline(n: int, base: float = 100.0, step: int = 60) -> list[dict[str, Any]]:
    """Mostly-flat baseline candles used to pad histories."""
    out = []
    price = base
    t = 1700000000
    for _i in range(n):
        out.append(make_bar(t=t, o=price, h=price + 0.1, lo=price - 0.1, c=price))
        t += step
    return out


# --- Helpers --------------------------------------------------------------


def _stub_fetch(by_tf: dict[str, list[dict[str, Any]]]):
    """Return a fetcher closure that returns candles for the given TF."""

    def fetch(symbol: str, timeframe: str, count: int) -> Any:
        candles = by_tf.get(timeframe)
        if candles is None:
            return {"error": f"no stub for {timeframe}"}
        # Mimic real MT5 behavior: oldest first, capped at count.
        return candles[-count:]

    return fetch


# --- Pivot detection ------------------------------------------------------


def test_pivot_detection_basic():
    candles = baseline(30)
    # Inject a clear pivot high at index 15.
    candles[15] = make_bar(t=candles[15]["time"], o=100.0, h=120.0, lo=99.5, c=100.2)
    highs, _lows = _detect_pivots(candles, pivot_left=5, pivot_right=5)
    pivot_high_indices = {p[1] for p in highs}
    assert 120.0 in pivot_high_indices, f"expected 120.0 in pivots, got {pivot_high_indices}"


# --- Clustering -----------------------------------------------------------


def test_cluster_merges_nearby_pivots():
    pivots = [
        (1700000000, 100.0),
        (1700000060, 100.3),
        (1700000120, 100.6),
    ]
    levels = _cluster_pivots(
        pivots,
        cluster_radius=0.5,
        min_touches=3,
        tier="M5",
        level_type="swing",
    )
    assert len(levels) == 1
    assert levels[0].weight == 3
    assert 100.0 <= levels[0].price <= 100.6


def test_min_touches_rejects_singletons():
    pivots = [(1700000000, 100.0)]
    levels = _cluster_pivots(
        pivots,
        cluster_radius=0.5,
        min_touches=3,
        tier="M5",
        level_type="swing",
    )
    assert levels == []


# --- Escalation -----------------------------------------------------------


def _make_one_sided_candles(n: int, current_price: float) -> list[dict[str, Any]]:
    """Build n candles that produce pivot highs ABOVE current_price only.

    Uses a slowly drifting baseline with three clear pivot highs at
    +5 / +6 / +7 USD above current_price. No pivot lows below price.
    """
    out: list[dict[str, Any]] = []
    t = 1700000000
    base = current_price
    for _i in range(n):
        out.append(make_bar(t=t, o=base, h=base + 0.05, lo=base - 0.05, c=base))
        t += 300

    # Inject pivot highs at indices 50, 100, 150 with prices well above.
    for idx, offset in ((50, 5.0), (100, 5.1), (150, 5.2)):
        if idx < n:
            base_p = out[idx]["open"]
            out[idx] = make_bar(
                t=out[idx]["time"],
                o=base_p,
                h=base_p + offset,
                lo=base_p - 0.05,
                c=base_p,
            )
    return out


def test_escalation_fires_when_one_sided():
    """When the M5 scan finds pivots only above current price, the
    M15 tier should be queried."""
    n = 200
    current_price = 100.0
    m5 = _make_one_sided_candles(n, current_price)

    # M15 has both-sides pivots so escalation can resolve.
    m15 = _make_one_sided_candles(n, current_price)
    for idx, drop in ((30, 5.0), (80, 5.1), (140, 5.2)):
        base_p = m15[idx]["open"]
        m15[idx] = make_bar(
            t=m15[idx]["time"],
            o=base_p,
            h=base_p + 0.05,
            lo=base_p - drop,
            c=base_p,
        )

    fetch = _stub_fetch({"M5": m5, "M15": m15, "D1": []})

    out = find_major_levels(
        symbol="TEST",
        timeframe="M5",
        lookback=200,
        cluster_atr_mult=2.0,
        min_touches=3,
        pivot_left=5,
        pivot_right=5,
        use_escalation=True,
        max_tier=2,
        include_round=False,
        include_multi_tf_extremes=False,
        _fetch_candles=fetch,
        _current_price=current_price,
        _current_time=1700060000,
    )
    assert "M5" in out["tiers_scanned"]
    assert "M15" in out["tiers_scanned"]
    assert out["escalation_triggered"] is True


def test_escalation_stops_when_both_sides_covered():
    """When M5 already has both-sides coverage, M15 should NOT be scanned."""
    n = 200
    current_price = 100.0
    m5 = _make_one_sided_candles(n, current_price)
    # Add lows below current price too.
    for idx, offset in ((30, 5.0), (80, 5.1), (140, 5.2)):
        base_p = m5[idx]["open"]
        m5[idx] = make_bar(
            t=m5[idx]["time"],
            o=base_p,
            h=base_p + 0.05,
            lo=base_p - offset,
            c=base_p,
        )

    fetch = _stub_fetch({"M5": m5, "M15": [], "D1": []})

    out = find_major_levels(
        symbol="TEST",
        timeframe="M5",
        lookback=200,
        cluster_atr_mult=2.0,
        min_touches=3,
        pivot_left=5,
        pivot_right=5,
        use_escalation=True,
        max_tier=2,
        include_round=False,
        include_multi_tf_extremes=False,
        _fetch_candles=fetch,
        _current_price=current_price,
        _current_time=1700060000,
    )
    assert out["tiers_scanned"] == ["M5"]
    assert out["escalation_triggered"] is False


# --- Dedupe ---------------------------------------------------------------


def test_dedupe_prefers_lower_tier():
    """Same price level appearing in M5 and H1 keeps M5 (lower tier)."""
    n = 200
    current_price = 100.0

    # Both tiers have pivots clustering around price+5 and price-5.
    def make_two_sided() -> list[dict[str, Any]]:
        c = _make_one_sided_candles(n, current_price)
        for idx, offset in ((30, 5.0), (80, 5.1), (140, 5.2)):
            base_p = c[idx]["open"]
            c[idx] = make_bar(
                t=c[idx]["time"],
                o=base_p,
                h=base_p + 0.05,
                lo=base_p - offset,
                c=base_p,
            )
        return c

    m5 = make_two_sided()
    h1 = make_two_sided()

    fetch = _stub_fetch({"M5": m5, "M15": [], "H1": h1, "D1": []})

    out = find_major_levels(
        symbol="TEST",
        timeframe="M5",
        lookback=200,
        cluster_atr_mult=2.0,
        min_touches=3,
        pivot_left=5,
        pivot_right=5,
        use_escalation=False,  # already two-sided on M5; no escalation
        max_tier=5,
        include_round=False,
        include_multi_tf_extremes=False,
        _fetch_candles=fetch,
        _current_price=current_price,
        _current_time=1700060000,
    )
    tiers = {L["tier"] for L in out["levels"]}
    assert tiers == {"M5"}, f"expected only M5 levels, got {tiers}"
