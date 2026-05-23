"""Phase 11 backtest -- DXY-proxy alignment + relaxed M5 setup.

User goal: deployable strategy producing >=10-15 valid signals per month.

Methodology
-----------
1. DXY proxy = inverted EURUSD M5 (EUR is 57.6% of DXY basket; correlation
   between 1/EURUSD and actual DXY is empirically 0.95+). Using a proxy
   is a documented compromise -- the alternative is an external DXY feed
   that this MT5 broker doesn't expose. Synthetic 6-pair DXY would be
   more accurate but requires 4 more pair histories; we accept the small
   loss of precision in exchange for getting started.

2. DXY direction at the time of an M5 XAUUSD signal:
     bullish_dxy if 1/EURUSD M5 close[-1] > EMA(20) of 1/EURUSD
     bearish_dxy if 1/EURUSD M5 close[-1] < EMA(20) of 1/EURUSD
     neutral otherwise (close to EMA, +/- 0.05%)

3. Strict timing: at the M5 XAUUSD signal candle's close time T, only
   EURUSD bars with close time <= T are eligible. Mirrors live
   deployment.

4. The hypothesis: gold's relationship with the dollar is the strongest
   academic finding (DXY/gold correlation -0.6 to -0.8). If we filter
   to take XAUUSD shorts only when DXY is bullish (and longs when DXY
   is bearish), we should see PF lift over a relaxed M5 baseline.

Six variants
------------
  V1  Relaxed M5 + DXY-aligned (strict)        primary candidate
  V2  Relaxed M5 + DXY-aligned + NY session     adds session filter
  V3  Relaxed M5 + DXY-aligned + skip London    weaker session filter
  V4  v0.5.0 strict + DXY-aligned (strict)      compare to baseline
  V5  Relaxed M5 only (control)                 to measure DXY lift
  V6  v0.5.0 strict only (control)              the deployable baseline

Pre-committed rules
-------------------
  1. n_filled         >= 50  across 29 months
  2. PF                >  1.40
  3. losing_months    <= 7 of 29
  4. mean_RR per win  >= 0.5
  5. signals/month    >= 8 (relaxed from 10-15 to allow scientific
                            rejection of low-volume variants)

Reference
---------
DXY/gold correlation: O'Connor, Lucey, Velasco, Donaghy (2015), "The
Financial Economics of Gold -- A Survey", International Review of
Financial Analysis 41.

Astronacci methodology (Goeryadi): commercial Indonesian trading
pedagogy combining Fibonacci levels with planetary cycles. Cited as
context; specific Astronacci rules not encoded in this phase.
"""

from __future__ import annotations

import bisect
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

# DXY proxy (inverted EURUSD)
DXY_EMA_PERIOD = 20
DXY_NEUTRAL_BAND_PCT = 0.0005   # +/- 0.05% of price; treat as neutral

# Relaxed M5 setup
RELAXED_BODY_PCT = 0.65
RELAXED_BODY_POINTS = 600
RELAXED_RANGE_USD = 6.0


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def session_label(h: int) -> str:
    if 23 <= h or h < 8:  return "Asia"
    if 8 <= h < 12:        return "London"
    if 12 <= h < 22:       return "NY"
    return "Off"


# --------------------------------------------------------------------------
# DXY proxy from EURUSD
# --------------------------------------------------------------------------


def load_eurusd_for_month(month: str) -> list[dict] | None:
    path = CACHE / f"eurusd-{month}-m5.json"
    if not path.exists():
        return None
    bars = json.loads(path.read_text(encoding="utf-8"))
    bars.sort(key=lambda b: b["time"])
    return bars


def invert_to_dxy_proxy(eurusd_bars: list[dict]) -> list[dict]:
    """Convert EURUSD bars to inverted-EURUSD as a DXY proxy.

    For an inversion 1/x: the high becomes 1/low, low becomes 1/high, etc.
    """
    out = []
    for b in eurusd_bars:
        if b["high"] <= 0 or b["low"] <= 0 or b["open"] <= 0 or b["close"] <= 0:
            continue
        out.append({
            "time": b["time"],
            "open":  1.0 / b["open"],
            "high":  1.0 / b["low"],
            "low":   1.0 / b["high"],
            "close": 1.0 / b["close"],
        })
    return out


