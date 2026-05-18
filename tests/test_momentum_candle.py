"""Tests for the momentum-candle strategy detector."""

from __future__ import annotations

from typing import Any

import pytest

from mt5_mvp.strategies import momentum_candle as mc
from mt5_mvp.strategies.base import rolling_sma, true_range, wilder_atr

# --- helpers --------------------------------------------------------------


def make_candle(
    *,
    t: int,
    o: float,
    h: float,
    lo: float,
    c: float,
    v: int = 10000,
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


def baseline_candles(n: int, *, base: float = 4500.0, vol: int = 10000) -> list[dict[str, Any]]:
    """Build ``n`` small-bodied baseline candles around ``base``."""
    out = []
    price = base
    for i in range(n):
        o = price
        h = price + 1.5
        lo = price - 1.5
        c = price + 0.5
        out.append(make_candle(t=1700000000 + i * 60, o=o, h=h, lo=lo, c=c, v=vol))
        price = c
    return out


# --- indicator unit tests -------------------------------------------------


def test_true_range_basic():
    assert true_range(prev_close=100, high=105, low=98) == 7
    assert true_range(prev_close=100, high=102, low=99) == 3
    assert true_range(prev_close=100, high=110, low=80) == 30


def test_wilder_atr_seeds_and_continues():
    # 30 bars, ranges expand toward the end.
    highs = [10 + i * 0.1 for i in range(30)]
    lows = [9 + i * 0.1 for i in range(30)]
    closes = [9.5 + i * 0.1 for i in range(30)]
    atr = wilder_atr(highs, lows, closes, period=14)
    assert atr[13] is None
    assert atr[14] is not None
    assert atr[29] is not None
    assert atr[29] > 0


def test_rolling_sma_aligned():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    sma = rolling_sma(vals, period=3)
    assert sma[0] is None
    assert sma[1] is None
    assert sma[2] == pytest.approx(2.0)
    assert sma[3] == pytest.approx(3.0)
    assert sma[4] == pytest.approx(4.0)


# --- scan: trigger detection ---------------------------------------------


def test_no_setups_when_history_too_short():
    candles = baseline_candles(10)
    assert mc.scan(candles) == []


def test_no_setup_when_no_momentum_candle():
    candles = baseline_candles(50)
    # add another baseline so the last bar (forming) is also boring
    candles.append(make_candle(t=1700001234, o=4500, h=4501, lo=4499, c=4500))
    assert mc.scan(candles) == []


def test_detects_bullish_momentum_breakout():
    # 30 tight baseline candles, then a strong bullish momentum candle, then
    # one boring forming bar (which the detector ignores).
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]

    # Big bullish candle: range 30, body 28 (93%), tiny upper wick.
    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        lo=last_close - 0.5,
        h=last_close + 30.0,
        c=last_close + 28.0,
        v=30000,  # 3x SMA20 of 10000 baseline
    )
    candles.append(momentum)

    # Forming bar (excluded from scan).
    forming = make_candle(
        t=1700000000 + 31 * 60,
        o=momentum["c"] if "c" in momentum else momentum["close"],
        lo=momentum["close"] - 1,
        h=momentum["close"] + 1,
        c=momentum["close"] + 0.5,
    )
    candles.append(forming)

    setups = mc.scan(candles, symbol="XAUUSD", timeframe="M15")
    assert len(setups) == 1
    s = setups[0]
    assert s.direction == "BUY"
    assert s.pattern in ("breakout", "trend", "pullback")
    assert s.body_pct >= 0.7
    assert s.range_atr_mult >= 1.0
    assert s.volume_ratio >= 1.5
    # Forming bar must not be the trigger.
    assert s.trigger_index == len(candles) - 2


def test_detects_bearish_momentum():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]

    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        h=last_close + 0.5,
        lo=last_close - 30.0,
        c=last_close - 28.0,
        v=30000,
    )
    candles.append(momentum)
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=momentum["close"],
            h=momentum["close"] + 1,
            lo=momentum["close"] - 1,
            c=momentum["close"] - 0.5,
        )
    )

    setups = mc.scan(candles)
    assert len(setups) == 1
    s = setups[0]
    assert s.direction == "SELL"
    assert s.candle_close < s.candle_open


# --- scan: filter behaviour ----------------------------------------------


