"""Factor analysis on May 2026 backtest results.

For each of the 72 signals fired, computes a wide feature set and
correlates each against TP2 outcome (the 1.27 extension hit / not hit)
in both entry modes.

Features tested:
  Geometric:
    - body_pct
    - close_wick_pct
    - far_wick_pct
    - body_points
    - range
    - body / volume ratio (just body_points / tick_volume)
  Volatility:
    - R5     (range / mean prior 5 ranges)
    - R20    (range / mean prior 20 ranges)
    - V5     (tick_volume / mean prior 5)
    - V20    (tick_volume / mean prior 20)
    - ATR14
    - range / ATR14
  Session:
    - utc_hour
    - is_asia, is_london, is_ny
  Trend / context:
    - prior 8 bars: count of monotonic-with-direction closes
    - prior 8 bars: net direction strength (close[t-1] vs close[t-8])
    - engulfs prior bar
    - inside-bar relationship
  Price-level:
    - distance to nearest 50 (round number) in points
    - distance to nearest 100
    - day's high/low proximity (signal extreme vs day extreme)
  Bar position in session:
    - first 2 hours of Asia / London / NY (session open premium?)
    - last 2 hours (session close)

For each feature, the script:
  1. Splits signals into 2-3 buckets (by quantile or category)
  2. Computes TP2 hit rate per bucket for each entry mode
  3. Reports lift / drag vs the baseline 73.6% (next_open) or 66.2% (pullback)

Goal: find filters that raise win rate above the break-even threshold
(77.7% next_open, 63.1% pullback).

Reads:
  cache/may2026-m5.json
  data/backtests/may2026-results-next_open.json
  data/backtests/may2026-results-pullback_236.json

Writes:
  data/backtests/may2026-factor-analysis.json   raw feature dump per signal
  data/backtests/may2026-factor-analysis.md     human-readable report
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache" / "may2026-m5.json"
RESULTS_NEXT = ROOT / "data" / "backtests" / "may2026-results-next_open.json"
RESULTS_PULL = ROOT / "data" / "backtests" / "may2026-results-pullback_236.json"
OUT_JSON = ROOT / "data" / "backtests" / "may2026-factor-analysis.json"
OUT_MD = ROOT / "data" / "backtests" / "may2026-factor-analysis.md"

POINT = 0.01
BASELINE_WR_NEXT = 0.7361
BASELINE_WR_PULL = 0.6615  # 43/65


def session_label(h: int) -> str:
    if 23 <= h or h < 8:
        return "Asia"
    if 8 <= h < 12:
        return "London"
    if 12 <= h < 22:
        return "NY"
    return "Off"


def true_range(prev_c: float, h: float, lo: float) -> float:
    return max(h - lo, abs(h - prev_c), abs(lo - prev_c))


def wilder_atr_at(idx: int, period: int, candles: list[dict]) -> float | None:
    if idx < period + 1:
        return None
    seed = sum(
        true_range(candles[idx - period + k - 1]["close"], candles[idx - period + k]["high"], candles[idx - period + k]["low"])
        for k in range(period)
    ) / period
    atr = seed
    for k in range(period, period + 1):
        prev_c = candles[idx - 1]["close"]
        tr = true_range(prev_c, candles[idx]["high"], candles[idx]["low"])
        atr = (atr * (period - 1) + tr) / period
    return atr


def compute_features(signal_idx: int, side: str, candles: list[dict]) -> dict[str, Any]:
    b = candles[signal_idx]
    rng = b["high"] - b["low"]
    body = abs(b["close"] - b["open"])
    body_pct = body / rng if rng > 0 else 0
    is_buy = side == "BUY"
    close_wick = (b["high"] - b["close"]) if is_buy else (b["close"] - b["low"])
    far_wick = (b["open"] - b["low"]) if is_buy else (b["high"] - b["open"])
    close_wick_pct = close_wick / rng if rng > 0 else 0
    far_wick_pct = far_wick / rng if rng > 0 else 0
    body_points = body / POINT

    # baselines
    def mean_range(n: int) -> float:
        if signal_idx - n < 0:
            return 0
        return statistics.mean(candles[signal_idx - k]["high"] - candles[signal_idx - k]["low"] for k in range(1, n + 1))

    def mean_vol(n: int) -> float:
        if signal_idx - n < 0:
            return 0
        return statistics.mean(candles[signal_idx - k]["tick_volume"] for k in range(1, n + 1))

    mr5 = mean_range(5)
    mr20 = mean_range(20)
    mv5 = mean_vol(5)
    mv20 = mean_vol(20)
    R5 = rng / mr5 if mr5 > 0 else 0
    R20 = rng / mr20 if mr20 > 0 else 0
    V5 = b["tick_volume"] / mv5 if mv5 > 0 else 0
    V20 = b["tick_volume"] / mv20 if mv20 > 0 else 0

    atr14 = wilder_atr_at(signal_idx, 14, candles)
    rng_over_atr = (rng / atr14) if atr14 else 0

    # Session
    utc_t = datetime.fromtimestamp(b["time"], tz=timezone.utc)
    h = utc_t.hour
    sess = session_label(h)

    # Trend prior 8 bars
    if signal_idx >= 8:
        prior = [candles[signal_idx - k] for k in range(8, 0, -1)]
        diffs = [prior[k + 1]["close"] - prior[k]["close"] for k in range(7)]
        if is_buy:
            mono = sum(1 for d in diffs if d > 0)
        else:
            mono = sum(1 for d in diffs if d < 0)
        net_drift = candles[signal_idx - 1]["close"] - candles[signal_idx - 8]["close"]
        trend_aligned = (net_drift > 0 and is_buy) or (net_drift < 0 and not is_buy)
        trend_against = (net_drift > 0 and not is_buy) or (net_drift < 0 and is_buy)
    else:
        mono = 0
        net_drift = 0
        trend_aligned = False
        trend_against = False

    # Engulfing prior bar
    if signal_idx >= 1:
        prev = candles[signal_idx - 1]
        if is_buy:
            engulfs = b["open"] <= prev["close"] and b["close"] > prev["high"]
        else:
            engulfs = b["open"] >= prev["close"] and b["close"] < prev["low"]
    else:
        engulfs = False

    # Round-number proximity (XAUUSD: nearest 10 USD multiple)
    extreme = b["high"] if not is_buy else b["low"]
    nearest_10 = round(extreme / 10.0) * 10
    dist_to_round_10 = abs(extreme - nearest_10)
    nearest_50 = round(extreme / 50.0) * 50
    dist_to_round_50 = abs(extreme - nearest_50)

    # Day high/low proximity (within the same UTC day so far)
    day_start_t = int(datetime(utc_t.year, utc_t.month, utc_t.day, tzinfo=timezone.utc).timestamp())
    day_so_far = [c for c in candles[max(0, signal_idx - 300):signal_idx + 1] if c["time"] >= day_start_t]
    if day_so_far:
        day_high = max(c["high"] for c in day_so_far)
        day_low = min(c["low"] for c in day_so_far)
        if is_buy:
            # BUY signal -- did it just print above day high (breakout)?
            at_day_high = b["high"] >= day_high - 0.5
            at_day_low = b["low"] <= day_low + 1.5
        else:
            at_day_high = b["high"] >= day_high - 1.5
            at_day_low = b["low"] <= day_low + 0.5
    else:
        at_day_high = False
        at_day_low = False

    # Local-N max same-direction range (dominance)
    if signal_idx >= 5:
        same_dir_ranges = []
        for k in range(1, 6):
            p = candles[signal_idx - k]
            p_is_buy = p["close"] > p["open"]
            if p_is_buy == is_buy:
                same_dir_ranges.append(p["high"] - p["low"])
        if same_dir_ranges:
            dominance = rng / max(same_dir_ranges)
        else:
            dominance = float("inf")  # no prior same-direction bar, trivially dominant
    else:
        dominance = 0

    # First-bar-of-session premium
    bar_of_session = 0
    if sess == "Asia":
        bar_of_session = (h - 23) % 24 if h >= 23 else h + 1
    elif sess == "London":
        bar_of_session = h - 8
    elif sess == "NY":
        bar_of_session = h - 12
    early_session = bar_of_session <= 1  # first hour of any session

    return {
        "body_pct": round(body_pct, 4),
        "close_wick_pct": round(close_wick_pct, 4),
        "far_wick_pct": round(far_wick_pct, 4),
        "body_points": round(body_points, 0),
        "range": round(rng, 2),
        "R5": round(R5, 3),
        "R20": round(R20, 3),
        "V5": round(V5, 3),
        "V20": round(V20, 3),
        "atr14": round(atr14, 3) if atr14 else None,
        "range_over_atr": round(rng_over_atr, 3),
        "session": sess,
        "utc_hour": h,
        "trend_monotonic": mono,
        "trend_aligned": trend_aligned,
        "trend_against": trend_against,
        "engulfs_prior": engulfs,
        "dist_to_round_10": round(dist_to_round_10, 2),
        "dist_to_round_50": round(dist_to_round_50, 2),
        "near_round_10": dist_to_round_10 <= 2.0,
        "near_round_50": dist_to_round_50 <= 5.0,
        "at_day_high": at_day_high,
        "at_day_low": at_day_low,
        "dominance_max5": round(dominance, 3) if dominance != float("inf") else 99.0,
        "early_session": early_session,
    }


def split_winrates(signals: list[dict], feature: str, mode: str) -> dict[str, Any]:
    """Group by feature value, return TP2 win rate per group."""
    grouped: dict[str, list[bool]] = {}
    for s in signals:
        if mode == "pullback_236" and not s.get("filled", True):
            continue
        v = s["features"].get(feature)
        if v is None:
            continue
        # Discretize boolean / categorical / numeric
        if isinstance(v, bool):
            key = "Yes" if v else "No"
        elif isinstance(v, str):
            key = v
        else:
            # numeric -- bucket later (handled outside)
            key = str(v)
        grouped.setdefault(key, []).append(s["outcome"] == "TP2")

    return {k: {"n": len(v), "tp2_rate": (sum(v) / len(v)) if v else 0.0} for k, v in grouped.items()}


def numeric_buckets(signals: list[dict], feature: str, mode: str, bins: list[tuple[float, float, str]]) -> dict[str, Any]:
    """Group numeric feature into provided (low, high, label) bins."""
    out: dict[str, list[bool]] = {label: [] for _, _, label in bins}
    for s in signals:
        if mode == "pullback_236" and not s.get("filled", True):
            continue
        v = s["features"].get(feature)
        if v is None:
            continue
        for low, high, label in bins:
            if low <= v < high:
                out[label].append(s["outcome"] == "TP2")
                break
    return {k: {"n": len(v), "tp2_rate": (sum(v) / len(v)) if v else 0.0} for k, v in out.items()}


def main() -> None:
    candles = json.loads(CACHE.read_text(encoding="utf-8"))
    candles.sort(key=lambda b: b["time"])
    next_results = json.loads(RESULTS_NEXT.read_text(encoding="utf-8"))
    pull_results = json.loads(RESULTS_PULL.read_text(encoding="utf-8"))

    # Compute features once and merge into both result sets
    for r in next_results:
        r["features"] = compute_features(r["idx"], r["side"], candles)
    for r in pull_results:
        r["features"] = compute_features(r["idx"], r["side"], candles)

    # Save raw enriched data
    OUT_JSON.write_text(json.dumps({"next_open": next_results, "pullback_236": pull_results}, indent=2), encoding="utf-8")

    # ----- Build the analysis report -----
    md: list[str] = []
    md.append("# May 2026 backtest -- factor analysis\n")
    md.append("Investigates which features separate TP2 winners from SL losers in the 72-signal May 2026 dataset.\n")
    md.append(f"Baseline WR -- next_open: {BASELINE_WR_NEXT * 100:.1f}%, pullback_236: {BASELINE_WR_PULL * 100:.1f}%\n")
    md.append("Break-even WR needed -- next_open: 77.7%, pullback_236: 63.1%\n\n")

    def report_categorical(title: str, feature: str) -> None:
        md.append(f"## {title} (`{feature}`)\n\n")
        md.append("| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |\n")
        md.append("|---|---:|---:|---:|---:|---:|---:|\n")
        n_groups = split_winrates(next_results, feature, "next_open")
        p_groups = split_winrates(pull_results, feature, "pullback_236")
        keys = sorted(set(list(n_groups.keys()) + list(p_groups.keys())))
        for k in keys:
            ng = n_groups.get(k, {"n": 0, "tp2_rate": 0.0})
            pg = p_groups.get(k, {"n": 0, "tp2_rate": 0.0})
            n_lift = (ng["tp2_rate"] - BASELINE_WR_NEXT) * 100 if ng["n"] else 0
            p_lift = (pg["tp2_rate"] - BASELINE_WR_PULL) * 100 if pg["n"] else 0
            md.append(
                f"| {k} | {ng['n']} | {ng['tp2_rate'] * 100:.1f}% | {n_lift:+.1f}pp | "
                f"{pg['n']} | {pg['tp2_rate'] * 100:.1f}% | {p_lift:+.1f}pp |\n"
            )
        md.append("\n")

    def report_numeric(title: str, feature: str, bins: list[tuple[float, float, str]]) -> None:
        md.append(f"## {title} (`{feature}`)\n\n")
        md.append("| Bucket | next_open n | next_open WR | lift | pullback n | pullback WR | lift |\n")
        md.append("|---|---:|---:|---:|---:|---:|---:|\n")
        n_groups = numeric_buckets(next_results, feature, "next_open", bins)
        p_groups = numeric_buckets(pull_results, feature, "pullback_236", bins)
        for _, _, label in bins:
            ng = n_groups.get(label, {"n": 0, "tp2_rate": 0.0})
            pg = p_groups.get(label, {"n": 0, "tp2_rate": 0.0})
            n_lift = (ng["tp2_rate"] - BASELINE_WR_NEXT) * 100 if ng["n"] else 0
            p_lift = (pg["tp2_rate"] - BASELINE_WR_PULL) * 100 if pg["n"] else 0
            md.append(
                f"| {label} | {ng['n']} | {ng['tp2_rate'] * 100:.1f}% | {n_lift:+.1f}pp | "
                f"{pg['n']} | {pg['tp2_rate'] * 100:.1f}% | {p_lift:+.1f}pp |\n"
            )
        md.append("\n")

    md.append("---\n\n# Categorical / boolean factors\n\n")
    report_categorical("Session", "session")
    report_categorical("Engulfs prior bar", "engulfs_prior")
    report_categorical("Trend aligned (prior 8 bars)", "trend_aligned")
    report_categorical("Trend against (prior 8 bars)", "trend_against")
    report_categorical("Near round 10 (within 2 USD)", "near_round_10")
    report_categorical("Near round 50 (within 5 USD)", "near_round_50")
    report_categorical("At day high (BUY) / day low (SELL)", "at_day_low")
    report_categorical("Against day extreme (BUY at day high / SELL at day low)", "at_day_high")
    report_categorical("Early session (first hour)", "early_session")

    md.append("---\n\n# Numeric factors\n\n")
    report_numeric("Body %", "body_pct", [(0.80, 0.85, "0.80-0.85"), (0.85, 0.90, "0.85-0.90"), (0.90, 0.95, "0.90-0.95"), (0.95, 1.01, "0.95-1.00")])
    report_numeric("Close-wick %", "close_wick_pct", [(0, 0.02, "0-2%"), (0.02, 0.05, "2-5%"), (0.05, 0.08, "5-8%"), (0.08, 0.11, "8-10%")])
    report_numeric("Far-wick %", "far_wick_pct", [(0, 0.02, "0-2%"), (0.02, 0.05, "2-5%"), (0.05, 0.10, "5-10%"), (0.10, 0.20, "10-20%"), (0.20, 1.0, ">20%")])
    report_numeric("Body in points", "body_points", [(800, 1000, "800-1000"), (1000, 1300, "1000-1300"), (1300, 1700, "1300-1700"), (1700, 5000, ">1700")])
    report_numeric("Range", "range", [(8, 11, "8-11"), (11, 14, "11-14"), (14, 18, "14-18"), (18, 100, ">18")])
    report_numeric("R5 (range / mean prior 5)", "R5", [(0, 1.0, "<1.0"), (1.0, 1.5, "1.0-1.5"), (1.5, 2.5, "1.5-2.5"), (2.5, 100, ">2.5")])
    report_numeric("V5 (volume / mean prior 5)", "V5", [(0, 0.9, "<0.9"), (0.9, 1.2, "0.9-1.2"), (1.2, 1.6, "1.2-1.6"), (1.6, 100, ">1.6")])
    report_numeric("Range / ATR(14)", "range_over_atr", [(0, 1.0, "<1.0"), (1.0, 1.5, "1.0-1.5"), (1.5, 2.5, "1.5-2.5"), (2.5, 100, ">2.5")])
    report_numeric("Trend monotonic count (prior 7 transitions)", "trend_monotonic", [(0, 3, "0-2"), (3, 5, "3-4"), (5, 7, "5-6"), (7, 8, "7")])
    report_numeric("Distance to nearest 10", "dist_to_round_10", [(0, 1, "0-1"), (1, 3, "1-3"), (3, 5, "3-5"), (5, 100, ">5")])
    report_numeric("Distance to nearest 50", "dist_to_round_50", [(0, 5, "0-5"), (5, 15, "5-15"), (15, 30, "15-30"), (30, 100, ">30")])
    report_numeric("Dominance (range / max prior-5 same-dir range)", "dominance_max5", [(0, 1.0, "<1.0"), (1.0, 1.5, "1.0-1.5"), (1.5, 2.5, "1.5-2.5"), (2.5, 100, ">2.5")])

    # ----- Best-performing combinations (interaction) -----
    md.append("---\n\n# Best 2-factor combinations\n\n")
    md.append("Looking for non-trivial interactions where two filters together produce a high TP2 rate at meaningful sample size (>=8 trades).\n\n")

    candidates_n = [(s, "next_open", BASELINE_WR_NEXT) for s in next_results]
    candidates_p = [(s, "pullback_236", BASELINE_WR_PULL) for s in pull_results if s.get("filled", True)]

    def feature_predicate(s: dict, key: str, val: Any) -> bool:
        f = s["features"]
        if key == "session":
            return f["session"] == val
        if key == "engulfs_prior":
            return f["engulfs_prior"] == val
        if key == "near_round_10":
            return f["near_round_10"] == val
        if key == "trend_against":
            return f["trend_against"] == val
        if key == "early_session":
            return f["early_session"] == val
        if key == "at_day_low":
            return f["at_day_low"] == val
        return False

    def metric(filtered: list[tuple[dict, str, float]]) -> tuple[int, float]:
        if not filtered:
            return 0, 0.0
        wins = sum(1 for s, _, _ in filtered if s["outcome"] == "TP2")
        return len(filtered), wins / len(filtered)

    # Probe a handful of promising combos
    combos = [
        [("session", "Asia"), ("engulfs_prior", True)],
        [("session", "Asia"), ("near_round_10", False)],
        [("session", "NY"), ("trend_against", False)],
        [("session", "NY"), ("at_day_low", False)],
        [("session", "Asia"), ("at_day_low", False)],
        [("session", "London")],
        [("session", "Asia")],
        [("session", "NY")],
        [("near_round_10", False)],
        [("trend_against", False)],
        [("engulfs_prior", True)],
        [("at_day_low", False)],
        [("session", "Asia"), ("trend_against", False)],
        [("session", "NY"), ("near_round_10", False)],
        [("session", "Asia"), ("near_round_10", False), ("trend_against", False)],
    ]
    md.append("| Filter | next_open n / WR | pullback n / WR |\n")
    md.append("|---|---|---|\n")
    for combo in combos:
        nf = [(s, m, b) for s, m, b in candidates_n if all(feature_predicate(s, k, v) for k, v in combo)]
        pf = [(s, m, b) for s, m, b in candidates_p if all(feature_predicate(s, k, v) for k, v in combo)]
        n_n, n_w = metric(nf)
        p_n, p_w = metric(pf)
        label = " AND ".join(f"{k}={v}" for k, v in combo)
        md.append(f"| {label} | {n_n} / {n_w * 100:.1f}% | {p_n} / {p_w * 100:.1f}% |\n")

    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
