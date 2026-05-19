"""Backtest momentum-candle signals through May 2026.

User-specified parameters:
  - body / range          >= 0.80
  - close-side wick / range <= 0.10
  - body in price points  >= 800   (8.0 USD on XAUUSD)
  - skip London           = false  (all UTC sessions allowed, no filter)

For each signal:
  - Simulate forward up to 60 bars (5 hours on M5)
  - Track if price hits TP2 (1.27 extension), TP1 (candle high), or SL
  - Record max forward extension (in fib level terms)
  - Record max retracement (deepest counter-move) during the trade
  - Order of touch matters: if SL is touched first the trade dies even if
    price later reaches TP2

Fibonacci reference frame for a BUY candle with low=L, high=H, range=H-L:
  Forward (extension) levels:
    0%   = candle low
    100% = candle high (TP1)
    127% = high + 0.27*range  (TP2, the -27 user asks about)

  Backward (retracement-while-in-trade) levels measured from entry:
    Trade entry ~ next bar open. Trade dies at SL = L - 0.10*range.
    Max retracement = how close price came to SL during the trade,
                      expressed as fraction of (entry - SL) distance.
                      0.0 = price never gave back; 1.0 = SL hit.

For SELL the geometry is mirrored.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle\cache\may2026-m5.json")
OUT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle\data\backtests")
OUT.mkdir(parents=True, exist_ok=True)

POINT = 0.01  # XAUUSD point size
MIN_BODY_PCT = 0.80
MAX_CWICK_PCT = 0.10
MIN_BODY_POINTS = 800
SIM_HORIZON_BARS = 60


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def is_signal(b: dict[str, Any]) -> tuple[bool, str | None]:
    rng = b["high"] - b["low"]
    if rng <= 0:
        return False, None
    body = abs(b["close"] - b["open"])
    body_pct = body / rng

    if b["close"] > b["open"]:
        side = "BUY"
        cwick = b["high"] - b["close"]
    elif b["close"] < b["open"]:
        side = "SELL"
        cwick = b["close"] - b["low"]
    else:
        return False, None

    cwick_pct = cwick / rng
    body_pts = body / POINT

    if body_pct < MIN_BODY_PCT:
        return False, None
    if cwick_pct > MAX_CWICK_PCT:
        return False, None
    if body_pts < MIN_BODY_POINTS:
        return False, None

    return True, side


def simulate(signal_idx: int, side: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Walk forward from signal_idx+1 until TP2/SL/timeout. Return outcome dict."""
    sig = candles[signal_idx]
    L = sig["low"]
    H = sig["high"]
    rng = H - L

    if side == "BUY":
        sl = L - 0.10 * rng
        tp1 = H
        tp2 = H + 0.27 * rng
    else:
        sl = H + 0.10 * rng
        tp1 = L
        tp2 = L - 0.27 * rng

    # Entry on next bar open
    if signal_idx + 1 >= len(candles):
        return {"outcome": "no-next-bar", "bars_held": 0}
    entry_bar = candles[signal_idx + 1]
    entry_price = entry_bar["open"]
    risk = abs(entry_price - sl)

    max_ext_level_pct = 0.0  # forward, in % of range past candle's directional extreme
    max_retrace_to_sl_pct = 0.0  # backward, fraction toward SL (0 safe, 1 stopped)
    outcome = "timeout"
    bars_held = 0
    exit_price = None
    exit_time = None

    for k in range(SIM_HORIZON_BARS):
        idx = signal_idx + 1 + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bars_held = k + 1

        bh, bl = bar["high"], bar["low"]

        # forward extension (% of range above H for BUY, below L for SELL)
        if side == "BUY":
            if bh > H:
                ext_level = (bh - L) / rng  # 1.0 = at H, 1.27 = at TP2
                max_ext_level_pct = max(max_ext_level_pct, ext_level)
        else:
            if bl < L:
                ext_level = (H - bl) / rng
                max_ext_level_pct = max(max_ext_level_pct, ext_level)

        # retracement toward SL during the trade (from entry_price)
        if risk > 0:
            if side == "BUY":
                drawdown = entry_price - bl
            else:
                drawdown = bh - entry_price
            if drawdown > 0:
                ret_frac = drawdown / risk
                max_retrace_to_sl_pct = max(max_retrace_to_sl_pct, ret_frac)

        # check SL first (worst-case ordering since we don't have tick data)
        # In MT5 the order of high/low within a bar is unknown; we use
        # standard backtest convention: if both SL and TP can be hit, SL wins.
        if side == "BUY":
            sl_hit = bl <= sl
            tp1_hit = bh >= tp1
            tp2_hit = bh >= tp2
        else:
            sl_hit = bh >= sl
            tp1_hit = bl <= tp1
            tp2_hit = bl <= tp2

        if sl_hit and (tp1_hit or tp2_hit):
            # Worst-case: SL first.
            outcome = "SL"
            exit_price = sl
            exit_time = bar["time"]
            break
        if sl_hit:
            outcome = "SL"
            exit_price = sl
            exit_time = bar["time"]
            break
        if tp2_hit:
            outcome = "TP2"
            exit_price = tp2
            exit_time = bar["time"]
            break
        if tp1_hit:
            # Don't exit on TP1 alone — strategy targets TP2.
            # But record that TP1 was reached.
            pass

    # Also figure out whether TP1 was reached at any point (even if final outcome is TP2 or SL)
    tp1_reached = max_ext_level_pct >= 1.0

    if side == "BUY":
        max_price = L + max_ext_level_pct * rng if max_ext_level_pct > 0 else None
    else:
        max_price = (H - max_ext_level_pct * rng) if max_ext_level_pct > 0 else None

    return {
        "outcome": outcome,
        "bars_held": bars_held,
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
        "exit_time_utc": utc(exit_time).isoformat() if exit_time else None,
        "tp1_reached": tp1_reached,
        "max_extension_pct": round(max_ext_level_pct * 100, 1),
        "max_retrace_to_sl_pct": round(max_retrace_to_sl_pct * 100, 1),
        "candle_low": round(L, 2),
        "candle_high": round(H, 2),
        "candle_range": round(rng, 2),
        "max_price_reached": round(max_price, 2) if max_price is not None else None,
    }