def compute_ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return [0.0] * len(values)
    out = [0.0] * len(values)
    k = 2.0 / (period + 1.0)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


# --------------------------------------------------------------------------
# DXY direction evaluator (strict timing)
# --------------------------------------------------------------------------


def latest_dxy_index_closed_before(
    dxy_bars: list[dict],
    xau_close_time: int,
) -> int:
    """Find latest DXY-proxy bar whose close-time is at or before the
    XAUUSD signal's close time."""
    bar_close_times = [b["time"] + 300 for b in dxy_bars]  # M5 closes 5 min after open
    idx = bisect.bisect_right(bar_close_times, xau_close_time) - 1
    return idx


def evaluate_dxy_direction(
    dxy_bars: list[dict],
    dxy_emas: list[float],
    dxy_idx: int,
) -> str:
    """Return 'BULL_DXY', 'BEAR_DXY', or 'NEUTRAL'."""
    if dxy_idx < DXY_EMA_PERIOD:
        return "NEUTRAL"
    close = dxy_bars[dxy_idx]["close"]
    ema = dxy_emas[dxy_idx]
    if ema <= 0:
        return "NEUTRAL"
    delta = (close - ema) / ema
    if delta > DXY_NEUTRAL_BAND_PCT:
        return "BULL_DXY"
    if delta < -DXY_NEUTRAL_BAND_PCT:
        return "BEAR_DXY"
    return "NEUTRAL"


# --------------------------------------------------------------------------
# M5 XAUUSD setup
# --------------------------------------------------------------------------


def compute_m5_features(idx: int, candles: list[dict]) -> dict[str, Any] | None:
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
    sess = session_label(utc(b["time"]).hour)
    if idx >= 8:
        prior = [candles[idx - k] for k in range(8, 0, -1)]
        diffs = [prior[k + 1]["close"] - prior[k]["close"] for k in range(7)]
        mono = sum(1 for d in diffs if (d > 0) == is_buy)
    else:
        mono = 0
    return {
        "side": side, "range": rng, "body_pct": body_pct,
        "cwick_pct": cwick_pct, "fwick_pct": fwick_pct,
        "body_points": body_points, "session": sess,
        "trend_monotonic": mono,
    }


