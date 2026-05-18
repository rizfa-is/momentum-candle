"""FastMCP server exposing 8 trading tools.

Tools (read-only):
    - get_account
    - get_symbol_price
    - get_candles_latest
    - get_positions

Tools (destructive):
    - place_market_order
    - modify_position
    - close_position
    - close_all_positions

Each destructive tool honours ``MT5_DRY_RUN`` (default on). The
.claude/hooks/live-trade-guard.sh hook adds a second layer of protection by
requiring a CONFIRM_LIVE token in the user prompt.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from . import account, market, trade
from .client import ensure_initialized

log = logging.getLogger("mt5mcp")

INSTRUCTIONS = """\
You are connected to a MetaTrader 5 trading account via MCP.

Workflow rules (always follow):
1. Call `get_account` before placing any trade to verify margin and trade_allowed.
2. Call `get_symbol_price` before placing orders to confirm the live price.
3. Call `get_positions` to find ticket numbers before modifying or closing.
4. The default symbol focus for this account is XAUUSD (gold).
5. Destructive tools (place_market_order, modify_position, close_position,
   close_all_positions) may run in dry-run mode. Inspect the response and
   relay the dry_run flag clearly to the user.

Volume conventions on this InstaForex demo:
- Min volume is typically 0.01 lots; step is 0.01.
- The server normalises volumes that fall outside the symbol limits.
- XAUUSD spreads are wider than majors; default deviation is 30 points.
"""

mcp: FastMCP = FastMCP("mt5-mvp", instructions=INSTRUCTIONS)


def _ensure() -> dict[str, Any] | None:
    """Return an error dict if MT5 is unreachable, else None."""
    if not ensure_initialized():
        return {"error": "MT5 terminal not connected. Start the MT5 terminal and log in."}
    return None


# --- read-only tools ------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def get_account() -> dict[str, Any]:
    """Return current trading account info: balance, equity, profit, margin,
    leverage, currency, trade_allowed. Call before placing trades."""
    if (err := _ensure()) is not None:
        return err
    return account.get_account()


@mcp.tool(annotations={"readOnlyHint": True})
def get_symbol_price(symbol: str = "XAUUSD") -> dict[str, Any]:
    """Return latest tick for a symbol: bid, ask, last, volume, time, spread.
    Default symbol is XAUUSD (gold) — the focus of this strategy."""
    if (err := _ensure()) is not None:
        return err
    return market.get_symbol_price(symbol)


@mcp.tool(annotations={"readOnlyHint": True})
def get_candles_latest(
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    count: int = 100,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return the most recent OHLCV candles.

    Args:
        symbol: trading symbol, e.g. "XAUUSD".
        timeframe: M1, M5, M15, M30, H1, H4, D1, W1, MN1, etc.
        count: number of bars (1..5000). Default 100.
    """
    if (err := _ensure()) is not None:
        return err
    return market.get_candles_latest(symbol=symbol, timeframe=timeframe, count=count)


@mcp.tool(annotations={"readOnlyHint": True})
def get_positions(symbol: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """List currently open positions, optionally filtered by symbol.
    Returns ticket, type (BUY/SELL), volume, price_open, sl, tp, profit,
    magic, comment for each position."""
    if (err := _ensure()) is not None:
        return err
    return trade.get_positions(symbol)


# --- destructive tools ----------------------------------------------------


@mcp.tool(annotations={"destructiveHint": True})
def place_market_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 30,
    magic: int | None = None,
    comment: str = "",
) -> dict[str, Any]:
    """Place a BUY or SELL market order at the current price.

    Honours MT5_DRY_RUN. retcode 10009 = success.

    Args:
        symbol: e.g. "XAUUSD".
        side: "BUY" or "SELL".
        volume: lot size, e.g. 0.01.
        sl: stop loss price (absolute, not points).
        tp: take profit price (absolute, not points).
        deviation: max slippage in points; default 30.
        magic: order magic number for idempotency; defaults from MT5_MAGIC.
        comment: optional comment shown in MT5.
    """
    if (err := _ensure()) is not None:
        return err
    return trade.place_market_order(
        symbol=symbol,
        side=side,
        volume=volume,
        sl=sl,
        tp=tp,
        deviation=deviation,
        magic=magic,
        comment=comment,
    )


@mcp.tool(annotations={"destructiveHint": True})
def modify_position(
    ticket: int,
    sl: float | None = None,
    tp: float | None = None,
) -> dict[str, Any]:
    """Update SL and/or TP on an existing open position. Provide at least one."""
    if (err := _ensure()) is not None:
        return err
    return trade.modify_position(ticket=ticket, sl=sl, tp=tp)


@mcp.tool(annotations={"destructiveHint": True})
def close_position(ticket: int, volume: float | None = None) -> dict[str, Any]:
    """Close an open position fully (omit volume) or partially.
    Use get_positions to find the ticket number first."""
    if (err := _ensure()) is not None:
        return err
    return trade.close_position(ticket=ticket, volume=volume)


@mcp.tool(annotations={"destructiveHint": True})
def close_all_positions(symbol: str | None = None) -> dict[str, Any]:
    """Close every open position, optionally only those for ``symbol``.
    Returns a count and per-position results."""
    if (err := _ensure()) is not None:
        return err
    return trade.close_all_positions(symbol)


__all__ = ["mcp"]
