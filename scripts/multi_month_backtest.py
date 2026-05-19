"""Multi-month backtest: run baseline + optimized filters across every
cached month and produce a combined report.

Reads any cache/YYYY-MM-m5.json file. Writes:
  data/backtests/multi-month-results.json   per-month-per-config metrics
  data/backtests/multi-month-summary.md     human-readable comparison

For each (month, filter, mode) configuration we report:
  - signals fired
  - filled count
  - WR (TP2 hit / filled)
  - mean RR per win
  - net R, profit factor

Aggregates compute pooled WR/PF across months.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache"
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10

EntryMode = Literal["next_open", "pullback_236"]


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


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


def passes_optimized_no_round(f: dict) -> bool:
    """Optimized minus the dist_to_round_50 rule (suspected curve-fit term)."""
    return (
        f["body_pct"] >= 0.86
        and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05
        and f["body_points"] >= 1000
        and f["range"] >= 11.0
        and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


def simulate(
    signal_idx: int,
    side: str,
    candles: list[dict[str, Any]],
    entry_mode: EntryMode,
) -> dict[str, Any]:
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

    if signal_idx + 1 >= len(candles):
        return {"outcome": "no-next-bar", "filled": False}

    if entry_mode == "next_open":
        entry_price = candles[signal_idx + 1]["open"]
        entry_idx = signal_idx + 1
    else:
        entry_price = None
        entry_idx = None
        for k in range(PULLBACK_FILL_BARS):
            idx = signal_idx + 1 + k
            if idx >= len(candles):
                break
            bar = candles[idx]
            if side == "BUY" and bar["low"] <= pullback_limit:
                entry_price = pullback_limit
                entry_idx = idx
                break
            if side == "SELL" and bar["high"] >= pullback_limit:
                entry_price = pullback_limit
                entry_idx = idx
                break

    if entry_price is None:
        return {"outcome": "not-filled", "filled": False, "sl": sl, "tp2": tp2}

    outcome = "timeout"
    exit_price = None
    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bh, bl = bar["high"], bar["low"]
        if side == "BUY":
            sl_hit = bl <= sl
            tp2_hit = bh >= tp2
        else:
            sl_hit = bh >= sl
            tp2_hit = bl <= tp2
        if sl_hit:  # worst-case ordering
            outcome = "SL"
            exit_price = sl
            break
        if tp2_hit:
            outcome = "TP2"
            exit_price = tp2
            break

    return {
        "outcome": outcome,
        "filled": True,
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp2": round(tp2, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
    }


def run(candles: list[dict], filter_fn, mode: EntryMode) -> dict:
    trades = []
    for i in range(len(candles) - 1):
        f = compute_features(i, candles)
        if not f:
            continue
        if not filter_fn(f):
            continue
        sim = simulate(i, f["side"], candles, mode)
        trades.append(sim)

    n_total = len(trades)
    filled = [t for t in trades if t.get("filled")]
    n_filled = len(filled)
    n_tp2 = sum(1 for t in filled if t["outcome"] == "TP2")
    n_sl = sum(1 for t in filled if t["outcome"] == "SL")
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
    pf = sum_pos / gross_loss if gross_loss else (float("inf") if n_tp2 else 0)
    wr = n_tp2 / n_filled if n_filled else 0
    mean_rr = sum(rr_wins) / len(rr_wins) if rr_wins else 0

    return {
        "n_total": n_total,
        "n_filled": n_filled,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "wr": wr,
        "mean_rr": mean_rr,
        "net_R": net,
        "per_trade_R": net / n_filled if n_filled else 0,
        "pf": pf,
        "gross_pos_R": sum_pos,
        "gross_neg_R": gross_loss,
    }


def fmt_pf(x: float) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.2f}"


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Found cached months: {months}")

    filters = {
        "baseline": passes_baseline,
        "optimized": passes_optimized,
        "optimized_no_round": passes_optimized_no_round,
    }
    modes: list[EntryMode] = ["next_open", "pullback_236"]

    all_results: dict = {}
    for slug in months:
        path = CACHE / f"{slug}-m5.json"
        candles = json.loads(path.read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        for filt_name, fn in filters.items():
            for mode in modes:
                key = f"{slug} | {filt_name} | {mode}"
                all_results[key] = run(candles, fn, mode)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "multi-month-results.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )

    # Aggregate by (filter, mode) across months
    aggregates: dict = {}
    for filt_name in filters:
        for mode in modes:
            keys = [k for k in all_results if filt_name in k.split(" | ")[1] and mode == k.split(" | ")[2]]
            # be precise: filter name == middle component
            keys = [k for k in all_results if k.split(" | ")[1] == filt_name and k.split(" | ")[2] == mode]
            tot_filled = sum(all_results[k]["n_filled"] for k in keys)
            tot_tp2 = sum(all_results[k]["n_tp2"] for k in keys)
            tot_sl = sum(all_results[k]["n_sl"] for k in keys)
            tot_pos = sum(all_results[k]["gross_pos_R"] for k in keys)
            tot_neg = sum(all_results[k]["gross_neg_R"] for k in keys)
            net = tot_pos - tot_neg
            wr = tot_tp2 / tot_filled if tot_filled else 0
            pf = tot_pos / tot_neg if tot_neg else (float("inf") if tot_tp2 else 0)
            aggregates[f"ALL | {filt_name} | {mode}"] = {
                "n_filled": tot_filled,
                "n_tp2": tot_tp2,
                "n_sl": tot_sl,
                "wr": wr,
                "net_R": net,
                "pf": pf,
                "per_trade_R": net / tot_filled if tot_filled else 0,
            }

    # Build report
    md = ["# Multi-month backtest -- Jan-May 2026\n\n"]
    md.append(f"Months tested: {', '.join(months)}\n\n")
    md.append("Three filters x two entry modes x five months = 30 configurations.\n\n")

    md.append("## Per-month results\n\n")
    md.append("```\n")
    md.append(
        f"{'config':<46}  {'sigs':>5}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  "
        f"{'WR':>5}  {'meanRR':>6}  {'net':>7}  {'PF':>6}\n"
    )
    md.append("-" * 105 + "\n")
    for slug in months:
        for filt_name in filters:
            for mode in modes:
                key = f"{slug} | {filt_name} | {mode}"
                r = all_results[key]
                label = f"{slug} | {filt_name:<18} | {mode}"
                md.append(
                    f"{label:<46}  {r['n_total']:>5}  {r['n_filled']:>5}  "
                    f"{r['n_tp2']:>4}  {r['n_sl']:>4}  "
                    f"{r['wr'] * 100:>4.1f}%  {r['mean_rr']:>6.3f}  "
                    f"{r['net_R']:>+7.2f}  {fmt_pf(r['pf']):>6}\n"
                )
        md.append("\n")
    md.append("```\n\n")

    # Aggregate
    md.append("## Pooled aggregate (5 months)\n\n")
    md.append("```\n")
    md.append(
        f"{'config':<46}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  "
        f"{'WR':>5}  {'net':>7}  {'PF':>6}  {'per-trade':>10}\n"
    )
    md.append("-" * 100 + "\n")
    for filt_name in filters:
        for mode in modes:
            key = f"ALL | {filt_name} | {mode}"
            r = aggregates[key]
            md.append(
                f"ALL | {filt_name:<18} | {mode:<14}      "
                f"{r['n_filled']:>5}  {r['n_tp2']:>4}  {r['n_sl']:>4}  "
                f"{r['wr'] * 100:>4.1f}%  {r['net_R']:>+7.2f}  "
                f"{fmt_pf(r['pf']):>6}  {r['per_trade_R']:>+8.3f} R\n"
            )
        md.append("\n")
    md.append("```\n\n")

    # Per-month WR table for the 3 strongest configs
    md.append("## Month-over-month WR for the 3 most-relevant configs\n\n")
    md.append("Looking for stability of the WR across months. A real edge\n")
    md.append("shows roughly the same WR every month; a curve-fit shows a\n")
    md.append("blowout in one month and average elsewhere.\n\n")
    md.append("```\n")
    md.append(f"{'month':<10}  {'baseline+pull':<18}  {'optimized+pull':<18}  {'opt_no_round+pull':<18}\n")
    md.append("-" * 75 + "\n")
    for slug in months:
        cells = []
        for filt in ("baseline", "optimized", "optimized_no_round"):
            r = all_results[f"{slug} | {filt} | pullback_236"]
            cells.append(f"{r['n_filled']:>3}t {r['wr'] * 100:>4.1f}% PF{fmt_pf(r['pf'])}")
        md.append(f"{slug:<10}  {cells[0]:<18}  {cells[1]:<18}  {cells[2]:<18}\n")
    md.append("```\n\n")

    out_md = OUT / "multi-month-summary.md"
    out_md.write_text("".join(md), encoding="utf-8")
    print(f"wrote {out_md}")
    print()
    print("=== Pooled aggregate ===")
    for filt_name in filters:
        for mode in modes:
            r = aggregates[f"ALL | {filt_name} | {mode}"]
            print(
                f"  {filt_name:<22} {mode:<14} "
                f"n={r['n_filled']:>4}  WR={r['wr'] * 100:>4.1f}%  "
                f"net={r['net_R']:+.2f}R  PF={fmt_pf(r['pf'])}  "
                f"per-trade={r['per_trade_R']:+.3f}R"
            )


if __name__ == "__main__":
    main()
