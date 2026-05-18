"""Internal helpers — shared across handlers."""

from __future__ import annotations

import os
from typing import Any

import MetaTrader5 as mt5


def to_dict(named_tuple: Any) -> dict[str, Any] | None:
    """Convert a MetaTrader5 named tuple to a plain dict.

    Returns ``None`` when ``named_tuple`` is ``None``. Useful for serialising
    MT5 responses through MCP (which speaks JSON).
    """
    if named_tuple is None:
        return None
    if hasattr(named_tuple, "_asdict"):
        return dict(named_tuple._asdict())
    if isinstance(named_tuple, dict):
        return named_tuple
    raise TypeError(f"Cannot convert {type(named_tuple).__name__} to dict")


def is_dry_run() -> bool:
    """True when destructive trade tools must simulate, not execute.

    Default is dry-run (safer). Set ``MT5_DRY_RUN=0`` to allow live orders;
    even then the live-trade-guard hook in ``.claude/`` will refuse without
    an explicit ``CONFIRM_LIVE`` token in the user prompt.
    """
    return os.getenv("MT5_DRY_RUN", "1") != "0"


def default_magic() -> int:
    """Default MT5 magic number for orders placed by this server."""
    raw = os.getenv("MT5_MAGIC", "900001")
    try:
        return int(raw)
    except ValueError:
        return 900001


def last_error_msg() -> str:
    """Format ``mt5.last_error()`` as a single string for error messages."""
    err = mt5.last_error()
    if isinstance(err, tuple) and len(err) == 2:
        code, message = err
        return f"[{code}] {message}"
    return str(err)


# Common retcodes seen with InstaForex demo accounts.
RETCODE_DESCRIPTIONS: dict[int, str] = {
    10004: "Requote",
    10006: "Request rejected",
    10007: "Request canceled by trader",
    10008: "Order placed",
    10009: "Request completed",
    10010: "Only part of the request was completed",
    10011: "Request processing error",
    10012: "Request canceled by timeout",
    10013: "Invalid request",
    10014: "Invalid volume in the request",
    10015: "Invalid price in the request",
    10016: "Invalid stops in the request",
    10017: "Trade is disabled",
    10018: "Market is closed",
    10019: "There is not enough money to complete the request",
    10020: "Prices changed",
    10021: "There are no quotes to process the request",
    10022: "Invalid order expiration date",
    10023: "Order state changed",
    10024: "Too frequent requests",
    10025: "No changes in request",
    10026: "Autotrading disabled by server",
    10027: "Autotrading disabled by client terminal",
    10028: "Request locked for processing",
    10029: "Order or position frozen",
    10030: "Invalid order filling type",
    10031: "No connection with the trade server",
}


def describe_retcode(code: int | None) -> str:
    """Human-readable name for a trade retcode."""
    if code is None:
        return "unknown"
    return RETCODE_DESCRIPTIONS.get(code, f"retcode {code}")
