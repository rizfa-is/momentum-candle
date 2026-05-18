"""Market data handlers — symbol prices and OHLCV candles."""

from __future__ import annotations

from typing import Any

import MetaTrader5 as mt5

from ._utils import last_error_msg, to_dict
from .constants import resolve_timeframe

MAX_CANDLES = 5000


def get_symbol_price(symbol: str) -> dict[str, Any]:
    """Return latest tick for ``symbol`` (bid/ask/spread/time)."""
    if not mt5.symbol_select(symbol, True):
        return {"error": f"Cannot select symbol '{symbol}': {last_error_msg()}"}
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"error": f"No tick for '{symbol}': {last_error_msg()}"}
    info = mt5.symbol_info(symbol)
    spread = None
    if info is not None:
        spread = getattr(info, "spread", None)
    data = to_dict(tick) or {}
    return {
        "symbol": symbol,
        "bid": data.get("bid"),
        "ask": data.get("ask"),
        "last": data.get("last"),
        "volume": data.get("volume"),
        "time": data.get("time"),
        "spread_points": spread,
    }


def get_candles_latest(
    symbol: str,
    timeframe: str = "H1",
    count: int = 100,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return the most recent ``count`` candles for ``symbol`` at ``timeframe``.

    Args:
        symbol: e.g. "XAUUSD".
        timeframe: one of constants.TIMEFRAME_MAP keys (M1..MN1).
        count: number of bars (1..5000).
    """
    try:
        tf = resolve_timeframe(timeframe)
    except ValueError as e:
        return {"error": str(e)}

    if not mt5.symbol_select(symbol, True):
        return {"error": f"Cannot select symbol '{symbol}': {last_error_msg()}"}

    n = max(1, min(int(count), MAX_CANDLES))
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None:
        return {"error": f"copy_rates_from_pos failed: {last_error_msg()}"}

    out: list[dict[str, Any]] = []
    for r in rates:
        # MT5 returns a numpy structured array; index access is field-by-position:
        # 0=time, 1=open, 2=high, 3=low, 4=close, 5=tick_volume, 6=spread, 7=real_volume
        out.append(
            {
                "time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "tick_volume": int(r[5]),
                "spread": int(r[6]),
                "real_volume": int(r[7]),
            }
        )
    return out
