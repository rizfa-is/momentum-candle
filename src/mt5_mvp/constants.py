"""String ↔ MetaTrader5 numeric constant maps.

Keeps human-readable strings (used by AI agents and signal text) decoupled
from the numeric MT5 API constants. Importing this module triggers
``import MetaTrader5``; tests stub that out via ``sys.modules``.
"""

from __future__ import annotations

import MetaTrader5 as mt5

# --- Timeframes ------------------------------------------------------------

TIMEFRAME_MAP: dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M2": mt5.TIMEFRAME_M2,
    "M3": mt5.TIMEFRAME_M3,
    "M4": mt5.TIMEFRAME_M4,
    "M5": mt5.TIMEFRAME_M5,
    "M6": mt5.TIMEFRAME_M6,
    "M10": mt5.TIMEFRAME_M10,
    "M12": mt5.TIMEFRAME_M12,
    "M15": mt5.TIMEFRAME_M15,
    "M20": mt5.TIMEFRAME_M20,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H3": mt5.TIMEFRAME_H3,
    "H4": mt5.TIMEFRAME_H4,
    "H6": mt5.TIMEFRAME_H6,
    "H8": mt5.TIMEFRAME_H8,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# --- Order sides / types ---------------------------------------------------

ORDER_TYPE_MAP: dict[str, int] = {
    "BUY": mt5.ORDER_TYPE_BUY,
    "SELL": mt5.ORDER_TYPE_SELL,
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
}

# --- Order filling ---------------------------------------------------------

FILLING_MAP: dict[str, int] = {
    "FOK": mt5.ORDER_FILLING_FOK,
    "IOC": mt5.ORDER_FILLING_IOC,
    "RETURN": mt5.ORDER_FILLING_RETURN,
}

# --- Order time-in-force ---------------------------------------------------

TIME_MAP: dict[str, int] = {
    "GTC": mt5.ORDER_TIME_GTC,
    "DAY": mt5.ORDER_TIME_DAY,
    "SPECIFIED": mt5.ORDER_TIME_SPECIFIED,
    "SPECIFIED_DAY": mt5.ORDER_TIME_SPECIFIED_DAY,
}

# --- Reverse lookup: numeric → "BUY"/"SELL" for diagnostics ----------------

ORDER_TYPE_REVERSE: dict[int, str] = {v: k for k, v in ORDER_TYPE_MAP.items()}


def resolve_timeframe(name: str) -> int:
    """Return the MT5 timeframe constant for ``name``.

    Raises:
        ValueError: if ``name`` is not a known timeframe.
    """
    key = name.upper()
    if key not in TIMEFRAME_MAP:
        raise ValueError(f"Unknown timeframe '{name}'. Valid: {sorted(TIMEFRAME_MAP)}")
    return TIMEFRAME_MAP[key]


def resolve_order_type(name: str) -> int:
    """Return the MT5 order-type constant for ``name``."""
    key = name.upper()
    if key not in ORDER_TYPE_MAP:
        raise ValueError(f"Unknown order type '{name}'. Valid: {sorted(ORDER_TYPE_MAP)}")
    return ORDER_TYPE_MAP[key]


def resolve_filling(name: str) -> int:
    """Return the MT5 filling-mode constant for ``name``."""
    key = name.upper()
    if key not in FILLING_MAP:
        raise ValueError(f"Unknown filling mode '{name}'. Valid: {sorted(FILLING_MAP)}")
    return FILLING_MAP[key]
