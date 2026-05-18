"""Strategy primitives — Setup dataclass plus shared math helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["BUY", "SELL"]
Pattern = Literal["breakout", "pullback", "trend"]
EntryMode = Literal["next_open", "pullback_236"]


@dataclass(slots=True)
class Setup:
    """A single trade setup produced by a strategy detector."""

    symbol: str
    timeframe: str
    direction: Direction
    pattern: Pattern
    trigger_index: int
    trigger_time: int
    candle_open: float
    candle_high: float
    candle_low: float
    candle_close: float
    body_pct: float
    range_atr_mult: float
    volume_ratio: float
    entry_mode: EntryMode
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr_tp1: float
    rr_tp2: float
    confidence: float
    reason: str
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for MCP response."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "pattern": self.pattern,
            "trigger_index": self.trigger_index,
            "trigger_time": self.trigger_time,
            "candle": {
                "open": self.candle_open,
                "high": self.candle_high,
                "low": self.candle_low,
                "close": self.candle_close,
            },
            "metrics": {
                "body_pct": round(self.body_pct, 4),
                "range_atr_mult": round(self.range_atr_mult, 3),
                "volume_ratio": round(self.volume_ratio, 3),
            },
            "entry_mode": self.entry_mode,
            "entry": round(self.entry, 5),
            "sl": round(self.sl, 5),
            "tp1": round(self.tp1, 5),
            "tp2": round(self.tp2, 5),
            "rr_tp1": round(self.rr_tp1, 3),
            "rr_tp2": round(self.rr_tp2, 3),
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            **({"extras": self.extras} if self.extras else {}),
        }


# --- Indicator helpers ----------------------------------------------------


def true_range(prev_close: float, high: float, low: float) -> float:
    """Wilder's true range component for a single candle."""
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def wilder_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float | None]:
    """Wilder-smoothed ATR. Returns a list aligned to candles; positions
    where ATR is undefined are ``None``."""
    n = len(closes)
    if n == 0:
        return []
    if not (len(highs) == len(lows) == n):
        raise ValueError("highs, lows, closes must have equal length")

    out: list[float | None] = [None] * n
    if n <= period:
        return out

    # Seed: simple average of TR over the first `period` bars (skipping bar 0
    # since it has no prev_close).
    trs: list[float] = []
    for i in range(1, period + 1):
        trs.append(true_range(closes[i - 1], highs[i], lows[i]))
    seed = sum(trs) / period
    out[period] = seed

    prev = seed
    for i in range(period + 1, n):
        tr = true_range(closes[i - 1], highs[i], lows[i])
        prev = (prev * (period - 1) + tr) / period
        out[i] = prev
    return out


def rolling_sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average; returns ``None`` until ``period`` items seen."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period or period <= 0:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def clip(x: float, lo: float, hi: float) -> float:
    """Clamp ``x`` to [lo, hi]."""
    return max(lo, min(hi, x))
