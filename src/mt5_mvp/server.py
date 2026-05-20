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
from .strategies import momentum_candle as mc
from .strategies import support_resistance as sr

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
6. To find trade ideas, use `scan_momentum_setups` (default symbol XAUUSD,
   timeframe M15). Each setup includes Fibonacci-based entry, SL, TP1 (the
   candle high), and TP2 (1.27 extension). See
   docs/strategies/momentum-candle.md for the full strategy.
7. To find major S/R levels, use `get_major_sr`. Auto-escalates from M5
   to higher timeframes when one side of price has no coverage.
   See docs/strategies/support-resistance.md.

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


# --- strategy tools -------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def scan_momentum_setups(
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    lookback: int = 200,
    min_body_pct: float = 0.70,
    atr_mult: float = 1.0,
    vol_mult: float = 1.5,
    entry_mode: str = "next_open",
    min_confidence: float = 0.50,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Scan recent candles for momentum-candle trade setups.

    The detector looks for high body-percentage candles with range expansion
    and tick-volume spikes, then classifies each as breakout / pullback /
    trend continuation. Returns Fibonacci-based entry, SL, TP1 (candle high)
    and TP2 (1.27 extension) per the strategy spec in
    docs/strategies/momentum-candle.md.

    Args:
        symbol: trading symbol (default XAUUSD).
        timeframe: M5, M15, H1, etc. M15 recommended by the source video.
        lookback: number of recent candles to scan (>=50 advised, max 5000).
        min_body_pct: body / range threshold (default 0.70).
        atr_mult: minimum range / ATR(14) (default 1.0).
        vol_mult: minimum tick_volume / SMA(20) (default 1.5).
        entry_mode: "next_open" (market) or "pullback_236" (limit at 23.6%).
        min_confidence: drop setups below this 0..1 score (default 0.50).

    Returns:
        List of setup dicts ordered newest first, or a single error dict.
    """
    if (err := _ensure()) is not None:
        return err

    candles = market.get_candles_latest(symbol=symbol, timeframe=timeframe, count=int(lookback))
    if isinstance(candles, dict):
        # market layer returned an error dict
        return candles
    if not candles:
        return {"error": "no candles returned"}

    if entry_mode not in ("next_open", "pullback_236"):
        return {"error": f"invalid entry_mode: {entry_mode!r}"}

    setups = mc.scan(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        min_body_pct=float(min_body_pct),
        atr_mult=float(atr_mult),
        vol_mult=float(vol_mult),
        entry_mode=entry_mode,  # type: ignore[arg-type]
        min_confidence=float(min_confidence),
    )
    return [s.to_dict() for s in setups]


@mcp.tool(annotations={"readOnlyHint": True})
def get_major_sr(
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
) -> dict[str, Any]:
    """Find major support/resistance levels for a symbol.

    Uses swing-pivot clustering on the active timeframe. When the scan
    only surfaces levels above (or below) the current price, the
    algorithm escalates through the timeframe ladder
    M5 -> M15 -> H1 -> H4 -> D1 until both sides are populated or the
    ladder is exhausted (controlled by ``max_tier``).

    Round-number levels (multiples of ``round_step``) and multi-TF
    extremes (day/prior-day/week high+low from D1) are injected as
    static levels in addition to swing-pivot clusters.

    Args:
        symbol: trading symbol (default XAUUSD).
        timeframe: starting timeframe; one of M5, M15, H1, H4, D1.
        lookback: bars to scan per tier (default 500).
        cluster_atr_mult: cluster radius = this x ATR(14).
        min_touches: minimum pivots clustered to qualify as major.
        pivot_left, pivot_right: fractal-confirmation lag bars.
        use_escalation: enable timeframe-ladder escalation.
        max_tier: cap tier index (1=M5, 2=M15, 3=H1, 4=H4, 5=D1).
        include_round: inject round-number levels.
        round_step: distance between round levels (default 50.0).
        include_multi_tf_extremes: inject day/week highs+lows.

    Returns:
        ``{
            "current_price": ...,
            "current_time_utc": ...,
            "atr14": ...,
            "tiers_scanned": [...],
            "escalation_triggered": bool,
            "levels": [{"price", "weight", "type", "tier",
                        "distance_pts", "side"}, ...]
        }``

        Levels are sorted nearest-first by absolute distance from the
        current price.
    """
    if (err := _ensure()) is not None:
        return err

    try:
        return sr.find_major_levels(
            symbol=symbol,
            timeframe=timeframe,
            lookback=int(lookback),
            cluster_atr_mult=float(cluster_atr_mult),
            min_touches=int(min_touches),
            pivot_left=int(pivot_left),
            pivot_right=int(pivot_right),
            use_escalation=bool(use_escalation),
            max_tier=int(max_tier),
            include_round=bool(include_round),
            round_step=float(round_step),
            include_multi_tf_extremes=bool(include_multi_tf_extremes),
        )
    except ValueError as e:
        return {"error": str(e)}


__all__ = ["mcp"]