def passes_v05_strict(f: dict) -> bool:
    return (
        f["body_pct"] >= 0.86
        and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05
        and f["body_points"] >= 1000
        and f["range"] >= 11.0
        and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


def passes_relaxed(f: dict) -> bool:
    return (
        f["body_pct"] >= RELAXED_BODY_PCT
        and f["body_points"] >= RELAXED_BODY_POINTS
        and f["range"] >= RELAXED_RANGE_USD
    )


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


@dataclass
class TradeResult:
    outcome: str
    filled: bool
    entry_price: float | None
    sl: float | None
    tp2: float | None
    rr_win: float | None


def simulate_pullback(candles: list[dict], idx: int, side: str) -> TradeResult:
    sig = candles[idx]
    L, H = sig["low"], sig["high"]
    rng = H - L
    if side == "BUY":
        sl = L - 0.10 * rng
        tp2 = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp2 = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    if idx + 1 >= len(candles):
        return TradeResult("no-next-bar", False, None, sl, tp2, None)

    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        i = idx + 1 + k
        if i >= len(candles):
            break
        bar = candles[i]
        if side == "BUY" and bar["low"] <= pullback_limit:
            entry_price = pullback_limit
            entry_idx = i
            break
        if side == "SELL" and bar["high"] >= pullback_limit:
            entry_price = pullback_limit
            entry_idx = i
            break

    if entry_price is None or entry_idx is None:
        return TradeResult("not-filled", False, None, sl, tp2, None)

    outcome = "timeout"
    for k in range(SIM_HORIZON_BARS):
        i = entry_idx + k
        if i >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[i]
        bh, bl = bar["high"], bar["low"]
        if side == "BUY":
            sl_hit = bl <= sl
            tp_hit = bh >= tp2
        else:
            sl_hit = bh >= sl
            tp_hit = bl <= tp2
        if sl_hit:
            outcome = "SL"
            break
        if tp_hit:
            outcome = "TP2"
            break

    rr_win = None
    if outcome == "TP2":
        risk = abs(entry_price - sl)
        if risk > 0:
            rr_win = abs(tp2 - entry_price) / risk

    return TradeResult(outcome, True, entry_price, sl, tp2, rr_win)


# --------------------------------------------------------------------------
# Variants
# --------------------------------------------------------------------------


@dataclass
class MonthMetrics:
    month: str
    n_signals: int = 0
    n_filled: int = 0
    n_tp: int = 0
    n_sl: int = 0
    n_to: int = 0
    n_unfilled: int = 0
    sum_rr: float = 0.0


VARIANTS: list[dict[str, Any]] = [
    {"id": "V1", "label": "Relaxed M5 + DXY-aligned",         "m5": "relaxed", "dxy": True,  "session": None},
    {"id": "V2", "label": "Relaxed M5 + DXY + NY only",       "m5": "relaxed", "dxy": True,  "session": "NY"},
    {"id": "V3", "label": "Relaxed M5 + DXY + skip London",   "m5": "relaxed", "dxy": True,  "session": "skip_london"},
    {"id": "V4", "label": "v0.5.0 strict + DXY-aligned",      "m5": "v05",     "dxy": True,  "session": None},
    {"id": "V5", "label": "Relaxed M5 only (control)",        "m5": "relaxed", "dxy": False, "session": "skip_london"},
    {"id": "V6", "label": "v0.5.0 baseline (control)",        "m5": "v05",     "dxy": False, "session": None},
]


def signal_passes(
    variant: dict,
    xau_candles: list[dict],
    dxy_bars: list[dict],
    dxy_emas: list[float],
    idx: int,
) -> tuple[bool, str | None]:
    f = compute_m5_features(idx, xau_candles)
    if not f:
        return False, None

    # M5 filter
    if variant["m5"] == "v05":
        if not passes_v05_strict(f):
            return False, None
    elif variant["m5"] == "relaxed":
        if not passes_relaxed(f):
            return False, None

    # Session
    if variant["session"] == "NY":
        if f["session"] != "NY":
            return False, None
    elif variant["session"] == "skip_london":
        if f["session"] == "London":
            return False, None

    # DXY alignment (strict timing)
    if variant["dxy"]:
        if not dxy_bars:
            return False, None
        m5_close_time = xau_candles[idx]["time"] + 300
        dxy_idx = latest_dxy_index_closed_before(dxy_bars, m5_close_time)
        direction = evaluate_dxy_direction(dxy_bars, dxy_emas, dxy_idx)
        if direction == "NEUTRAL":
            return False, None
        # SELL gold needs DXY going UP; BUY gold needs DXY going DOWN.
        if f["side"] == "SELL" and direction != "BULL_DXY":
            return False, None
        if f["side"] == "BUY" and direction != "BEAR_DXY":
            return False, None

    return True, f["side"]


def run_variant(variant: dict, months_data: dict[str, dict]) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, data in months_data.items():
        xau = data["xau"]
        dxy = data["dxy"]
        dxy_emas = data["dxy_emas"]
        m = MonthMetrics(month=month)
        for idx in range(len(xau)):
            ok, side = signal_passes(variant, xau, dxy, dxy_emas, idx)
            if not ok or side is None:
                continue
            m.n_signals += 1
            res = simulate_pullback(xau, idx, side)
            if not res.filled:
                m.n_unfilled += 1
                continue
            m.n_filled += 1
            if res.outcome == "TP2":
                m.n_tp += 1
                if res.rr_win is not None:
                    m.sum_rr += res.rr_win
            elif res.outcome == "SL":
                m.n_sl += 1
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
    n_to = sum(m.n_to for m in months)
    sum_rr = sum(m.sum_rr for m in months)
    losing = 0
    trading = 0
    for m in months:
        if m.n_filled == 0:
            continue
        trading += 1
        if m.sum_rr - m.n_sl < 0:
            losing += 1
    pf = sum_rr / n_sl if n_sl else (float("inf") if n_tp else 0.0)
    wr = n_tp / n_fill if n_fill else 0.0
    mean_rr = sum_rr / n_tp if n_tp else 0.0
    net_R = sum_rr - n_sl
    sigs_per_month = n_fill / max(1, len(months))
    return {
        "n_signals": n_sig,
        "n_filled": n_fill,
        "n_tp": n_tp,
        "n_sl": n_sl,
        "n_timeout": n_to,
        "wr": wr,
        "mean_rr": mean_rr,
        "net_R": net_R,
        "per_trade_R": net_R / n_fill if n_fill else 0.0,
        "pf": pf,
        "losing_months": losing,
        "trading_months": trading,
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


# --------------------------------------------------------------------------
# Correlation diagnostic (sanity check on the proxy)
# --------------------------------------------------------------------------


def daily_returns_correlation(months_data: dict[str, dict]) -> dict:
    """Compute daily-return correlation between XAUUSD and DXY-proxy
    across all months (sanity check the methodology).
    """
    xau_daily = {}
    dxy_daily = {}
    for month, data in months_data.items():
        for b in data["xau"]:
            day = b["time"] // 86400
            if day not in xau_daily:
                xau_daily[day] = (b["open"], b["close"])
            else:
                xau_daily[day] = (xau_daily[day][0], b["close"])
        for b in data["dxy"]:
            day = b["time"] // 86400
            if day not in dxy_daily:
                dxy_daily[day] = (b["open"], b["close"])
            else:
                dxy_daily[day] = (dxy_daily[day][0], b["close"])

    common_days = sorted(set(xau_daily.keys()) & set(dxy_daily.keys()))
    if len(common_days) < 30:
        return {"n_days": len(common_days), "correlation": None}

    xau_returns = []
    dxy_returns = []
    for d in common_days:
        xo, xc = xau_daily[d]
        do, dc = dxy_daily[d]
        if xo > 0 and do > 0:
            xau_returns.append((xc - xo) / xo)
            dxy_returns.append((dc - do) / do)

    n = len(xau_returns)
    if n < 30: return {"n_days": n, "correlation": None}
    mean_x = sum(xau_returns) / n
    mean_d = sum(dxy_returns) / n
    cov = sum((xau_returns[i] - mean_x) * (dxy_returns[i] - mean_d) for i in range(n))
    var_x = sum((xau_returns[i] - mean_x) ** 2 for i in range(n))
    var_d = sum((dxy_returns[i] - mean_d) ** 2 for i in range(n))
    if var_x <= 0 or var_d <= 0:
        return {"n_days": n, "correlation": None}
    correlation = cov / (var_x ** 0.5 * var_d ** 0.5)
    return {"n_days": n, "correlation": correlation}


# --------------------------------------------------------------------------
# Reporter
# --------------------------------------------------------------------------


def write_report(
    results: dict[str, dict],
    per_month_results: dict[str, dict[str, MonthMetrics]],
    months: list[str],
    correlation: dict,
    out_md: Path,
) -> None:
    md: list[str] = []
    md.append("# Phase 11 backtest -- DXY-proxy alignment + relaxed M5 setup\n\n")
    md.append(f"Window: {months[0]} to {months[-1]} ({len(months)} months M5 XAUUSD)\n\n")
    md.append("DXY proxy = inverted EURUSD M5. Strict timing applied for DXY direction.\n\n")
    if correlation["correlation"] is not None:
        md.append(f"**Sanity check**: XAU/DXY-proxy daily-return correlation across "
                  f"{correlation['n_days']} days = {correlation['correlation']:+.3f}.\n")
        md.append(f"(Expected: -0.6 to -0.8 per O'Connor et al 2015. ")
        md.append(f"Lower magnitude is normal for a single-pair proxy; ")
        md.append(f"hard test of the proxy: it MUST be negative.)\n\n")
    md.append("Pre-committed rules: n>=50, PF>1.40, losing_months<=7/29, mean_RR>=0.5, sigs/mo>=8\n\n")

    md.append("## Pooled aggregate per variant\n\n```\n")
    md.append(
        f"{'V':<4}  {'config':<38}  {'sigs':>5}  {'fill':>5}  "
        f"{'TP':>4}  {'SL':>4}  {'WR':>5}  {'meanRR':>7}  "
        f"{'netR':>7}  {'PF':>6}  {'losM':>6}  {'sigs/mo':>7}  {'verdict':<8}\n"
    )
    md.append("-" * 130 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg)
        md.append(
            f"{v['id']:<4}  {v['label']:<38}  "
            f"{agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp']:>4}  {agg['n_sl']:>4}  "
            f"{agg['wr'] * 100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
            f"{agg['sigs_per_month']:>6.1f}  "
            f"{'PASS' if ok else 'REJECT':<8}\n"
        )
    md.append("```\n\n")

    md.append("## Per-variant per-month detail\n\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, reasons = apply_rules(agg)
        md.append(f"### {v['id']} -- {v['label']}\n\n```\n")
        md.append(f"{'month':<10}  {'sigs':>5}  {'fill':>5}  {'TP':>4}  {'SL':>4}  {'WR':>5}  {'netR':>7}  {'PF':>6}\n")
        for month in months:
            m = per_month_results[v["id"]].get(month)
            if not m:
                continue
            net = m.sum_rr - m.n_sl
            wr = m.n_tp / m.n_filled if m.n_filled else 0.0
            pf = m.sum_rr / m.n_sl if m.n_sl else (float("inf") if m.n_tp else 0.0)
            md.append(
                f"{month:<10}  {m.n_signals:>5}  {m.n_filled:>5}  "
                f"{m.n_tp:>4}  {m.n_sl:>4}  {wr * 100:>4.1f}%  "
                f"{net:>+6.2f}R  {fmt_pf(pf):>6}\n"
            )
        md.append(f"\nVERDICT: {'PASS' if ok else 'REJECT'}")
        if reasons:
            md.append("  -- " + "; ".join(reasons))
        md.append("\n```\n\n")

    out_md.write_text("".join(md), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    months = sorted(p.stem.replace("-m5", "")
                    for p in CACHE.glob("[0-9]*-m5.json"))
    print(f"Loading {len(months)} months: {months[0]} -> {months[-1]}")

    months_data: dict[str, dict] = {}
    for slug in months:
        xau_path = CACHE / f"{slug}-m5.json"
        xau = json.loads(xau_path.read_text(encoding="utf-8"))
        xau.sort(key=lambda b: b["time"])

        eurusd = load_eurusd_for_month(slug) or []
        dxy_bars = invert_to_dxy_proxy(eurusd) if eurusd else []
        dxy_closes = [b["close"] for b in dxy_bars]
        dxy_emas = compute_ema(dxy_closes, DXY_EMA_PERIOD) if dxy_closes else []

        months_data[slug] = {
            "xau": xau, "dxy": dxy_bars, "dxy_emas": dxy_emas,
        }
        print(f"  {slug}: XAU={len(xau)}  DXY-proxy={len(dxy_bars)}")

    OUT.mkdir(parents=True, exist_ok=True)

    print("\nCorrelation sanity check...")
    corr = daily_returns_correlation(months_data)
    if corr["correlation"] is not None:
        print(f"  daily-return correlation: {corr['correlation']:+.3f} ({corr['n_days']} days)")
    else:
        print(f"  insufficient data for correlation")

    print("\nRunning 6 variants...")
    results: dict[str, dict] = {}
    per_month_results: dict[str, dict[str, MonthMetrics]] = {}
    for v in VARIANTS:
        per_month = run_variant(v, months_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, _ = apply_rules(agg)
        print(
            f"  {v['id']:<3} {v['label']:<38} "
            f"n={agg['n_filled']:>5}  WR={agg['wr'] * 100:>4.1f}%  "
            f"PF={fmt_pf(agg['pf']):>5}  netR={agg['net_R']:>+7.2f}  "
            f"sigs/mo={agg['sigs_per_month']:>5.1f}  "
            f"{'PASS' if ok else 'REJECT'}"
        )

    json_path = OUT / "phase11-results.json"
    serializable = {
        "correlation": corr,
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved raw results to {json_path}")

    md_path = OUT / "phase11-report.md"
    write_report(results, per_month_results, months, corr, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
