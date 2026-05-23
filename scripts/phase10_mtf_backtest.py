"""Phase 10 backtest -- MTF (H1 trend bias + M5 setup confirmation).

Tests whether requiring H1 directional alignment improves the v0.5.0
momentum-candle strategy or a relaxed version of it.

User asked: "capture downtrend in H1, then wait M5 setup for sell
confirmation" (and mirror for buy).

H1 trend definition (strict, locked before running):
  Downtrend if BOTH:
    1. Last 3 H1 closes are each lower than the previous H1 close
    2. Current H1 close is below EMA(10) of H1 closes
  Uptrend: mirror.

Critical Phase-9 lesson applied:
  Strict timing -- when an M5 candle closes at time T, only H1 bars
  whose close time + 1 minute < T are eligible to define the trend.
  This prevents peeking at the in-progress H1 bar (which would only be
  fully formed in hindsight).

Variants:
  V1  H1 + v0.5.0 strict M5  (naive timing, idx-aligned H1)
  V2  H1 + v0.5.0 strict M5  (STRICT TIMING -- live realistic)
  V3  H1 + relaxed M5 SELL/BUY  (strict)
  V4  Relaxed M5 only  (control, no H1)
  V5  H1 trend + EMA pullback + v0.5.0 M5  (strict)

Pre-committed decision rules (must hold for adoption):
  1. n_filled         >= 50 across 29 months
  2. PF                >  1.40
  3. losing_months    <= 7 of 29 (~24%)
  4. mean_RR per win  >= 0.5
  5. PF lift over comparable baseline >= +0.05

If V2 doesn't lift v0.5.0 by >=0.05 PF, MTF doesn't help.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache"
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10

# H1 trend
H1_MONOTONIC_BARS = 3
H1_EMA_PERIOD = 10
H1_BAR_SECONDS = 3600

# Session windows (UTC)
LONDON_HOUR_START = 8
LONDON_HOUR_END = 12

# Relaxed M5 setup
RELAXED_BODY_PCT = 0.70
RELAXED_BODY_POINTS = 800
RELAXED_RANGE_USD = 8.0

# EMA pullback (for V5)
EMA_PULLBACK_TOLERANCE_PCT = 0.0030  # 0.30% of price; ~ ATR-relative on XAUUSD


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def session_label(h: int) -> str:
    if 23 <= h or h < 8:
        return "Asia"
    if LONDON_HOUR_START <= h < LONDON_HOUR_END:
        return "London"
    if 12 <= h < 22:
        return "NY"
    return "Off"


# --------------------------------------------------------------------------
# H1 aggregation from M5 (no extra data pull required)
# --------------------------------------------------------------------------


def aggregate_m5_to_h1(m5_candles: list[dict]) -> list[dict]:
    """Aggregate sorted M5 candles into H1 bars.

    Each H1 bar is identified by floor(time / 3600) * 3600 as its open
    time. open = first M5 open in the hour, close = last M5 close,
    high/low = max/min within the hour.
    """
    if not m5_candles:
        return []
    h1: dict[int, dict] = {}
    for c in m5_candles:
        h_open = (c["time"] // H1_BAR_SECONDS) * H1_BAR_SECONDS
        if h_open not in h1:
            h1[h_open] = {
                "time": h_open,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
            }
        else:
            b = h1[h_open]
            if c["high"] > b["high"]:
                b["high"] = c["high"]
            if c["low"] < b["low"]:
                b["low"] = c["low"]
            b["close"] = c["close"]
    bars = sorted(h1.values(), key=lambda b: b["time"])
    return bars


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
# H1 trend evaluator (strict-timing-aware)
# --------------------------------------------------------------------------


def latest_h1_index_closed_before(
    h1_bars: list[dict],
    m5_close_time: int,
    strict: bool,
) -> int:
    """Return the index of the latest H1 bar whose CLOSE time is before
    the M5 candle's close time.

    Strict mode adds a 60-second buffer: H1 bar must have closed at least
    1 minute before the M5 close, mirroring real-time behavior where the
    EA only sees the H1 bar after broker confirmation.
    """
    h1_close_times = [b["time"] + H1_BAR_SECONDS for b in h1_bars]
    cutoff = m5_close_time - (60 if strict else 0)
    idx = bisect.bisect_right(h1_close_times, cutoff) - 1
    return idx


def evaluate_h1_trend(
    h1_bars: list[dict],
    h1_idx: int,
    h1_emas: list[float],
) -> str:
    """Return 'UP', 'DOWN', or 'NONE'."""
    if h1_idx < H1_EMA_PERIOD:
        return "NONE"
    closes = [h1_bars[h1_idx - k]["close"] for k in range(H1_MONOTONIC_BARS + 1)]
    ema = h1_emas[h1_idx]
    last_close = closes[0]

    monotonic_down = all(closes[k] < closes[k + 1] for k in range(H1_MONOTONIC_BARS))
    monotonic_up = all(closes[k] > closes[k + 1] for k in range(H1_MONOTONIC_BARS))

    if monotonic_down and last_close < ema:
        return "DOWN"
    if monotonic_up and last_close > ema:
        return "UP"
    return "NONE"


def near_ema(price: float, ema: float, tolerance_pct: float) -> bool:
    if ema <= 0:
        return False
    return abs(price - ema) / ema <= tolerance_pct


# --------------------------------------------------------------------------
# M5 setup detection
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
        "side": side,
        "range": rng,
        "body_pct": body_pct,
        "cwick_pct": cwick_pct,
        "fwick_pct": fwick_pct,
        "body_points": body_points,
        "session": sess,
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
        and f["session"] != "London"
    )


# --------------------------------------------------------------------------
# Simulation (pullback_236 + fib targets, identical to multi_month)
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
# Variant logic
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
    {"id": "V1", "label": "H1 + v0.5.0 (naive timing)",  "h1": True,  "m5": "v05",     "strict": False, "ema_pullback": False},
    {"id": "V2", "label": "H1 + v0.5.0 (strict timing)", "h1": True,  "m5": "v05",     "strict": True,  "ema_pullback": False},
    {"id": "V3", "label": "H1 + relaxed M5 (strict)",    "h1": True,  "m5": "relaxed", "strict": True,  "ema_pullback": False},
    {"id": "V4", "label": "Relaxed M5 only (control)",   "h1": False, "m5": "relaxed", "strict": True,  "ema_pullback": False},
    {"id": "V5", "label": "H1 + EMA pullback + v0.5.0",  "h1": True,  "m5": "v05",     "strict": True,  "ema_pullback": True},
]


def variant_filter(
    variant: dict,
    m5_candles: list[dict],
    h1_bars: list[dict],
    h1_emas: list[float],
    idx: int,
) -> tuple[bool, str | None]:
    f = compute_m5_features(idx, m5_candles)
    if not f:
        return False, None

    # M5 check
    if variant["m5"] == "v05":
        if not passes_v05_strict(f):
            return False, None
    elif variant["m5"] == "relaxed":
        if not passes_relaxed(f):
            return False, None

    # H1 check
    if variant["h1"]:
        m5_close_time = m5_candles[idx]["time"] + 300  # M5 closes 5min after open
        h1_idx = latest_h1_index_closed_before(h1_bars, m5_close_time, variant["strict"])
        trend = evaluate_h1_trend(h1_bars, h1_idx, h1_emas)
        if trend == "NONE":
            return False, None
        # Direction match: SELL needs DOWN, BUY needs UP
        if f["side"] == "SELL" and trend != "DOWN":
            return False, None
        if f["side"] == "BUY" and trend != "UP":
            return False, None

        # EMA pullback (V5 only)
        if variant.get("ema_pullback") and h1_idx >= 0:
            ema = h1_emas[h1_idx]
            # Pullback = M5 candle's signal-side wick touched within tolerance of EMA
            sig_extreme = m5_candles[idx]["high"] if f["side"] == "SELL" else m5_candles[idx]["low"]
            if not near_ema(sig_extreme, ema, EMA_PULLBACK_TOLERANCE_PCT):
                return False, None

    return True, f["side"]


# --------------------------------------------------------------------------
# Run + aggregate
# --------------------------------------------------------------------------


def run_variant(
    variant: dict,
    months_data: dict[str, dict],
) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, data in months_data.items():
        m5_candles = data["m5"]
        h1_bars = data["h1"]
        h1_emas = data["h1_emas"]
        m = MonthMetrics(month=month)
        for idx in range(len(m5_candles)):
            ok, side = variant_filter(variant, m5_candles, h1_bars, h1_emas, idx)
            if not ok or side is None:
                continue
            m.n_signals += 1
            res = simulate_pullback(m5_candles, idx, side)
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
    }


# Reference baseline (v0.5.0 alone, computed inline here for the lift check)
def run_baseline_v05(months_data: dict[str, dict]) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, data in months_data.items():
        m5_candles = data["m5"]
        m = MonthMetrics(month=month)
        for idx in range(len(m5_candles)):
            f = compute_m5_features(idx, m5_candles)
            if not f or not passes_v05_strict(f):
                continue
            m.n_signals += 1
            res = simulate_pullback(m5_candles, idx, f["side"])
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


def apply_rules(agg: dict, baseline_pf: float) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    if agg["n_filled"] < 50:
        ok = False
        reasons.append(f"n_filled={agg['n_filled']} < 50")
    if agg["pf"] <= 1.40:
        ok = False
        reasons.append(f"PF={agg['pf']:.2f} <= 1.40")
    if agg["losing_months"] > 7:
        ok = False
        reasons.append(f"losing_months={agg['losing_months']} > 7")
    if agg["mean_rr"] < 0.5:
        ok = False
        reasons.append(f"mean_rr={agg['mean_rr']:.3f} < 0.5")
    lift = agg["pf"] - baseline_pf
    if lift < 0.05:
        ok = False
        reasons.append(f"PF lift={lift:+.2f} < +0.05 over baseline {baseline_pf:.2f}")
    return ok, reasons


def fmt_pf(x: float) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.2f}"


def write_report(
    results: dict[str, dict],
    per_month_results: dict[str, dict[str, MonthMetrics]],
    months: list[str],
    baseline_agg: dict,
    out_md: Path,
) -> None:
    md: list[str] = []
    md.append("# Phase 10 backtest -- MTF (H1 trend bias + M5 setup)\n\n")
    md.append(f"Window: {months[0]} to {months[-1]} ({len(months)} months M5 XAUUSD)\n\n")
    md.append("Five variants, pullback_236 entry on M5. ")
    md.append("Phase 9's strict-timing safeguard applied to V2/V3/V5.\n\n")

    md.append("Pre-committed rules: n>=50, PF>1.40, losing_months<=7/29, mean_RR>=0.5, ")
    md.append(f"PF lift >= +0.05 over v0.5.0 baseline (PF {baseline_agg['pf']:.2f}).\n\n")

    md.append("## v0.5.0 baseline (29 months) -- for reference\n\n```\n")
    md.append(f"n_filled  WR     PF     netR     losing_months\n")
    md.append(f"{baseline_agg['n_filled']:<8}  {baseline_agg['wr']*100:.1f}%  ")
    md.append(f"{fmt_pf(baseline_agg['pf'])}  {baseline_agg['net_R']:+.2f}R  ")
    md.append(f"{baseline_agg['losing_months']}/{baseline_agg['trading_months']}\n")
    md.append("```\n\n")

    md.append("## Pooled aggregate per variant\n\n```\n")
    md.append(
        f"{'V':<4}  {'config':<38}  {'sigs':>5}  {'fill':>5}  "
        f"{'TP':>4}  {'SL':>4}  {'WR':>5}  {'meanRR':>7}  "
        f"{'netR':>7}  {'PF':>6}  {'losM':>6}  {'lift':>6}  {'verdict':<8}\n"
    )
    md.append("-" * 130 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg, baseline_agg["pf"])
        lift = agg["pf"] - baseline_agg["pf"]
        md.append(
            f"{v['id']:<4}  {v['label']:<38}  "
            f"{agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp']:>4}  {agg['n_sl']:>4}  "
            f"{agg['wr'] * 100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
            f"{lift:>+5.2f}  "
            f"{'PASS' if ok else 'REJECT':<8}\n"
        )
    md.append("```\n\n")

    md.append("## Per-variant per-month detail\n\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, reasons = apply_rules(agg, baseline_agg["pf"])
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
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Loading {len(months)} months: {months[0]} -> {months[-1]}")

    months_data: dict[str, dict] = {}
    for slug in months:
        path = CACHE / f"{slug}-m5.json"
        m5 = json.loads(path.read_text(encoding="utf-8"))
        m5.sort(key=lambda b: b["time"])
        h1 = aggregate_m5_to_h1(m5)
        h1_closes = [b["close"] for b in h1]
        h1_emas = compute_ema(h1_closes, H1_EMA_PERIOD)
        months_data[slug] = {"m5": m5, "h1": h1, "h1_emas": h1_emas}
        print(f"  {slug}: M5={len(m5)}  H1={len(h1)}")

    OUT.mkdir(parents=True, exist_ok=True)

    print("\nComputing v0.5.0 baseline...")
    baseline_per_month = run_baseline_v05(months_data)
    baseline_agg = aggregate(baseline_per_month)
    print(f"  baseline: n={baseline_agg['n_filled']}  WR={baseline_agg['wr']*100:.1f}%  "
          f"PF={fmt_pf(baseline_agg['pf'])}  netR={baseline_agg['net_R']:+.2f}  "
          f"losM={baseline_agg['losing_months']}/{baseline_agg['trading_months']}")

    print("\nRunning 5 variants...")
    results: dict[str, dict] = {}
    per_month_results: dict[str, dict[str, MonthMetrics]] = {}
    for v in VARIANTS:
        per_month = run_variant(v, months_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, _ = apply_rules(agg, baseline_agg["pf"])
        lift = agg["pf"] - baseline_agg["pf"]
        print(
            f"  {v['id']:<3} {v['label']:<38} "
            f"n={agg['n_filled']:>4}  WR={agg['wr'] * 100:>4.1f}%  "
            f"PF={fmt_pf(agg['pf']):>5}  netR={agg['net_R']:>+6.2f}  "
            f"lift={lift:+.2f}  losM={agg['losing_months']}/{agg['trading_months']}  "
            f"{'PASS' if ok else 'REJECT'}"
        )

    json_path = OUT / "phase10-results.json"
    serializable = {
        "baseline": baseline_agg,
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved raw results to {json_path}")

    md_path = OUT / "phase10-report.md"
    write_report(results, per_month_results, months, baseline_agg, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