def main() -> None:
    candles = json.loads(CACHE.read_text(encoding="utf-8"))
    candles.sort(key=lambda b: b["time"])

    signals = []
    for i, b in enumerate(candles):
        if i + 1 >= len(candles):
            break
        ok, side = is_signal(b)
        if not ok:
            continue
        sim = simulate(i, side, candles)
        signals.append(
            {
                "idx": i,
                "time_utc": utc(b["time"]).isoformat(),
                "side": side,
                "open": round(b["open"], 2),
                "high": round(b["high"], 2),
                "low": round(b["low"], 2),
                "close": round(b["close"], 2),
                "body_pct": round(abs(b["close"] - b["open"]) / (b["high"] - b["low"]) * 100, 1),
                "body_points": round(abs(b["close"] - b["open"]) / POINT, 0),
                **sim,
            }
        )

    # Outcome breakdown
    n = len(signals)
    n_tp2 = sum(1 for s in signals if s["outcome"] == "TP2")
    n_sl = sum(1 for s in signals if s["outcome"] == "SL")
    n_to = sum(1 for s in signals if s["outcome"] in ("timeout", "ran-out-of-data"))
    n_tp1 = sum(1 for s in signals if s["tp1_reached"])

    print(f"=== Backtest May 2026 -- XAUUSD M5 ===")
    print(f"Window: {utc(candles[0]['time']).isoformat()} -> {utc(candles[-1]['time']).isoformat()}")
    print(f"Bars: {len(candles)}")
    print(f"Filter: body%>={MIN_BODY_PCT}, cwick%<={MAX_CWICK_PCT}, body>={MIN_BODY_POINTS}pt, sessions=ALL")
    print()
    print(f"Signals fired: {n}")
    if n == 0:
        print("No signals — filter too tight for May 2026 on this account.")
    else:
        print(f"  TP2 (1.27 ext) hit: {n_tp2:>3}  ({n_tp2 / n * 100:>5.1f}%)")
        print(f"  TP1 (candle high)  : {n_tp1:>3}  ({n_tp1 / n * 100:>5.1f}%)  [reached at any point]")
        print(f"  SL hit              : {n_sl:>3}  ({n_sl / n * 100:>5.1f}%)")
        print(f"  Timeout (60 bars)   : {n_to:>3}  ({n_to / n * 100:>5.1f}%)")
        print()
        # PnL summary at constant risk = 1
        pnl_units = 0.0
        for s in signals:
            if s["outcome"] == "TP2":
                pnl_units += abs(s["tp2"] - s["entry_price"]) / abs(s["entry_price"] - s["sl"])
            elif s["outcome"] == "SL":
                pnl_units -= 1.0
        print(f"  PnL @ 1R/trade (TP2 target): {pnl_units:+.2f} R")
        print(f"  Profit factor (gross):       {pnl_units + n_sl:.2f} R / {n_sl:.2f} R = {((pnl_units + n_sl) / max(n_sl, 1)):.2f}" if n_sl else "  Profit factor: inf (no losses)")
    print()

    # Per-signal table
    print("Per-signal results:")
    print(f"{'#':>3}  {'time UTC':<19}  {'side':<4}  {'open':>7}  {'high':>7}  {'low':>7}  {'close':>7}  {'body%':>5}  {'body_pt':>7}  {'outcome':<10}  {'maxExt%':>7}  {'maxDD%':>6}  {'bars':>4}")
    print("-" * 130)
    for n_, s in enumerate(signals, 1):
        print(f"{n_:>3}  {s['time_utc'][:19]:<19}  {s['side']:<4}  "
              f"{s['open']:>7.2f}  {s['high']:>7.2f}  {s['low']:>7.2f}  {s['close']:>7.2f}  "
              f"{s['body_pct']:>4.1f}%  {s['body_points']:>7.0f}  "
              f"{s['outcome']:<10}  {s['max_extension_pct']:>6.1f}%  {s['max_retrace_to_sl_pct']:>5.1f}%  "
              f"{s['bars_held']:>4}")

    # Save raw JSON
    out_json = OUT / "may2026-results.json"
    out_json.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    print()
    print(f"Saved {len(signals)} signals to {out_json}")


if __name__ == "__main__":
    main()
