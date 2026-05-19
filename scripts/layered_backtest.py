"""Layered backtest: simulate up to N concurrent open positions.

Same filter logic as the previous backtests, but instead of skipping
new signals while one trade is open (InpOnlyOnePos behavior), we let
up to MAX_CONCURRENT trades run in parallel. New signals during an
open trade are accepted as long as we're under the cap.

Risk model: each position risks exactly 1R (its own SL distance). With
N concurrent positions max, peak per-trade risk exposure is N * 1R.
PnL accounting still uses the per-position TP2/SL outcome.

Compares:
  max_concurrent = 1, 2, 3
  on both May 2026 (in-sample-ish) and April 2026 (OOS)
  baseline + optimized filters
  next_open + pullback_236 entry modes

Reads:
  cache/may2026-m5.json
  cache/april2026-m5.json

Writes:
  data/backtests/layered-comparison.md
  data/backtests/layered-results.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10

EntryMode = Literal["next_open", "pullback_236"]


# --------------------------------------------------------------------------
# Feature computation (shared with oos_validation_april.py, kept inline so
# this script is self-contained)
# --------------------------------------------------------------------------


def session_label(h: int) -> str:
    if 23 <= h or h < 8:
        return "Asia"
    if 8 <= h < 12:
        return "London"
    if 12 <= h < 22:
        return "NY"
    return "Off"


def compute_features(idx: int, candles: list[dict]) -> dict[str, Any] | None:
    b = candles[idx]
    rng = b["high"] - b["low"]
    if rng <= 0:
        return None
    body = abs(b["close"] - b["open"])
    body_pct = body / rng
    is_buy = b["close"] > b["open"]
    is_sell = b["close"] < b["open"]
    if not (is_buy or is_sell):
        return None
    side = "BUY" if is_buy else "SELL"
    close_wick = (b["high"] - b["close"]) if is_buy else (b["close"] - b["low"])
    far_wick = (b["open"] - b["low"]) if is_buy else (b["high"] - b["open"])
    cwick_pct = close_wick / rng
    fwick_pct = far_wick / rng
    body_points = body / POINT

    utc_t = datetime.fromtimestamp(b["time"], tz=timezone.utc)
    sess = session_label(utc_t.hour)

    if idx >= 8:
        prior = [candles[idx - k] for k in range(8, 0, -1)]
        diffs = [prior[k + 1]["close"] - prior[k]["close"] for k in range(7)]
        mono = sum(1 for d in diffs if (d > 0) == is_buy)
    else:
        mono = 0

    extreme = b["high"] if is_sell else b["low"]
    nearest_50 = round(extreme / 50.0) * 50
    dist_to_round_50 = abs(extreme - nearest_50)

    return {
        "side": side,
        "range": rng,
        "body_pct": body_pct,
        "cwick_pct": cwick_pct,
        "fwick_pct": fwick_pct,
        "body_points": body_points,
        "session": sess,
        "trend_monotonic": mono,
        "dist_to_round_50": dist_to_round_50,
    }


def passes_baseline(f: dict) -> bool:
    return (
        f["body_pct"] >= 0.80
        and f["cwick_pct"] <= 0.10
        and f["body_points"] >= 800
    )


def passes_optimized(f: dict) -> bool:
    return (
        f["body_pct"] >= 0.86
        and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05
        and f["body_points"] >= 1000
        and f["range"] >= 11.0
        and f["dist_to_round_50"] <= 15.0
        and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


# --------------------------------------------------------------------------
# Open-trade tracker
# --------------------------------------------------------------------------


def make_trade(signal_idx: int, side: str, candles: list[dict], mode: EntryMode) -> dict | None:
    """Set up a trade dict that we'll step forward bar-by-bar.

    For pullback_236 we record the limit price; the trade is "armed" but
    not "active" until the limit fills. Returns None if entry won't
    happen (for next_open: never None; for pullback: None if no fill in
    PULLBACK_FILL_BARS).
    """
    sig = candles[signal_idx]
    L = sig["low"]
    H = sig["high"]
    rng = H - L

    if side == "BUY":
        sl = L - 0.10 * rng
        tp2 = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp2 = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    # next_open: entry is bar signal_idx+1 open
    if mode == "next_open":
        if signal_idx + 1 >= len(candles):
            return None
        return {
            "signal_idx": signal_idx,
            "side": side,
            "entry_idx": signal_idx + 1,
            "entry_price": candles[signal_idx + 1]["open"],
            "sl": sl,
            "tp2": tp2,
            "active": True,
            "armed_until": None,
            "pullback_limit": None,
            "outcome": None,
        }

    # pullback_236: armed at the limit price, expires after PULLBACK_FILL_BARS
    return {
        "signal_idx": signal_idx,
        "side": side,
        "entry_idx": None,
        "entry_price": None,
        "sl": sl,
        "tp2": tp2,
        "active": False,  # not yet filled
        "armed_until": signal_idx + PULLBACK_FILL_BARS,
        "pullback_limit": pullback_limit,
        "outcome": None,
    }


def step_trade(trade: dict, bar_idx: int, bar: dict) -> dict | None:
    """Advance an existing trade by one bar; mutate state.

    Returns the trade if it just exited (so the caller can record the
    final outcome), else None.
    """
    if trade["outcome"] is not None:
        return None

    # Pullback armed-but-not-filled: check fill, then SL/TP for the same bar
    if not trade["active"]:
        if bar_idx > trade["armed_until"]:
            trade["outcome"] = "not-filled"
            trade["bars_held"] = 0
            return trade
        # Try to fill at the limit
        if trade["side"] == "BUY" and bar["low"] <= trade["pullback_limit"]:
            trade["entry_price"] = trade["pullback_limit"]
            trade["entry_idx"] = bar_idx
            trade["active"] = True
        elif trade["side"] == "SELL" and bar["high"] >= trade["pullback_limit"]:
            trade["entry_price"] = trade["pullback_limit"]
            trade["entry_idx"] = bar_idx
            trade["active"] = True
        else:
            return None  # still waiting

    # Active trade: check SL/TP on this bar
    bh, bl = bar["high"], bar["low"]
    side = trade["side"]
    sl = trade["sl"]
    tp2 = trade["tp2"]

    if side == "BUY":
        sl_hit = bl <= sl
        tp2_hit = bh >= tp2
    else:
        sl_hit = bh >= sl
        tp2_hit = bl <= tp2

    # Worst-case ordering: SL wins on ambiguous bars
    if sl_hit:
        trade["outcome"] = "SL"
        trade["exit_price"] = sl
        trade["exit_idx"] = bar_idx
        trade["bars_held"] = bar_idx - trade["entry_idx"] + 1
        return trade
    if tp2_hit:
        trade["outcome"] = "TP2"
        trade["exit_price"] = tp2
        trade["exit_idx"] = bar_idx
        trade["bars_held"] = bar_idx - trade["entry_idx"] + 1
        return trade

    # Timeout check
    if trade["entry_idx"] is not None and bar_idx - trade["entry_idx"] >= SIM_HORIZON_BARS:
        trade["outcome"] = "timeout"
        trade["exit_price"] = bar["close"]
        trade["exit_idx"] = bar_idx
        trade["bars_held"] = bar_idx - trade["entry_idx"] + 1
        return trade

    return None


# --------------------------------------------------------------------------
# Main layered simulation
# --------------------------------------------------------------------------


def run(
    candles: list[dict],
    filter_fn,
    mode: EntryMode,
    max_concurrent: int,
) -> dict:
    """Walk the candles, opening trades when filter fires and concurrency
    cap allows. Step all open trades forward each bar."""

    open_trades: list[dict] = []
    closed_trades: list[dict] = []
    skipped_signals = 0
    total_signals = 0

    for i, bar in enumerate(candles):
        # 1. Step every open trade forward by this bar
        still_open: list[dict] = []
        for t in open_trades:
            exited = step_trade(t, i, bar)
            if exited is not None:
                closed_trades.append(exited)
            else:
                still_open.append(t)
        open_trades = still_open

        # 2. Check for a new signal on bar i (look at the close of bar i-1
        # since signal_idx is the candle that has just closed)
        # In our convention compute_features works on bar i directly.
        f = compute_features(i, candles)
        if not f:
            continue
        if not filter_fn(f):
            continue
        total_signals += 1

        # Capacity check
        active_count = sum(1 for t in open_trades if t.get("active") or t.get("armed_until") is not None)
        if active_count >= max_concurrent:
            skipped_signals += 1
            continue

        # Open new trade (either next_open immediate, or pullback armed)
        new_trade = make_trade(i, f["side"], candles, mode)
        if new_trade is None:
            continue
        open_trades.append(new_trade)

    # Force-close anything still open at the end of the data
    last_idx = len(candles) - 1
    for t in open_trades:
        if t["outcome"] is None:
            if not t.get("active"):
                t["outcome"] = "expired-end"
                t["bars_held"] = 0
            else:
                t["outcome"] = "timeout-end"
                t["exit_price"] = candles[last_idx]["close"]
                t["bars_held"] = last_idx - (t["entry_idx"] or last_idx) + 1
            closed_trades.append(t)

    # Score
    filled = [t for t in closed_trades if t.get("entry_price") is not None and t["outcome"] in ("TP2", "SL", "timeout", "timeout-end")]
    n_filled = len(filled)
    n_tp2 = sum(1 for t in filled if t["outcome"] == "TP2")
    n_sl = sum(1 for t in filled if t["outcome"] == "SL")
    n_to = sum(1 for t in filled if t["outcome"] in ("timeout", "timeout-end"))
    n_not_filled = sum(1 for t in closed_trades if t["outcome"] in ("not-filled", "expired-end"))

    rr_wins = []
    for t in filled:
        if t["outcome"] != "TP2":
            continue
        risk = abs(t["entry_price"] - t["sl"])
        reward = abs(t["tp2"] - t["entry_price"])
        if risk > 0:
            rr_wins.append(reward / risk)

    sum_pos = sum(rr_wins)
    gross_loss = float(n_sl)
    net = sum_pos - gross_loss
    per_trade = net / n_filled if n_filled else 0
    pf = sum_pos / gross_loss if gross_loss else (float("inf") if n_tp2 else 0)
    wr = n_tp2 / n_filled if n_filled else 0
    be_wr = 1.0 / (1.0 + sum(rr_wins) / len(rr_wins)) if rr_wins else 0
    mean_rr = sum(rr_wins) / len(rr_wins) if rr_wins else 0

    return {
        "total_signals": total_signals,
        "skipped_signals": skipped_signals,
        "trades_opened": total_signals - skipped_signals,
        "n_filled": n_filled,
        "n_not_filled": n_not_filled,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "n_timeout": n_to,
        "wr": wr,
        "mean_rr": mean_rr,
        "be_wr": be_wr,
        "net_R": net,
        "per_trade_R": per_trade,
        "pf": pf,
    }


# --------------------------------------------------------------------------
# Reporter
# --------------------------------------------------------------------------


def fmt_pf(x: float) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.2f}"


def main() -> None:
    months = {
        "May 2026": ROOT / "cache" / "may2026-m5.json",
        "April 2026": ROOT / "cache" / "april2026-m5.json",
    }
    filters = {
        "baseline": passes_baseline,
        "optimized": passes_optimized,
    }
    modes: list[EntryMode] = ["next_open", "pullback_236"]
    caps = [1, 2, 3]

    all_results: dict = {}
    for month_name, path in months.items():
        candles = json.loads(path.read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        for filt_name, fn in filters.items():
            for mode in modes:
                for cap in caps:
                    key = f"{month_name} | {filt_name} | {mode} | max={cap}"
                    res = run(candles, fn, mode, cap)
                    all_results[key] = res

    # Save raw
    (OUT / "layered-results.json").write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    # Build report
    md: list[str] = []
    md.append("# Layered position backtest -- 1, 2, 3 max concurrent\n\n")
    md.append("Same filter and entry-mode logic as previous backtests, but instead of\n")
    md.append("skipping new signals while one position is open, we allow up to N\n")
    md.append("simultaneous positions per symbol. Each position carries its own SL\n")
    md.append("and TP2 from its own trigger candle.\n\n")
    md.append("Each unit of P/L is 1R based on the position's own entry-to-SL distance.\n")
    md.append("Peak risk exposure with N positions = N * 1R. PF compares gross wins\n")
    md.append("(in R) to gross losses (in R).\n\n")

    md.append("## Comparison table\n\n")
    md.append("```\n")
    md.append(f"{'cfg':<60}  {'sigs':>5}  {'skip':>5}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  {'WR':>5}  {'meanRR':>7}  {'netR':>6}  {'PF':>6}\n")
    md.append("-" * 140 + "\n")
    for month_name in months:
        for filt_name in filters:
            for mode in modes:
                for cap in caps:
                    key = f"{month_name} | {filt_name} | {mode} | max={cap}"
                    r = all_results[key]
                    md.append(
                        f"{key:<60}  "
                        f"{r['total_signals']:>5}  {r['skipped_signals']:>5}  {r['n_filled']:>5}  "
                        f"{r['n_tp2']:>4}  {r['n_sl']:>4}  {r['wr'] * 100:>4.1f}%  "
                        f"{r['mean_rr']:>6.3f}  {r['net_R']:>+6.2f}  {fmt_pf(r['pf']):>6}\n"
                    )
        md.append("\n")
    md.append("```\n\n")

    # Highlight: how does layering change the picture?
    md.append("## Effect of position-cap increase\n\n")
    md.append("For each (month, filter, mode), how does going from 1 -> 2 -> 3 max\n")
    md.append("change net R and PF?\n\n")
    md.append("```\n")
    md.append(f"{'config':<55}  {'cap=1 PF/net':<14}  {'cap=2 PF/net':<14}  {'cap=3 PF/net':<14}\n")
    md.append("-" * 110 + "\n")
    for month_name in months:
        for filt_name in filters:
            for mode in modes:
                row_label = f"{month_name} | {filt_name} | {mode}"
                cells = []
                for cap in caps:
                    r = all_results[f"{month_name} | {filt_name} | {mode} | max={cap}"]
                    cells.append(f"{fmt_pf(r['pf']):>5}/{r['net_R']:>+6.2f}")
                md.append(f"{row_label:<55}  {cells[0]:<14}  {cells[1]:<14}  {cells[2]:<14}\n")
        md.append("\n")
    md.append("```\n\n")

    # Verdict
    md.append("## Verdict\n\n")
    md.append("Look for two things:\n\n")
    md.append("1. **Does layering preserve WR?** If WR holds steady from cap=1 to cap=3,\n")
    md.append("   the signals are independent enough to layer safely. If WR drops,\n")
    md.append("   layered trades are catching the same bad regime together.\n\n")
    md.append("2. **Does layering scale net R?** A 2x or 3x net R at the same PF\n")
    md.append("   means each additional position concurrent adds value. Constant net R\n")
    md.append("   means later positions are just stealing trades from earlier ones.\n\n")
    md.append("Reading the table, focus on the OPTIMIZED + pullback_236 cells -- that\n")
    md.append("was our best surviving configuration after OOS validation.\n\n")

    out_md = OUT / "layered-comparison.md"
    out_md.write_text("".join(md), encoding="utf-8")
    print(f"wrote {out_md}")
    print()

    # Quick console summary of the most-relevant cells
    print("Key configurations (optimized + pullback_236):")
    for month_name in months:
        for cap in caps:
            r = all_results[f"{month_name} | optimized | pullback_236 | max={cap}"]
            print(
                f"  {month_name}, cap={cap}:  signals={r['total_signals']:>3}  "
                f"filled={r['n_filled']:>3}  WR={r['wr'] * 100:.1f}%  "
                f"net={r['net_R']:+.2f}R  PF={fmt_pf(r['pf'])}"
            )
        print()


if __name__ == "__main__":
    main()
