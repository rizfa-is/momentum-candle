"""Trading handlers — market orders, modify, close, close-all.

All destructive functions respect ``MT5_DRY_RUN`` (default on). When dry-run
is active, the function returns a synthetic response describing what it
*would* have sent to the broker. The MCP server layer additionally enforces
the dry-run guard and tags tools as ``destructiveHint``.
"""

from __future__ import annotations

import logging
from typing import Any

import MetaTrader5 as mt5

from ._utils import (
    default_magic,
    describe_retcode,
    is_dry_run,
    last_error_msg,
    to_dict,
)
from .constants import ORDER_TYPE_REVERSE, resolve_filling, resolve_order_type

log = logging.getLogger("mt5mcp")

DEFAULT_DEVIATION = 30  # points (XAUUSD typical spread is wide on InstaForex demo)


# --- helpers --------------------------------------------------------------


def _detect_filling(symbol: str) -> int:
    """Pick a sensible filling mode from symbol_info.filling_mode flags.

    InstaForex demo commonly accepts only RETURN; other brokers prefer IOC.
    """
    info = mt5.symbol_info(symbol)
    flags = getattr(info, "filling_mode", 0) if info is not None else 0
    # Bit flags in MT5: 1 = FOK, 2 = IOC. RETURN works regardless.
    if flags & 2:
        return resolve_filling("IOC")
    if flags & 1:
        return resolve_filling("FOK")
    return resolve_filling("RETURN")


def _market_price(symbol: str, side: str) -> float | None:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    return float(tick.ask) if side.upper() == "BUY" else float(tick.bid)


