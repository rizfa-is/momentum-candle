"""Momentum-candle strategy detector.

Spec: ``docs/strategies/momentum-candle.md``.
Source video: https://www.youtube.com/watch?v=Utj8qRwNtgE
"""

from __future__ import annotations

import logging
from typing import Any

from .base import (
    EntryMode,
    Pattern,
    Setup,
    clip,
    rolling_sma,
    wilder_atr,
)

log = logging.getLogger("mt5mcp")


# --- Default thresholds ---------------------------------------------------

DEFAULT_MIN_BODY_PCT = 0.70
DEFAULT_MAX_CLOSE_WICK_PCT = 0.10
DEFAULT_ATR_MULT = 1.0
DEFAULT_VOL_MULT = 1.5
DEFAULT_ATR_PERIOD = 14
DEFAULT_VOL_SMA_PERIOD = 20
DEFAULT_MIN_CONFIDENCE = 0.50

# Pattern detection windows.
CONSOLIDATION_LOOKBACK = 5  # bars used to detect breakout context
TREND_LOOKBACK = 10
TREND_MIN_MONOTONIC = 5
PULLBACK_LOOKBACK = 10
PULLBACK_TOLERANCE_ATR = 0.382


# --- Public scan ----------------------------------------------------------


def scan(
    candles: list[dict[str, Any]],
    *,
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    min_body_pct: float = DEFAULT_MIN_BODY_PCT,
    max_close_wick_pct: float = DEFAULT_MAX_CLOSE_WICK_PCT,
    atr_mult: float = DEFAULT_ATR_MULT,
    vol_mult: float = DEFAULT_VOL_MULT,
    atr_period: int = DEFAULT_ATR_PERIOD,
    vol_sma_period: int = DEFAULT_VOL_SMA_PERIOD,
    entry_mode: EntryMode = "next_open",
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> list[Setup]:
    """Scan ``candles`` for momentum-candle setups.

    ``candles`` follows the schema returned by
    ``mt5_mvp.market.get_candles_latest``: list of dicts with keys
    ``time, open, high, low, close, tick_volume, spread, real_volume``,
    oldest first.

    Returns setups sorted by ``trigger_index`` descending (newest first).
    The latest bar is treated as forming and excluded.
    """
    n = len(candles)
    if n < max(atr_period + 2, vol_sma_period + 2):
        return []

    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    opens = [float(c["open"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    vols = [float(c.get("tick_volume", 0)) for c in candles]
    times = [int(c["time"]) for c in candles]

    atrs = wilder_atr(highs, lows, closes, period=atr_period)
    vol_smas = rolling_sma(vols, vol_sma_period)

    setups: list[Setup] = []

    # Skip the last bar — treated as still forming.
    for i in range(atr_period + 1, n - 1):
        atr_i = atrs[i]
        sma_i = vol_smas[i]
        if atr_i is None or atr_i <= 0 or sma_i is None or sma_i <= 0:
            continue

        o, h, lo, c = opens[i], highs[i], lows[i], closes[i]
        rng = h - lo
        if rng <= 0:
            continue

        body = abs(c - o)
        body_pct = body / rng
        direction = "BUY" if c > o else "SELL"

        # Close-side wick.
        close_wick = (h - c) if direction == "BUY" else (c - lo)
        close_wick_pct = close_wick / rng

        range_atr_mult = rng / atr_i
        vol_ratio = vols[i] / sma_i

        # Hard filters.
        if body_pct < min_body_pct:
            continue
        if close_wick_pct > max_close_wick_pct:
            continue
        if range_atr_mult < atr_mult:
            continue
        if vol_ratio < vol_mult:
            continue

        pattern = _classify_pattern(i, direction, highs, lows, closes, atr_i)

        # Compute Fibonacci-based entry/SL/TP.
        entry, sl, tp1, tp2 = _fib_levels(direction, h, lo, opens, closes, i, entry_mode)

        risk = abs(entry - sl)
        if risk <= 0:
            continue
        rr_tp1 = abs(tp1 - entry) / risk
        rr_tp2 = abs(tp2 - entry) / risk

        confidence = _score(
            body_pct=body_pct,
            range_atr_mult=range_atr_mult,
            vol_ratio=vol_ratio,
            close_wick_pct=close_wick_pct,
            pattern=pattern,
        )
        if confidence < min_confidence:
            continue

        reason = (
            f"{pattern} momentum {direction.lower()} "
            f"(body {body_pct * 100:.0f}%, range {range_atr_mult:.2f}x ATR, "
            f"vol {vol_ratio:.2f}x SMA20)"
        )

        setups.append(
            Setup(
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                pattern=pattern,
                trigger_index=i,
                trigger_time=times[i],
                candle_open=o,
                candle_high=h,
                candle_low=lo,
                candle_close=c,
                body_pct=body_pct,
                range_atr_mult=range_atr_mult,
                volume_ratio=vol_ratio,
                entry_mode=entry_mode,
                entry=entry,
                sl=sl,
                tp1=tp1,
                tp2=tp2,
                rr_tp1=rr_tp1,
                rr_tp2=rr_tp2,
                confidence=confidence,
                reason=reason,
            )
        )

    # Newest first.
    setups.sort(key=lambda s: s.trigger_index, reverse=True)
    return setups


# --- Pattern classification -----------------------------------------------


def _classify_pattern(
    i: int,
    direction: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr_i: float,
) -> Pattern:
    """Pick the strongest matching pattern: breakout > trend > pullback."""
    if _is_breakout(i, direction, highs, lows, closes, atr_i):
        return "breakout"
    if _is_trend_continuation(i, direction, closes):
        return "trend"
    if _is_pullback(i, direction, highs, lows, atr_i):
        return "pullback"
    # Fallback — momentum without clear context still valid; classify as the
    # weakest pattern so confidence reflects it.
    return "pullback"


def _is_breakout(
    i: int,
    direction: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr_i: float,
) -> bool:
    start = i - CONSOLIDATION_LOOKBACK
    if start < 0:
        return False
    window_high = max(highs[start:i])
    window_low = min(lows[start:i])
    window_range = window_high - window_low
    if window_range <= 0:
        return False
    # Tight consolidation = avg range substantially smaller than ATR(i).
    if window_range > atr_i * 1.2:
        return False
    if direction == "BUY":
        return closes[i] > window_high
    return closes[i] < window_low


def _is_trend_continuation(i: int, direction: str, closes: list[float]) -> bool:
    start = i - TREND_LOOKBACK
    if start < 0:
        return False
    diffs = [closes[k + 1] - closes[k] for k in range(start, i)]
    if direction == "BUY":
        monotonic_count = sum(1 for d in diffs if d > 0)
    else:
        monotonic_count = sum(1 for d in diffs if d < 0)
    if monotonic_count < TREND_MIN_MONOTONIC:
        return False

    near_window = closes[i - 5 : i]
    if direction == "BUY":
        return closes[i] > max(near_window)
    return closes[i] < min(near_window)


def _is_pullback(
    i: int,
    direction: str,
    highs: list[float],
    lows: list[float],
    atr_i: float,
) -> bool:
    start = i - PULLBACK_LOOKBACK
    if start < 0:
        return False
    tol = PULLBACK_TOLERANCE_ATR * atr_i
    if direction == "BUY":
        recent_low = min(lows[start:i])
        return abs(lows[i] - recent_low) <= tol
    recent_high = max(highs[start:i])
    return abs(highs[i] - recent_high) <= tol


# --- Fib levels -----------------------------------------------------------


def _fib_levels(
    direction: str,
    high: float,
    low: float,
    opens: list[float],
    closes: list[float],
    i: int,
    entry_mode: EntryMode,
) -> tuple[float, float, float, float]:
    """Return (entry, sl, tp1, tp2) per the strategy spec."""
    rng = high - low
    if direction == "BUY":
        sl = low - 0.10 * rng
        tp1 = high
        tp2 = high + 0.27 * rng
        if entry_mode == "pullback_236":
            entry = high - 0.236 * rng
        else:
            # next-bar open if available; fallback to trigger close.
            entry = opens[i + 1] if i + 1 < len(opens) else closes[i]
    else:  # SELL
        sl = high + 0.10 * rng
        tp1 = low
        tp2 = low - 0.27 * rng
        if entry_mode == "pullback_236":
            entry = low + 0.236 * rng
        else:
            entry = opens[i + 1] if i + 1 < len(opens) else closes[i]
    return entry, sl, tp1, tp2


# --- Confidence scoring ---------------------------------------------------


def _score(
    *,
    body_pct: float,
    range_atr_mult: float,
    vol_ratio: float,
    close_wick_pct: float,
    pattern: Pattern,
) -> float:
    body_score = clip((body_pct - 0.70) / 0.30, 0.0, 1.0)
    range_score = clip((range_atr_mult - 1.0) / 1.5, 0.0, 1.0)
    vol_score = clip((vol_ratio - 1.5) / 2.5, 0.0, 1.0)
    wick_score = clip(1.0 - close_wick_pct / 0.10, 0.0, 1.0)
    pattern_score = 1.0 if pattern == "breakout" else 0.7 if pattern == "trend" else 0.5

    return (
        0.30 * body_score
        + 0.30 * range_score
        + 0.20 * vol_score
        + 0.10 * pattern_score
        + 0.10 * wick_score
    )