def test_low_volume_rejected_even_with_big_body():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        lo=last_close - 0.5,
        h=last_close + 30.0,
        c=last_close + 28.0,
        v=8000,  # below 1.5x SMA20 of 10000
    )
    candles.append(momentum)
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=last_close + 28,
            h=last_close + 29,
            lo=last_close + 27,
            c=last_close + 28.3,
        )
    )
    assert mc.scan(candles) == []


def test_oversized_close_wick_rejected():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    # Bullish but with a 30% upper wick (close far below high).
    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        lo=last_close - 0.5,
        h=last_close + 30.0,
        c=last_close + 20.0,  # close-side wick = 10 / 30 = 33%
        v=30000,
    )
    candles.append(momentum)
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=last_close + 20,
            h=last_close + 21,
            lo=last_close + 19,
            c=last_close + 20.3,
        )
    )
    assert mc.scan(candles) == []


# --- scan: fib levels ----------------------------------------------------


def test_fib_levels_buy():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        lo=last_close - 0.5,
        h=last_close + 30.0,
        c=last_close + 28.0,
        v=30000,
    )
    forming = make_candle(
        t=1700000000 + 31 * 60,
        o=last_close + 28.5,  # next-bar open
        h=last_close + 29.0,
        lo=last_close + 27.5,
        c=last_close + 28.7,
    )
    candles.extend([momentum, forming])

    setups = mc.scan(candles, entry_mode="next_open")
    assert len(setups) == 1
    s = setups[0]
    rng = s.candle_high - s.candle_low
    assert s.entry == pytest.approx(forming["open"])
    assert s.sl == pytest.approx(s.candle_low - 0.10 * rng)
    assert s.tp1 == pytest.approx(s.candle_high)
    assert s.tp2 == pytest.approx(s.candle_high + 0.27 * rng)
    assert s.rr_tp1 > 0
    assert s.rr_tp2 > s.rr_tp1


def test_fib_levels_pullback_entry_mode():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    momentum = make_candle(
        t=1700000000 + 30 * 60,
        o=last_close,
        lo=last_close - 0.5,
        h=last_close + 30.0,
        c=last_close + 28.0,
        v=30000,
    )
    candles.append(momentum)
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=last_close + 28,
            h=last_close + 29,
            lo=last_close + 27,
            c=last_close + 28.3,
        )
    )

    setups = mc.scan(candles, entry_mode="pullback_236")
    assert len(setups) == 1
    s = setups[0]
    rng = s.candle_high - s.candle_low
    assert s.entry == pytest.approx(s.candle_high - 0.236 * rng)


# --- to_dict --------------------------------------------------------------


def test_setup_to_dict_shape():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    candles.append(
        make_candle(
            t=1700000000 + 30 * 60,
            o=last_close,
            lo=last_close - 0.5,
            h=last_close + 30.0,
            c=last_close + 28.0,
            v=30000,
        )
    )
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=last_close + 28,
            h=last_close + 29,
            lo=last_close + 27,
            c=last_close + 28.3,
        )
    )

    setups = mc.scan(candles)
    d = setups[0].to_dict()
    for k in (
        "symbol",
        "timeframe",
        "direction",
        "pattern",
        "trigger_index",
        "trigger_time",
        "candle",
        "metrics",
        "entry",
        "sl",
        "tp1",
        "tp2",
        "rr_tp1",
        "rr_tp2",
        "confidence",
        "reason",
    ):
        assert k in d, f"missing key {k}"
    assert set(d["candle"].keys()) == {"open", "high", "low", "close"}
    assert set(d["metrics"].keys()) == {"body_pct", "range_atr_mult", "volume_ratio"}


# --- confidence -----------------------------------------------------------


def test_confidence_is_in_range():
    candles = baseline_candles(30)
    last_close = candles[-1]["close"]
    candles.append(
        make_candle(
            t=1700000000 + 30 * 60,
            o=last_close,
            lo=last_close - 0.5,
            h=last_close + 30.0,
            c=last_close + 28.0,
            v=30000,
        )
    )
    candles.append(
        make_candle(
            t=1700000000 + 31 * 60,
            o=last_close + 28,
            h=last_close + 29,
            lo=last_close + 27,
            c=last_close + 28.3,
        )
    )
    setups = mc.scan(candles)
    assert len(setups) == 1
    assert 0.0 <= setups[0].confidence <= 1.0
