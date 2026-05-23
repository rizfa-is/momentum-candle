"""Phase 12 backtest -- multi-symbol expansion (XAUUSD + XPDUSD).

Tests whether the v0.5.0 filter has edge on a different precious metal
(palladium / XPDUSD). Silver was unavailable on InstaForex demo, so
palladium is the substitute precious-metal counterpart.

Goal: extend the deployable universe to multiple symbols. If v0.5.0
works on XPD with comparable WR/PF, the trade frequency roughly doubles
when both symbols are scanned in parallel, addressing the 10-15+
sigs/mo target.

Methodology
-----------
- Same M5 v0.5.0 strict filter applied verbatim (no per-symbol tuning;
  per-symbol tuning would be curve-fit-prone on first contact).
- Same simulation engine (pullback_236, fib 0.586 RR, 60-bar timeout,
  worst-case ordering).
- Pre-committed thresholds same as Phase 11.

Per-symbol POINT size matters for the body-in-points filter:
  XAUUSD point = 0.01 USD     (1000pt = $10)
  XPDUSD point = 0.01 USD     (1000pt = $10) -- same scale fortunately
  
Range-in-USD threshold (11.0) is direct USD on both. We test it as-is
first; if XPDUSD has structurally smaller ranges, we'll add a relaxed
variant.
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


# Range threshold autoscale: XPDUSD trades at $1000 typical level vs gold's
# $4000-4500 -- ranges are different in absolute USD. Try literal then
# scaled.
def passes_v05_xpd_scaled(f: dict) -> bool:
    """XPD-relaxed: range floor scaled to typical XPD daily range."""
    return (
        f["body_pct"] >= 0.86 and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05 and f["body_points"] >= 200  # XPD body in points
        and f["range"] >= 3.0 and f["session"] != "London"     # XPD range floor
        and f["trend_monotonic"] <= 4
    )


@dataclass
class TradeResult:
    outcome: str
    filled: bool
    rr_win: float = 0.0


def simulate(candles: list[dict], idx: int, side: str) -> TradeResult:
    sig = candles[idx]
    L, H = sig["low"], sig["high"]
    rng = H - L
    if side == "BUY":
        sl = L - 0.10 * rng
        tp = H + 0.27 * rng
        pull = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp = L - 0.27 * rng
        pull = L + 0.236 * rng
    if idx + 1 >= len(candles):
        return TradeResult("no-next-bar", False)
    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        i = idx + 1 + k
        if i >= len(candles): break
        bar = candles[i]
        if side == "BUY" and bar["low"] <= pull:
            entry_price = pull; entry_idx = i; break
        if side == "SELL" and bar["high"] >= pull:
            entry_price = pull; entry_idx = i; break
    if entry_price is None or entry_idx is None:
        return TradeResult("not-filled", False)
    risk = abs(entry_price - sl)
    if risk <= 0:
        return TradeResult("bad-risk", False)
    outcome = "timeout"
    rr = 0.0
    for k in range(SIM_HORIZON_BARS):
        i = entry_idx + k
        if i >= len(candles): outcome = "ran-out"; break
        bar = candles[i]
        if side == "BUY":
            if bar["low"] <= sl: outcome = "SL"; break
            if bar["high"] >= tp:
                outcome = "TP"; rr = abs(tp - entry_price) / risk; break
        else:
            if bar["high"] >= sl: outcome = "SL"; break
            if bar["low"] <= tp:
                outcome = "TP"; rr = abs(tp - entry_price) / risk; break
    return TradeResult(outcome, True, rr)


@dataclass
class MonthMetrics:
    month: str
    n_signals: int = 0
    n_filled: int = 0
    n_tp: int = 0
    n_sl: int = 0
    n_to: int = 0
    sum_rr: float = 0.0


VARIANTS = [
    {"id": "V1", "label": "XAU v0.5.0 baseline (control)",       "symbol": "xauusd", "filter": passes_v05_strict},
    {"id": "V2", "label": "XPD v0.5.0 strict (literal)",         "symbol": "xpdusd", "filter": passes_v05_strict},
    {"id": "V3", "label": "XPD v0.5.0 scaled (b200/r3)",         "symbol": "xpdusd", "filter": passes_v05_xpd_scaled},
    {"id": "V4", "label": "Portfolio: XAU v0.5.0 + XPD scaled",  "symbol": "portfolio", "filter": None},
]


def load_symbol_months(prefix: str, months: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for slug in months:
        if prefix == "":
            path = CACHE / f"{slug}-m5.json"
        else:
            path = CACHE / f"{prefix}-{slug}-m5.json"
        if not path.exists():
            continue
        bars = json.loads(path.read_text(encoding="utf-8"))
        bars.sort(key=lambda b: b["time"])
        out[slug] = bars
    return out


def run_single_symbol(filter_fn, symbol_data: dict[str, list[dict]]) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, candles in symbol_data.items():
        m = MonthMetrics(month=month)
        for idx in range(len(candles)):
            f = compute_features(idx, candles)
            if not f or not filter_fn(f):
                continue
            m.n_signals += 1
            res = simulate(candles, idx, f["side"])
            if not res.filled:
                continue
            m.n_filled += 1
            if res.outcome == "TP":
                m.n_tp += 1
                m.sum_rr += res.rr_win
            elif res.outcome == "SL":
                m.n_sl += 1
            else:
                m.n_to += 1
        per_month[month] = m
    return per_month


def run_portfolio(xau_data, xpd_data) -> dict[str, MonthMetrics]:
    """Sum XAU v0.5.0 + XPD scaled per-month."""
    xau_per = run_single_symbol(passes_v05_strict, xau_data)
    xpd_per = run_single_symbol(passes_v05_xpd_scaled, xpd_data)
    per_month: dict[str, MonthMetrics] = {}
    for month in sorted(set(xau_per.keys()) | set(xpd_per.keys())):
        m = MonthMetrics(month=month)
        for src in (xau_per.get(month), xpd_per.get(month)):
            if src is None:
                continue
            m.n_signals += src.n_signals
            m.n_filled += src.n_filled
            m.n_tp += src.n_tp
            m.n_sl += src.n_sl
            m.n_to += src.n_to
            m.sum_rr += src.sum_rr
        per_month[month] = m
    return per_month


def aggregate(per_month: dict[str, MonthMetrics]) -> dict:
    months = list(per_month.values())
    n_sig = sum(m.n_signals for m in months)
    n_fill = sum(m.n_filled for m in months)
    n_tp = sum(m.n_tp for m in months)
    n_sl = sum(m.n_sl for m in months)
    n_to = sum(m.n_to for m in months)
    sum_rr = sum(m.sum_rr for m in months)
    losing = 0
    trading = 0
    for m in months:
        if m.n_filled == 0: continue
        trading += 1
        if m.sum_rr - m.n_sl < 0:
            losing += 1
    pf = sum_rr / n_sl if n_sl else (float("inf") if n_tp else 0.0)
    wr = n_tp / n_fill if n_fill else 0.0
    mean_rr = sum_rr / n_tp if n_tp else 0.0
    net_R = sum_rr - n_sl
    sigs_per_month = n_fill / max(1, len(months))
    return {
        "n_signals": n_sig, "n_filled": n_fill, "n_tp": n_tp, "n_sl": n_sl,
        "n_timeout": n_to, "wr": wr, "mean_rr": mean_rr, "net_R": net_R,
        "per_trade_R": net_R / n_fill if n_fill else 0.0, "pf": pf,
        "losing_months": losing, "trading_months": trading,
        "sigs_per_month": sigs_per_month,
    }


def apply_rules(agg: dict) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    if agg["n_filled"] < 50:
        ok = False; reasons.append(f"n_filled={agg['n_filled']} < 50")
    if agg["pf"] <= 1.40:
        ok = False; reasons.append(f"PF={agg['pf']:.2f} <= 1.40")
    if agg["losing_months"] > 7:
        ok = False; reasons.append(f"losing_months={agg['losing_months']} > 7")
    if agg["mean_rr"] < 0.5:
        ok = False; reasons.append(f"mean_rr={agg['mean_rr']:.3f} < 0.5")
    if agg["sigs_per_month"] < 8:
        ok = False; reasons.append(f"sigs/mo={agg['sigs_per_month']:.1f} < 8")
    return ok, reasons


def fmt_pf(x: float) -> str:
    if x == float("inf"): return "inf"
    return f"{x:.2f}"


def write_report(results, per_month_results, months, out_md):
    md: list[str] = []
    md.append("# Phase 12 backtest -- multi-symbol expansion (XAU + XPD)\n\n")
    md.append(f"Window: {months[0]} to {months[-1]} ({len(months)} months M5)\n\n")
    md.append("Silver (XAGUSD) was unavailable on InstaForex demo, so palladium ")
    md.append("(XPDUSD) is the precious-metal sister tested. Same v0.5.0 filter ")
    md.append("applied verbatim and a price-scaled variant.\n\n")
    md.append("Pre-committed rules: n>=50, PF>1.40, losing_months<=7/29, meanRR>=0.5, sigs/mo>=8\n\n")

    md.append("## Pooled aggregate\n\n```\n")
    md.append(f"{'V':<4}  {'config':<46}  {'sigs':>5}  {'fill':>5}  {'TP':>4}  {'SL':>4}  {'WR':>5}  {'meanRR':>7}  {'netR':>7}  {'PF':>6}  {'losM':>6}  {'sigs/mo':>7}  {'verdict':<8}\n")
    md.append("-" * 145 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg)
        md.append(
            f"{v['id']:<4}  {v['label']:<46}  {agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp']:>4}  {agg['n_sl']:>4}  {agg['wr']*100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
            f"{agg['sigs_per_month']:>6.1f}  {'PASS' if ok else 'REJECT':<8}\n"
        )
    md.append("```\n\n")

    md.append("## Per-variant per-month\n\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, reasons = apply_rules(agg)
        md.append(f"### {v['id']} -- {v['label']}\n\n```\n")
        md.append(f"{'month':<10}  {'sigs':>5}  {'fill':>5}  {'TP':>4}  {'SL':>4}  {'WR':>5}  {'netR':>7}  {'PF':>6}\n")
        for month in months:
            m = per_month_results[v["id"]].get(month)
            if not m: continue
            net = m.sum_rr - m.n_sl
            wr = m.n_tp / m.n_filled if m.n_filled else 0.0
            pf = m.sum_rr / m.n_sl if m.n_sl else (float("inf") if m.n_tp else 0.0)
            md.append(f"{month:<10}  {m.n_signals:>5}  {m.n_filled:>5}  {m.n_tp:>4}  {m.n_sl:>4}  {wr*100:>4.1f}%  {net:>+6.2f}R  {fmt_pf(pf):>6}\n")
        md.append(f"\nVERDICT: {'PASS' if ok else 'REJECT'}")
        if reasons: md.append("  -- " + "; ".join(reasons))
        md.append("\n```\n\n")
    out_md.write_text("".join(md), encoding="utf-8")


def main():
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("[0-9]*-m5.json"))
    print(f"Loading {len(months)} months XAU + XPD\n")

    xau_data = load_symbol_months("", months)
    xpd_data = load_symbol_months("xpdusd", months)
    print(f"  XAU months loaded: {len(xau_data)}")
    print(f"  XPD months loaded: {len(xpd_data)}")

    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    per_month_results = {}
    for v in VARIANTS:
        if v["symbol"] == "xauusd":
            per_month = run_single_symbol(v["filter"], xau_data)
        elif v["symbol"] == "xpdusd":
            per_month = run_single_symbol(v["filter"], xpd_data)
        elif v["symbol"] == "portfolio":
            per_month = run_portfolio(xau_data, xpd_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, _ = apply_rules(agg)
        print(
            f"  {v['id']:<3} {v['label']:<46} "
            f"n={agg['n_filled']:>4}  WR={agg['wr']*100:>4.1f}%  "
            f"PF={fmt_pf(agg['pf']):>5}  netR={agg['net_R']:>+6.2f}  "
            f"sigs/mo={agg['sigs_per_month']:>5.1f}  "
            f"{'PASS' if ok else 'REJECT'}"
        )
    json_path = OUT / "phase12-results.json"
    serializable = {
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved to {json_path}")
    md_path = OUT / "phase12-report.md"
    write_report(results, per_month_results, months, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