def _normalize_volume(symbol: str, volume: float) -> float:
    """Clamp/round volume to the symbol's volume_min, volume_max, volume_step."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return float(volume)
    vmin = float(getattr(info, "volume_min", 0.01))
    vmax = float(getattr(info, "volume_max", 100.0))
    vstep = float(getattr(info, "volume_step", 0.01)) or 0.01
    v = max(vmin, min(float(volume), vmax))
    # Round down to the nearest step.
    steps = int(v / vstep)
    return round(steps * vstep, 8)


def get_positions(symbol: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """List open positions, optionally filtered by symbol."""
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        return {"error": f"positions_get failed: {last_error_msg()}"}
    keep = (
        "ticket",
        "time",
        "type",
        "volume",
        "symbol",
        "price_open",
        "sl",
        "tp",
        "price_current",
        "profit",
        "swap",
        "magic",
        "comment",
    )
    rows: list[dict[str, Any]] = []
    for p in positions:
        d = to_dict(p) or {}
        row = {k: d[k] for k in keep if k in d}
        if "type" in row:
            row["type"] = ORDER_TYPE_REVERSE.get(row["type"], row["type"])
        rows.append(row)
    return rows


# --- destructive ----------------------------------------------------------


def place_market_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = DEFAULT_DEVIATION,
    magic: int | None = None,
    comment: str = "",
) -> dict[str, Any]:
    """Place a BUY or SELL market order.

    Honours ``MT5_DRY_RUN`` — when enabled, returns a synthetic response and
    does **not** call ``order_send``.
    """
    side_u = side.upper()
    if side_u not in ("BUY", "SELL"):
        return {"error": f"side must be BUY or SELL, got {side!r}"}

    try:
        otype = resolve_order_type(side_u)
    except ValueError as e:
        return {"error": str(e)}

    if not mt5.symbol_select(symbol, True):
        return {"error": f"Cannot select symbol '{symbol}': {last_error_msg()}"}

    price = _market_price(symbol, side_u)
    if price is None:
        return {"error": f"No tick for '{symbol}': {last_error_msg()}"}

    vol = _normalize_volume(symbol, volume)
    if vol <= 0:
        return {"error": f"Normalized volume is zero for {symbol} (requested {volume})"}

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": vol,
        "type": otype,
        "price": price,
        "deviation": int(deviation),
        "magic": int(magic if magic is not None else default_magic()),
        "comment": comment or "mt5-mvp",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _detect_filling(symbol),
    }
    if sl is not None:
        request["sl"] = float(sl)
    if tp is not None:
        request["tp"] = float(tp)

    if is_dry_run():
        log.info("[DRY-RUN] place_market_order %s", request)
        return {
            "dry_run": True,
            "request": request,
            "note": (
                "MT5_DRY_RUN is active. To place this trade live, set "
                "MT5_DRY_RUN=0 and include CONFIRM_LIVE in the prompt."
            ),
        }

    result = mt5.order_send(request)
    if result is None:
        return {"error": f"order_send returned None: {last_error_msg()}"}

    rd = to_dict(result) or {}
    rd["retcode_text"] = describe_retcode(rd.get("retcode"))
    rd["request"] = request
    return rd


def modify_position(
    ticket: int,
    sl: float | None = None,
    tp: float | None = None,
) -> dict[str, Any]:
    """Update SL and/or TP on an existing position."""
    if sl is None and tp is None:
        return {"error": "Provide at least one of sl, tp"}

    pos = mt5.positions_get(ticket=int(ticket))
    if not pos:
        return {"error": f"Position {ticket} not found"}
    p = pos[0]

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": int(ticket),
        "symbol": p.symbol,
        "sl": float(sl) if sl is not None else float(getattr(p, "sl", 0.0) or 0.0),
        "tp": float(tp) if tp is not None else float(getattr(p, "tp", 0.0) or 0.0),
    }

    if is_dry_run():
        log.info("[DRY-RUN] modify_position %s", request)
        return {"dry_run": True, "request": request}

    result = mt5.order_send(request)
    if result is None:
        return {"error": f"order_send returned None: {last_error_msg()}"}
    rd = to_dict(result) or {}
    rd["retcode_text"] = describe_retcode(rd.get("retcode"))
    return rd


def close_position(ticket: int, volume: float | None = None) -> dict[str, Any]:
    """Close an open position fully or partially."""
    pos = mt5.positions_get(ticket=int(ticket))
    if not pos:
        return {"error": f"Position {ticket} not found"}
    p = pos[0]

    close_volume = float(volume) if volume is not None else float(p.volume)
    close_volume = _normalize_volume(p.symbol, close_volume)

    if int(p.type) == int(mt5.ORDER_TYPE_BUY):
        otype = mt5.ORDER_TYPE_SELL
        side_for_price = "SELL"
    else:
        otype = mt5.ORDER_TYPE_BUY
        side_for_price = "BUY"

    price = _market_price(p.symbol, side_for_price)
    if price is None:
        return {"error": f"No tick for '{p.symbol}': {last_error_msg()}"}

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": int(ticket),
        "symbol": p.symbol,
        "volume": close_volume,
        "type": otype,
        "price": price,
        "deviation": DEFAULT_DEVIATION,
        "magic": int(getattr(p, "magic", default_magic())),
        "comment": "mt5-mvp/close",
        "type_filling": _detect_filling(p.symbol),
    }

    if is_dry_run():
        log.info("[DRY-RUN] close_position %s", request)
        return {"dry_run": True, "request": request}

    result = mt5.order_send(request)
    if result is None:
        return {"error": f"order_send returned None: {last_error_msg()}"}
    rd = to_dict(result) or {}
    rd["retcode_text"] = describe_retcode(rd.get("retcode"))
    return rd


def close_all_positions(symbol: str | None = None) -> dict[str, Any]:
    """Close every open position, optionally filtered by symbol."""
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        return {"error": f"positions_get failed: {last_error_msg()}"}
    if not positions:
        return {"closed": 0, "results": []}

    results: list[dict[str, Any]] = []
    for p in positions:
        results.append(close_position(int(p.ticket)))
    closed = sum(1 for r in results if r.get("retcode") in (10009, 10008) or r.get("dry_run"))
    return {"closed": closed, "total": len(positions), "results": results}
