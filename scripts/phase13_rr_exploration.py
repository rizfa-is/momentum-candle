"""Phase 13 backtest -- RR exploration on v0.5.0.

The fib-based TP/SL produces a 0.586 mean RR per win on M5 XAUUSD. That
fixed RR is the structural ceiling Phase 11 exposed. This phase tests
whether different exit math rebalances cadence vs quality without
changing the entry filter.

Six exit-math variants on the v0.5.0 strict filter, 29 months of M5
XAUUSD data, no new pulls.

  V1  fib_127       baseline (0.586 RR, what v0.5.0 ships)
  V2  fixed_1.0R    SL = -0.10*range, TP = 1.0R from entry
  V3  fixed_1.5R    SL same, TP = 1.5R from entry
  V4  fixed_2.0R    SL same, TP = 2.0R from entry
  V5  trailing_atr  SL same, TP = trail high/low by 0.5*ATR after 1R
  V6  fib_127_be    fib_127 with break-even shift after 0.586R floats green

Pre-committed rules: same as Phase 11.
  n_filled         >= 50
  PF                >  1.40
  losing_months    <= 7 of 29
  mean_RR per win  >= 0.5  (NOTE: this rule is dropped for fixed-R variants
                            because mean_RR for fixed_1.0R is by definition
                            ~1.0 if it hits, ~0 if not -- the rule was
                            designed for the fib system)
  sigs/mo          >= 8
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache"
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def session_label(h: int) -> str:
    if 23 <= h or h < 8: return "Asia"
    if 8 <= h < 12:       return "London"
    if 12 <= h < 22:      return "NY"
    return "Off"


def compute_atr14(candles: list[dict]) -> list[float]:
    n = len(candles)
    atr = [0.0] * n
    if n < 16: return atr
    tr = [0.0] * n
    for i in range(1, n):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    s = sum(tr[1:15])
    atr[15] = s / 14
    for i in range(16, n):
        s = s - tr[i - 14] + tr[i - 1]
        atr[i] = s / 14
    return atr


def compute_features(idx: int, candles: list[dict]) -> dict[str, Any] | None:
    b = candles[idx]
    rng = b["high"] - b["low"]
    if rng <= 0: return None
    body = abs(b["close"] - b["open"])
    body_pct = body / rng
    is_buy = b["close"] > b["open"]
    is_sell = b["close"] < b["open"]
    if not (is_buy or is_sell): return None
    side = "BUY" if is_buy else "SELL"
    cw = (b["high"] - b["close"]) if is_buy else (b["close"] - b["low"])
    fw = (b["open"] - b["low"]) if is_buy else (b["high"] - b["open"])
    if idx >= 8:
        prior = [candles[idx - k] for k in range(8, 0, -1)]
        diffs = [prior[k + 1]["close"] - prior[k]["close"] for k in range(7)]
        mono = sum(1 for d in diffs if (d > 0) == is_buy)
    else:
        mono = 0
    return {
        "side": side, "range": rng, "body_pct": body_pct,
        "cwick_pct": cw / rng, "fwick_pct": fw / rng,
        "body_points": body / POINT,
        "session": session_label(utc(b["time"]).hour),
        "trend_monotonic": mono,
    }


def passes_v05_strict(f: dict) -> bool:
    return (
        f["body_pct"] >= 0.86 and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05 and f["body_points"] >= 1000
        and f["range"] >= 11.0 and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


@dataclass
class TradeResult:
    outcome: str
    filled: bool
    rr_realized: float = 0.0   # final R outcome (-1.0 for SL, +X for TP, ~0 for BE/timeout)


def simulate_variant(
    candles: list[dict],
    atr_arr: list[float],
    idx: int,
    side: str,
    variant_id: str,
) -> TradeResult:
    sig = candles[idx]
    L, H = sig["low"], sig["high"]
    rng = H - L
    if side == "BUY":
        sl = L - 0.10 * rng
        tp_fib = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp_fib = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    if idx + 1 >= len(candles):
        return TradeResult("no-next-bar", False)

    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        i = idx + 1 + k
        if i >= len(candles): break
        bar = candles[i]
        if side == "BUY" and bar["low"] <= pullback_limit:
            entry_price = pullback_limit; entry_idx = i; break
        if side == "SELL" and bar["high"] >= pullback_limit:
            entry_price = pullback_limit; entry_idx = i; break
    if entry_price is None or entry_idx is None:
        return TradeResult("not-filled", False)

    risk = abs(entry_price - sl)
    if risk <= 0:
        return TradeResult("bad-risk", False)

    # Compute TP target by variant
    if variant_id == "V1":            # fib_127 (baseline)
        tp = tp_fib
    elif variant_id == "V2":          # fixed 1.0R
        tp = entry_price + risk if side == "BUY" else entry_price - risk
    elif variant_id == "V3":          # fixed 1.5R
        tp = entry_price + 1.5 * risk if side == "BUY" else entry_price - 1.5 * risk
    elif variant_id == "V4":          # fixed 2.0R
        tp = entry_price + 2.0 * risk if side == "BUY" else entry_price - 2.0 * risk
    elif variant_id == "V5":          # trailing ATR after 1R
        tp = None  # trailing logic below
    elif variant_id == "V6":          # fib_127 with BE shift
        tp = tp_fib
    else:
        return TradeResult("bad-variant", False)

    # Forward simulation
    cur_sl = sl
    be_shifted = False
    one_r_hit = False
    trail_extreme = entry_price  # for V5

    outcome = "timeout"
    rr_realized = 0.0

    for k in range(SIM_HORIZON_BARS):
        i = entry_idx + k
        if i >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[i]
        bh, bl = bar["high"], bar["low"]

        # V5 trailing: track favorable extreme, shift SL to (extreme - 0.5*ATR)
        # only after 1R is reached.
        if variant_id == "V5":
            if side == "BUY":
                if not one_r_hit and bh >= entry_price + risk:
                    one_r_hit = True
                if one_r_hit:
                    trail_extreme = max(trail_extreme, bh)
                    atr_now = atr_arr[entry_idx + k] if entry_idx + k < len(atr_arr) else 0.0
                    if atr_now > 0:
                        new_sl = trail_extreme - 0.5 * atr_now
                        if new_sl > cur_sl:
                            cur_sl = new_sl
                if bl <= cur_sl:
                    outcome = "TRAIL_OUT"
                    rr_realized = (cur_sl - entry_price) / risk
                    break
            else:
                if not one_r_hit and bl <= entry_price - risk:
                    one_r_hit = True
                if one_r_hit:
                    trail_extreme = min(trail_extreme, bl)
                    atr_now = atr_arr[entry_idx + k] if entry_idx + k < len(atr_arr) else 0.0
                    if atr_now > 0:
                        new_sl = trail_extreme + 0.5 * atr_now
                        if new_sl < cur_sl:
                            cur_sl = new_sl
                if bh >= cur_sl:
                    outcome = "TRAIL_OUT"
                    rr_realized = (entry_price - cur_sl) / risk
                    break
            # also catch initial SL
            if not one_r_hit:
                if side == "BUY" and bl <= cur_sl:
                    outcome = "SL"; rr_realized = -1.0; break
                if side == "SELL" and bh >= cur_sl:
                    outcome = "SL"; rr_realized = -1.0; break
            continue  # V5 has its own SL handling; don't fall to common branch

        # V6 break-even shift after 0.586R unrealized
        if variant_id == "V6" and not be_shifted:
            be_target = 0.586 * risk
            if side == "BUY" and bh - entry_price >= be_target:
                cur_sl = entry_price
                be_shifted = True
            elif side == "SELL" and entry_price - bl >= be_target:
                cur_sl = entry_price
                be_shifted = True

        # SL / TP check
        if side == "BUY":
            sl_hit = bl <= cur_sl
            tp_hit = (bh >= tp) if tp is not None else False
        else:
            sl_hit = bh >= cur_sl
            tp_hit = (bl <= tp) if tp is not None else False

        if sl_hit:
            if cur_sl == entry_price:
                outcome = "BE"; rr_realized = 0.0
            else:
                outcome = "SL"; rr_realized = -1.0
            break
        if tp_hit:
            outcome = "TP"
            rr_realized = abs(tp - entry_price) / risk
            break

    return TradeResult(outcome, True, rr_realized)


@dataclass
class MonthMetrics:
    month: str
    n_signals: int = 0
    n_filled: int = 0
    n_tp: int = 0
    n_sl: int = 0
    n_be: int = 0
    n_to: int = 0
    sum_rr_pos: float = 0.0
    sum_rr_neg: float = 0.0


VARIANTS = [
    {"id": "V1", "label": "fib_127 baseline (v0.5.0 ships this)"},
    {"id": "V2", "label": "fixed 1.0R TP"},
    {"id": "V3", "label": "fixed 1.5R TP"},
    {"id": "V4", "label": "fixed 2.0R TP"},
    {"id": "V5", "label": "trailing ATR after 1R"},
    {"id": "V6", "label": "fib_127 + break-even at 0.586R"},
]


def run_variant(variant_id: str, months_data: dict[str, dict]) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, data in months_data.items():
        candles = data["candles"]
        atr_arr = data["atr"]
        m = MonthMetrics(month=month)
        for idx in range(len(candles)):
            f = compute_features(idx, candles)
            if not f or not passes_v05_strict(f):
                continue
            m.n_signals += 1
            res = simulate_variant(candles, atr_arr, idx, f["side"], variant_id)
            if not res.filled:
                continue
            m.n_filled += 1
            if res.outcome == "TP":
                m.n_tp += 1
                m.sum_rr_pos += res.rr_realized
            elif res.outcome == "SL":
                m.n_sl += 1
                m.sum_rr_neg += abs(res.rr_realized)
            elif res.outcome == "BE":
                m.n_be += 1
            elif res.outcome == "TRAIL_OUT":
                # treat as either tp-equivalent or partial loss
                if res.rr_realized > 0:
                    m.n_tp += 1
                    m.sum_rr_pos += res.rr_realized
                elif res.rr_realized < 0:
                    m.n_sl += 1
                    m.sum_rr_neg += abs(res.rr_realized)
                else:
                    m.n_be += 1
            else:
                m.n_to += 1
        per_month[month] = m
    return per_month


def aggregate(per_month: dict[str, MonthMetrics]) -> dict:
    months = list(per_month.values())
    n_sig = sum(m.n_signals for m in months)
    n_fill = sum(m.n_filled for m in months)
    n_tp = sum(m.n_tp for m in months)
    n_sl = sum(m.n_sl for m in months)
    n_be = sum(m.n_be for m in months)
    n_to = sum(m.n_to for m in months)
    sum_pos = sum(m.sum_rr_pos for m in months)
    sum_neg = sum(m.sum_rr_neg for m in months)

    losing = 0
    trading = 0
    for m in months:
        if m.n_filled == 0:
            continue
        trading += 1
        if m.sum_rr_pos - m.sum_rr_neg < 0:
            losing += 1

    pf = sum_pos / sum_neg if sum_neg > 0 else (float("inf") if n_tp else 0.0)
    wr = n_tp / n_fill if n_fill else 0.0
    mean_rr = sum_pos / n_tp if n_tp else 0.0
    net_R = sum_pos - sum_neg
    sigs_per_month = n_fill / max(1, len(months))
    return {
        "n_signals": n_sig, "n_filled": n_fill,
        "n_tp": n_tp, "n_sl": n_sl, "n_be": n_be, "n_timeout": n_to,
        "wr": wr, "mean_rr": mean_rr, "net_R": net_R,
        "per_trade_R": net_R / n_fill if n_fill else 0.0,
        "pf": pf,
        "losing_months": losing, "trading_months": trading,
        "sigs_per_month": sigs_per_month,
    }


def apply_rules(agg: dict, variant_id: str) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    if agg["n_filled"] < 50:
        ok = False; reasons.append(f"n_filled={agg['n_filled']} < 50")
    if agg["pf"] <= 1.40:
        ok = False; reasons.append(f"PF={agg['pf']:.2f} <= 1.40")
    if agg["losing_months"] > 7:
        ok = False; reasons.append(f"losing_months={agg['losing_months']} > 7")
    # mean_rr rule applies only to fib variants where it was originally calibrated
    if variant_id in ("V1", "V6") and agg["mean_rr"] < 0.5:
        ok = False; reasons.append(f"mean_rr={agg['mean_rr']:.3f} < 0.5")
    if agg["sigs_per_month"] < 8:
        ok = False; reasons.append(f"sigs/mo={agg['sigs_per_month']:.1f} < 8")
    return ok, reasons


def fmt_pf(x: float) -> str:
    if x == float("inf"): return "inf"
    return f"{x:.2f}"


def write_report(
    results: dict[str, dict],
    per_month_results: dict[str, dict[str, MonthMetrics]],
    months: list[str],
    out_md: Path,
) -> None:
    md: list[str] = []
    md.append("# Phase 13 backtest -- RR exploration on v0.5.0\n\n")
    md.append(f"Window: {months[0]} to {months[-1]} ({len(months)} months M5 XAUUSD)\n\n")
    md.append("Six exit-math variants on the v0.5.0 strict entry filter.\n\n")

    md.append("## Pooled aggregate per variant\n\n```\n")
    md.append(f"{'V':<4}  {'config':<42}  {'sigs':>5}  {'fill':>5}  {'TP':>4}  {'SL':>4}  {'BE':>3}  {'WR':>5}  {'meanRR':>7}  {'netR':>7}  {'PF':>6}  {'losM':>6}  {'sigs/mo':>7}  {'verdict':<8}\n")
    md.append("-" * 145 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg, v["id"])
        md.append(
            f"{v['id']:<4}  {v['label']:<42}  {agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp']:>4}  {agg['n_sl']:>4}  {agg['n_be']:>3}  "
            f"{agg['wr']*100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
            f"{agg['sigs_per_month']:>6.1f}  "
            f"{'PASS' if ok else 'REJECT':<8}\n"
        )
    md.append("```\n\n")

    md.append("## Per-variant per-month detail\n\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, reasons = apply_rules(agg, v["id"])
        md.append(f"### {v['id']} -- {v['label']}\n\n```\n")
        md.append(f"{'month':<10}  {'sigs':>5}  {'fill':>5}  {'TP':>4}  {'SL':>4}  {'BE':>3}  {'netR':>7}  {'PF':>6}\n")
        for month in months:
            m = per_month_results[v["id"]].get(month)
            if not m: continue
            net = m.sum_rr_pos - m.sum_rr_neg
            pf = m.sum_rr_pos / m.sum_rr_neg if m.sum_rr_neg > 0 else (float("inf") if m.n_tp else 0.0)
            md.append(f"{month:<10}  {m.n_signals:>5}  {m.n_filled:>5}  {m.n_tp:>4}  {m.n_sl:>4}  {m.n_be:>3}  {net:>+6.2f}R  {fmt_pf(pf):>6}\n")
        md.append(f"\nVERDICT: {'PASS' if ok else 'REJECT'}")
        if reasons:
            md.append("  -- " + "; ".join(reasons))
        md.append("\n```\n\n")

    out_md.write_text("".join(md), encoding="utf-8")


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("[0-9]*-m5.json"))
    print(f"Loading {len(months)} months: {months[0]} -> {months[-1]}")
    months_data: dict[str, dict] = {}
    for slug in months:
        candles = json.loads((CACHE / f"{slug}-m5.json").read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        months_data[slug] = {"candles": candles, "atr": compute_atr14(candles)}

    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    per_month_results: dict[str, dict[str, MonthMetrics]] = {}
    for v in VARIANTS:
        per_month = run_variant(v["id"], months_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, _ = apply_rules(agg, v["id"])
        print(
            f"  {v['id']:<3} {v['label']:<42} "
            f"n={agg['n_filled']:>4}  WR={agg['wr']*100:>4.1f}%  "
            f"PF={fmt_pf(agg['pf']):>5}  netR={agg['net_R']:>+6.2f}  "
            f"meanRR={agg['mean_rr']:.3f}  sigs/mo={agg['sigs_per_month']:>5.1f}  "
            f"{'PASS' if ok else 'REJECT'}"
        )

    json_path = OUT / "phase13-results.json"
    serializable = {
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved raw results to {json_path}")
    md_path = OUT / "phase13-report.md"
    write_report(results, per_month_results, months, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
