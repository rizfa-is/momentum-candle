"""Out-of-sample validation: apply the May 2026 baseline AND optimized
filters to April 2026 data.

If the optimized filter's gains generalize, the WR uplift survives.
If they don't, May was a curve-fit and we have to discard.

Reads:
  cache/april2026-m5.json

Writes:
  data/backtests/april2026-results-baseline-next_open.json
  data/backtests/april2026-results-baseline-pullback_236.json
  data/backtests/april2026-results-optimized-next_open.json
  data/backtests/april2026-results-optimized-pullback_236.json
  data/backtests/oos-validation.md
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache" / "april2026-m5.json"
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10

# Baseline filter (the user's original test)
BASELINE = {
    "min_body_pct": 0.80,
    "max_cwick_pct": 0.10,
    "min_body_points": 800,
}

# Optimized filter (8 stacked rules from May factor analysis)
OPTIMIZED = {
    "min_body_pct": 0.86,
    "max_cwick_pct": 0.10,
    "max_fwick_pct": 0.05,
    "min_body_points": 1000,
    "min_range_usd": 11.0,
    "dist_to_round_50_max": 15.0,
    "session_skip": ["London"],
    "trend_monotonic_max": 4,
}

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


def compute_features(idx: int, candles: list[dict]) -> dict[str, Any]:
    b = candles[idx]
    rng = b["high"] - b["low"]
    body = abs(b["close"] - b["open"])
    body_pct = body / rng if rng > 0 else 0
    is_buy = b["close"] > b["open"]
    is_sell = b["close"] < b["open"]
    if not (is_buy or is_sell):
        return {}
    side = "BUY" if is_buy else "SELL"
    close_wick = (b["high"] - b["close"]) if is_buy else (b["close"] - b["low"])
    far_wick = (b["open"] - b["low"]) if is_buy else (b["high"] - b["open"])
    cwick_pct = close_wick / rng if rng > 0 else 0
    fwick_pct = far_wick / rng if rng > 0 else 0
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
        f["body_pct"] >= BASELINE["min_body_pct"]
        and f["cwick_pct"] <= BASELINE["max_cwick_pct"]
        and f["body_points"] >= BASELINE["min_body_points"]
    )


def passes_optimized(f: dict) -> bool:
    if f["body_pct"] < OPTIMIZED["min_body_pct"]:
        return False
    if f["cwick_pct"] > OPTIMIZED["max_cwick_pct"]:
        return False
    if f["fwick_pct"] > OPTIMIZED["max_fwick_pct"]:
        return False
    if f["body_points"] < OPTIMIZED["min_body_points"]:
        return False
    if f["range"] < OPTIMIZED["min_range_usd"]:
        return False
    if f["dist_to_round_50"] > OPTIMIZED["dist_to_round_50_max"]:
        return False
    if f["session"] in OPTIMIZED["session_skip"]:
        return False
    if f["trend_monotonic"] > OPTIMIZED["trend_monotonic_max"]:
        return False
    return True


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

    entry_price: float | None = None
    entry_idx: int | None = None
    fill_bars_used = 0

    if entry_mode == "next_open":
        entry_price = candles[signal_idx + 1]["open"]
        entry_idx = signal_idx + 1
    else:
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
        }

    risk = abs(entry_price - sl)
    outcome = "timeout"
    bars_held = 0
    exit_price: float | None = None

    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bars_held = k + 1
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
        "bars_held": bars_held,
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
        "fill_bars_used": fill_bars_used,
    }


def summarize(label: str, signals: list[dict]) -> dict:
    filled = [s for s in signals if s.get("filled")]
    n_total = len(signals)
    n_filled = len(filled)
    n_tp2 = sum(1 for s in filled if s["outcome"] == "TP2")
    n_sl = sum(1 for s in filled if s["outcome"] == "SL")
    rr_wins = []
    for s in filled:
        if s["outcome"] != "TP2":
            continue
        risk = abs(s["entry_price"] - s["sl"])
        reward = abs(s["tp2"] - s["entry_price"])
        if risk > 0:
            rr_wins.append(reward / risk)
    sum_pos = sum(rr_wins)
    gross_loss = float(n_sl)
    net = sum_pos - gross_loss
    per_trade = net / n_filled if n_filled else 0
    pf = sum_pos / gross_loss if gross_loss else (float("inf") if n_tp2 else 0)
    wr = n_tp2 / n_filled if n_filled else 0
    be_wr = 1.0 / (1.0 + sum(rr_wins) / len(rr_wins)) if rr_wins else 0
    return {
        "label": label,
        "n_total": n_total,
        "n_filled": n_filled,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "wr": wr,
        "be_wr": be_wr,
        "mean_rr_win": sum(rr_wins) / len(rr_wins) if rr_wins else 0,
        "net_R": net,
        "per_trade_R": per_trade,
        "pf": pf,
    }


def run(candles: list[dict], filter_fn, entry_mode: EntryMode, label: str) -> tuple[list[dict], dict]:
    results = []
    for i, b in enumerate(candles):
        if i + 1 >= len(candles):
            break
        f = compute_features(i, candles)
        if not f:
            continue
        if not filter_fn(f):
            continue
        sim = simulate(i, f["side"], candles, entry_mode)
        results.append(
            {
                "idx": i,
                "time_utc": utc(b["time"]).isoformat(),
                "side": f["side"],
                "open": round(b["open"], 2),
                "high": round(b["high"], 2),
                "low": round(b["low"], 2),
                "close": round(b["close"], 2),
                "session": f["session"],
                "body_pct": round(f["body_pct"] * 100, 1),
                "cwick_pct": round(f["cwick_pct"] * 100, 1),
                "fwick_pct": round(f["fwick_pct"] * 100, 1),
                "body_points": round(f["body_points"], 0),
                "range_usd": round(f["range"], 2),
                "dist_to_round_50": round(f["dist_to_round_50"], 2),
                "trend_monotonic": f["trend_monotonic"],
                **sim,
            }
        )
    summary = summarize(label, results)
    return results, summary


def main() -> None:
    candles = json.loads(CACHE.read_text(encoding="utf-8"))
    candles.sort(key=lambda b: b["time"])
    print(f"April 2026: {len(candles)} M5 bars")
    print(f"  {utc(candles[0]['time']).isoformat()} -> {utc(candles[-1]['time']).isoformat()}")
    print()

    suites = [
        ("baseline", "next_open", passes_baseline),
        ("baseline", "pullback_236", passes_baseline),
        ("optimized", "next_open", passes_optimized),
        ("optimized", "pullback_236", passes_optimized),
    ]
    summaries = {}
    for filt_name, mode, fn in suites:
        results, summary = run(candles, fn, mode, f"{filt_name}-{mode}")
        out_file = OUT / f"april2026-results-{filt_name}-{mode}.json"
        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        summaries[(filt_name, mode)] = summary

    # Print
    for key, summ in summaries.items():
        print(f"=== {key[0]} / {key[1]} ===")
        print(f"  signals: {summ['n_total']}, filled: {summ['n_filled']}")
        print(f"  WR: {summ['wr'] * 100:.1f}%   BE-WR: {summ['be_wr'] * 100:.1f}%")
        print(f"  Mean RR: {summ['mean_rr_win']:.3f}")
        print(f"  Net: {summ['net_R']:+.2f} R   Per trade: {summ['per_trade_R']:+.3f} R   PF: {summ['pf']:.2f}")
        print()

    # Generate the OOS validation report
    md: list[str] = []
    md.append("# Out-of-sample validation -- April 2026 vs May 2026\n\n")
    md.append("Same filter logic, different month. If May was curve-fit, April will show it.\n\n")

    md.append("## April 2026 dataset\n\n")
    md.append(f"- Bars: {len(candles)} M5 candles\n")
    md.append(f"- Window: {utc(candles[0]['time']).isoformat()} -> {utc(candles[-1]['time']).isoformat()}\n\n")

    md.append("## Side-by-side comparison\n\n")
    md.append("```\n")
    md.append(f"                                MAY (in-sample)        APRIL (OOS)            DELTA\n")
    md.append(f"────────────────────────────────────────────────────────────────────────────────────────\n")

    # May numbers (from prior analysis)
    may_data = {
        ("baseline", "next_open"):    {"n": 72, "filled": 72, "wr": 0.736, "rr": 0.287, "pf": 0.80,  "net": -3.79, "per_trade": -0.053},
        ("baseline", "pullback_236"): {"n": 72, "filled": 65, "wr": 0.662, "rr": 0.586, "pf": 1.14,  "net":  3.18, "per_trade":  0.049},
        ("optimized","next_open"):    {"n": 10, "filled": 10, "wr": 1.000, "rr": 0.295, "pf": float("inf"), "net":  2.95, "per_trade":  0.295},
        ("optimized","pullback_236"): {"n": 10, "filled":  9, "wr": 0.889, "rr": 0.586, "pf": 4.68,  "net":  3.68, "per_trade":  0.409},
    }

    for filt in ("baseline", "optimized"):
        for mode in ("next_open", "pullback_236"):
            may = may_data[(filt, mode)]
            apr = summaries[(filt, mode)]
            md.append(f"\n{filt.upper()} / {mode}\n")
            md.append(f"  signals fired         {may['n']:>3}                    {apr['n_total']:>3}                    {apr['n_total'] - may['n']:+d}\n")
            md.append(f"  filled                {may['filled']:>3}                    {apr['n_filled']:>3}                    {apr['n_filled'] - may['filled']:+d}\n")
            md.append(f"  WR                    {may['wr'] * 100:>5.1f}%                {apr['wr'] * 100:>5.1f}%                {apr['wr'] * 100 - may['wr'] * 100:+.1f}pp\n")
            md.append(f"  Mean RR per win       {may['rr']:>5.3f}                 {apr['mean_rr_win']:>5.3f}                 {apr['mean_rr_win'] - may['rr']:+.3f}\n")
            pf_may_str = "inf" if may['pf'] == float("inf") else f"{may['pf']:.2f}"
            pf_apr_str = "inf" if apr['pf'] == float("inf") else f"{apr['pf']:.2f}"
            md.append(f"  Profit factor         {pf_may_str:>5}                  {pf_apr_str:>5}\n")
            md.append(f"  Net PnL               {may['net']:+5.2f} R               {apr['net_R']:+5.2f} R               {apr['net_R'] - may['net']:+.2f} R\n")
            md.append(f"  Per trade             {may['per_trade']:+.3f} R              {apr['per_trade_R']:+.3f} R              {apr['per_trade_R'] - may['per_trade']:+.3f} R\n")
    md.append("```\n\n")

    # Verdict
    md.append("## Verdict\n\n")
    apr_opt_n = summaries[("optimized","next_open")]
    apr_opt_p = summaries[("optimized","pullback_236")]
    apr_base_n = summaries[("baseline","next_open")]
    apr_base_p = summaries[("baseline","pullback_236")]

    md.append("**Pre-committed decision rule** (set before April data was pulled):\n\n")
    md.append("- If April optimized WR within 10pp of May optimized WR -> ADOPT\n")
    md.append("- If April optimized WR drops 10-25pp -> CONDITIONAL ADOPT (more data needed)\n")
    md.append("- If April optimized WR collapses to baseline or below -> REJECT (curve-fit)\n\n")

    delta_n_open_pp = (apr_opt_n['wr'] - 1.000) * 100
    delta_pull_pp = (apr_opt_p['wr'] - 0.889) * 100

    md.append(f"April optimized next_open WR:    {apr_opt_n['wr'] * 100:.1f}% (vs 100.0% in-sample, delta {delta_n_open_pp:+.1f}pp)\n")
    md.append(f"April optimized pullback_236 WR: {apr_opt_p['wr'] * 100:.1f}% (vs 88.9% in-sample, delta {delta_pull_pp:+.1f}pp)\n\n")

    md.append("April baseline next_open WR:     {:.1f}%\n".format(apr_base_n['wr'] * 100))
    md.append("April baseline pullback_236 WR:  {:.1f}%\n\n".format(apr_base_p['wr'] * 100))

    md.append("Optimized lift over baseline (April):\n")
    md.append(f"  next_open:    {(apr_opt_n['wr'] - apr_base_n['wr']) * 100:+.1f}pp\n")
    md.append(f"  pullback_236: {(apr_opt_p['wr'] - apr_base_p['wr']) * 100:+.1f}pp\n\n")

    OUT_md = OUT / "oos-validation.md"
    OUT_md.write_text("".join(md), encoding="utf-8")
    print(f"wrote {OUT_md}")


if __name__ == "__main__":
    main()
