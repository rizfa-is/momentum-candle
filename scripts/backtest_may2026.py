"""Backtest momentum-candle signals through May 2026.

User-specified filter:
  - body / range          >= 0.80
  - close-side wick / range <= 0.10
  - body in price points  >= 800   (8.0 USD on XAUUSD)
  - skip London           = false  (all UTC sessions allowed)

Two entry modes simulated side-by-side:
  next_open      Market entry on next bar's open (original)
  pullback_236   Limit order at the 23.6 fib retracement of the signal
                 candle. Order is canceled if not filled within
                 PULLBACK_FILL_BARS bars (default 10).

Both modes share the same SL and TP2:
  BUY:  SL = low - 0.10*range,  TP2 = high + 0.27*range
  SELL: mirror

For each signal we record:
  - whether it filled (always for next_open; conditional for pullback_236)
  - outcome: TP2 / SL / timeout
  - max forward extension during trade (% past directional extreme)
  - max retracement toward SL during trade

Worst-case intra-bar ordering: if both SL and TP2 are crossed in the
same bar, SL wins. Real tick data would resolve some of these to TP2.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

CACHE = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle\cache\may2026-m5.json")
OUT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle\data\backtests")
OUT.mkdir(parents=True, exist_ok=True)

POINT = 0.01  # XAUUSD point size
MIN_BODY_PCT = 0.80
MAX_CWICK_PCT = 0.10
MIN_BODY_POINTS = 800
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10  # how long the limit order stays alive

EntryMode = Literal["next_open", "pullback_236"]


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


def simulate(
    signal_idx: int,
    side: str,
    candles: list[dict[str, Any]],
    entry_mode: EntryMode,
) -> dict[str, Any]:
    """Walk forward from signal_idx+1 until TP2/SL/timeout.

    For pullback_236, the trade only opens when price reaches the 23.6
    fib retracement within PULLBACK_FILL_BARS bars after the signal.
    """
    sig = candles[signal_idx]
    L = sig["low"]
    H = sig["high"]
    rng = H - L

    if side == "BUY":
        sl = L - 0.10 * rng
        tp1 = H
        tp2 = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp1 = L
        tp2 = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    if signal_idx + 1 >= len(candles):
        return {"outcome": "no-next-bar", "filled": False, "bars_held": 0}

    # ----- entry resolution --------------------------------------------
    entry_price: float | None = None
    entry_idx: int | None = None
    fill_bars_used = 0

    if entry_mode == "next_open":
        entry_bar = candles[signal_idx + 1]
        entry_price = entry_bar["open"]
        entry_idx = signal_idx + 1
        fill_bars_used = 0
    else:  # pullback_236
        for k in range(PULLBACK_FILL_BARS):
            idx = signal_idx + 1 + k
            if idx >= len(candles):
                break
            bar = candles[idx]
            if side == "BUY" and bar["low"] <= pullback_limit:
                entry_price = pullback_limit
                entry_idx = idx
                fill_bars_used = k + 1
                break
            if side == "SELL" and bar["high"] >= pullback_limit:
                entry_price = pullback_limit
                entry_idx = idx
                fill_bars_used = k + 1
                break

    if entry_price is None or entry_idx is None:
        return {
            "outcome": "not-filled",
            "filled": False,
            "bars_held": 0,
            "entry_price": None,
            "sl": round(sl, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "pullback_limit": round(pullback_limit, 2),
            "candle_low": round(L, 2),
            "candle_high": round(H, 2),
            "candle_range": round(rng, 2),
            "max_extension_pct": 0.0,
            "max_retrace_to_sl_pct": 0.0,
            "tp1_reached": False,
            "fill_bars_used": 0,
        }

    risk = abs(entry_price - sl)

    # ----- forward simulation ------------------------------------------
    max_ext_level_pct = 0.0
    max_retrace_to_sl_pct = 0.0
    outcome = "timeout"
    bars_held = 0
    exit_price: float | None = None
    exit_time: int | None = None

    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bars_held = k + 1

        bh, bl = bar["high"], bar["low"]

        if side == "BUY":
            if bh > H:
                ext_level = (bh - L) / rng
                max_ext_level_pct = max(max_ext_level_pct, ext_level)
        else:
            if bl < L:
                ext_level = (H - bl) / rng
                max_ext_level_pct = max(max_ext_level_pct, ext_level)

        if risk > 0:
            if side == "BUY":
                drawdown = entry_price - bl
            else:
                drawdown = bh - entry_price
            if drawdown > 0:
                ret_frac = drawdown / risk
                max_retrace_to_sl_pct = max(max_retrace_to_sl_pct, ret_frac)

        if side == "BUY":
            sl_hit = bl <= sl
            tp2_hit = bh >= tp2
        else:
            sl_hit = bh >= sl
            tp2_hit = bl <= tp2

        if sl_hit and tp2_hit:
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

    tp1_reached = max_ext_level_pct >= 1.0

    return {
        "outcome": outcome,
        "filled": True,
        "bars_held": bars_held,
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "pullback_limit": round(pullback_limit, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
        "exit_time_utc": utc(exit_time).isoformat() if exit_time else None,
        "tp1_reached": tp1_reached,
        "max_extension_pct": round(max_ext_level_pct * 100, 1),
        "max_retrace_to_sl_pct": round(max_retrace_to_sl_pct * 100, 1),
        "candle_low": round(L, 2),
        "candle_high": round(H, 2),
        "candle_range": round(rng, 2),
        "fill_bars_used": fill_bars_used,
    }


def summarise(label: str, signals: list[dict[str, Any]]) -> None:
    print(f"\n=== {label} ===")
    n_total = len(signals)
    filled = [s for s in signals if s["filled"]]
    n_filled = len(filled)
    n_unfilled = n_total - n_filled
    n_tp2 = sum(1 for s in filled if s["outcome"] == "TP2")
    n_sl = sum(1 for s in filled if s["outcome"] == "SL")
    n_to = sum(1 for s in filled if s["outcome"] in ("timeout", "ran-out-of-data"))
    n_tp1 = sum(1 for s in filled if s.get("tp1_reached"))

    print(f"Total signals fired:  {n_total}")
    print(f"Filled (entry hit):   {n_filled}  ({n_filled / n_total * 100:.1f}%)")
    if n_unfilled:
        print(f"Not filled:           {n_unfilled}  ({n_unfilled / n_total * 100:.1f}%)")

    if n_filled == 0:
        print("(no filled trades — nothing to score)")
        return

    print(f"  TP2 hit (1.27 ext):  {n_tp2:>3}  ({n_tp2 / n_filled * 100:>5.1f}% of filled)")
    print(f"  TP1 reached:         {n_tp1:>3}  ({n_tp1 / n_filled * 100:>5.1f}% of filled)")
    print(f"  SL hit:              {n_sl:>3}  ({n_sl / n_filled * 100:>5.1f}% of filled)")
    print(f"  Timeout (60 bars):   {n_to:>3}  ({n_to / n_filled * 100:>5.1f}% of filled)")

    rr_wins = []
    for s in filled:
        if s["outcome"] != "TP2":
            continue
        risk = abs(s["entry_price"] - s["sl"])
        reward = abs(s["tp2"] - s["entry_price"])
        if risk > 0:
            rr_wins.append(reward / risk)

    if rr_wins:
        sum_pos = sum(rr_wins)
        gross_loss = float(n_sl)
        net = sum_pos - gross_loss
        per_trade = net / n_filled
        be_wr = 1.0 / (1.0 + sum(rr_wins) / len(rr_wins)) if rr_wins else 0
        pf = sum_pos / gross_loss if gross_loss > 0 else float("inf")
        print()
        print(f"  Mean RR per TP2 win: {sum(rr_wins) / len(rr_wins):.3f}")
        print(f"  Min  RR per TP2 win: {min(rr_wins):.3f}")
        print(f"  Max  RR per TP2 win: {max(rr_wins):.3f}")
        print(f"  Gross PnL: +{sum_pos:.2f}R wins, -{gross_loss:.2f}R losses")
        print(f"  Net PnL:   {net:+.2f} R over {n_filled} filled trades ({per_trade:+.3f} R/trade)")
        print(f"  Profit factor: {pf:.2f}")
        print(f"  Break-even WR: {be_wr * 100:.1f}%   actual WR: {n_tp2 / n_filled * 100:.1f}%")


def main() -> None:
    candles = json.loads(CACHE.read_text(encoding="utf-8"))
    candles.sort(key=lambda b: b["time"])

    print(f"Window: {utc(candles[0]['time']).isoformat()} -> {utc(candles[-1]['time']).isoformat()}")
    print(f"Bars: {len(candles)}")
    print(f"Filter: body%>={MIN_BODY_PCT}, cwick%<={MAX_CWICK_PCT}, body>={MIN_BODY_POINTS}pt, sessions=ALL")

    # Generate signal list once, then run both entry modes
    base_signals = []
    for i, b in enumerate(candles):
        if i + 1 >= len(candles):
            break
        ok, side = is_signal(b)
        if not ok:
            continue
        base_signals.append((i, side))

    print(f"\nSignals matching filter: {len(base_signals)}")

    for mode in ("next_open", "pullback_236"):
        results = []
        for i, side in base_signals:
            sim = simulate(i, side, candles, mode)  # type: ignore[arg-type]
            b = candles[i]
            results.append(
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
                    "entry_mode": mode,
                    **sim,
                }
            )
        summarise(f"Entry mode: {mode}", results)
        out_json = OUT / f"may2026-results-{mode}.json"
        out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"  Saved {len(results)} signals to {out_json.name}")


if __name__ == "__main__":
    main()
