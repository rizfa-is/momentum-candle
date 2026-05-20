"""Phase 5 backtest: FADE failed 3WS/3BC at major S/R.

Phase 4 found that 3WS at support has WR ~21% on a 1.27-extension target.
That's a strong systematic signal -- likely market makers running
liquidity sweeps below obvious support before letting price continue.
The Phase 4 report's deferred hypothesis: instead of trading WITH the
pattern, FADE the failure.

Fade strategy:
  1. Detect 3WS pattern at major support (Phase 4's `sr_at_level`)
  2. Wait FAILURE_WINDOW bars for failure: price closes below anchor
  3. SHORT the breakdown
     - SL above the pattern's highest high (where the bull thesis lived)
     - TP at next major support below, or fixed 2R
  4. Mirror for 3BC at resistance (failure = close above anchor; LONG)

Variants:
  fade_market         enter at failure-bar's NEXT-bar open
  fade_retest         enter via limit at the broken anchor (price retest)
  fade_2r             enter market, target fixed 2R

Reads:  cache/2026-01-m5.json .. cache/2026-05-m5.json
Writes: data/backtests/phase5-results.json
        data/backtests/phase5-report.md
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
RETEST_FILL_BARS = 8

# Pattern thresholds (matched to Phase 4 for apples-to-apples)
MIN_BODY_PCT = 0.55
MAX_WICK_PCT = 0.30
MIN_BODY_POINTS = 300
USE_REVERSAL_CTX = True

# S/R parameters (matched to Phase 4)
SR_BAND_ATR_MULT = 0.6
SR_LOOKBACK = 500
SR_CLUSTER_ATR_MULT = 0.5
SR_MIN_TOUCHES = 3
SR_PIVOT_LEFT = 10
SR_PIVOT_RIGHT = 10
SR_ROUND_STEP = 50.0

# Fade-specific parameters
FAILURE_WINDOW = 3                # bars to wait for failure
FAILURE_PIERCE_MULT = 0.10        # bar close must clear anchor by this much * ATR

EntryMode = Literal["fade_market", "fade_retest", "fade_2r"]


# ------------------------------------------------------------------
# ATR
# ------------------------------------------------------------------


def wilder_atr_at(idx: int, candles: list[dict], period: int = 14) -> float | None:
    if idx < period + 1:
        return None
    trs: list[float] = []
    for i in range(idx - period + 1, idx + 1):
        h = candles[i]["high"]
        lo = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    return sum(trs) / period


# ------------------------------------------------------------------
# Pattern detection (same as Phase 4)
# ------------------------------------------------------------------


def is_bull_candle(b: dict) -> bool:
    rng = b["high"] - b["low"]
    if rng <= 0 or b["close"] <= b["open"]:
        return False
    body = b["close"] - b["open"]
    body_pct = body / rng
    upper_wick_pct = (b["high"] - b["close"]) / rng
    if body_pct < MIN_BODY_PCT:
        return False
    if upper_wick_pct > MAX_WICK_PCT:
        return False
    if body / POINT < MIN_BODY_POINTS:
        return False
    return True


def is_bear_candle(b: dict) -> bool:
    rng = b["high"] - b["low"]
    if rng <= 0 or b["close"] >= b["open"]:
        return False
    body = b["open"] - b["close"]
    body_pct = body / rng
    lower_wick_pct = (b["close"] - b["low"]) / rng
    if body_pct < MIN_BODY_PCT:
        return False
    if lower_wick_pct > MAX_WICK_PCT:
        return False
    if body / POINT < MIN_BODY_POINTS:
        return False
    return True


def detect_pattern(i: int, candles: list[dict]) -> str | None:
    if i < 3:
        return None
    b1, b2, b3 = candles[i - 2], candles[i - 1], candles[i]
    if is_bull_candle(b1) and is_bull_candle(b2) and is_bull_candle(b3):
        if b3["close"] > b2["close"] > b1["close"]:
            if USE_REVERSAL_CTX:
                prev = candles[i - 3]
                if not (prev["close"] < prev["open"]):
                    return None
            return "BUY"
    if is_bear_candle(b1) and is_bear_candle(b2) and is_bear_candle(b3):
        if b3["close"] < b2["close"] < b1["close"]:
            if USE_REVERSAL_CTX:
                prev = candles[i - 3]
                if not (prev["close"] > prev["open"]):
                    return None
            return "SELL"
    return None


# ------------------------------------------------------------------
# S/R level scan (same as Phase 4)
# ------------------------------------------------------------------


def detect_pivots(
    candles: list[dict],
    end_idx: int,
    pivot_left: int,
    pivot_right: int,
    lookback: int,
) -> list[tuple[float, str]]:
    start_idx = max(pivot_left, end_idx - lookback)
    last_safe = end_idx - pivot_right
    pivots: list[tuple[float, str]] = []
    if last_safe <= start_idx:
        return pivots
    for k in range(start_idx, last_safe):
        h = candles[k]["high"]
        lo = candles[k]["low"]
        is_high = True
        is_low = True
        for j in range(1, pivot_left + 1):
            if candles[k - j]["high"] >= h:
                is_high = False
            if candles[k - j]["low"] <= lo:
                is_low = False
            if not is_high and not is_low:
                break
        if is_high or is_low:
            for j in range(1, pivot_right + 1):
                if candles[k + j]["high"] >= h:
                    is_high = False
                if candles[k + j]["low"] <= lo:
                    is_low = False
                if not is_high and not is_low:
                    break
        if is_high:
            pivots.append((float(h), "H"))
        if is_low:
            pivots.append((float(lo), "L"))
    return pivots


def cluster_levels(
    pivots: list[tuple[float, str]],
    radius: float,
    min_touches: int,
) -> list[float]:
    if not pivots or radius <= 0:
        return []
    sorted_pivots = sorted(pivots, key=lambda p: p[0])
    clusters: list[list[float]] = []
    current = [sorted_pivots[0][0]]
    for price, _ in sorted_pivots[1:]:
        mean = sum(current) / len(current)
        if abs(price - mean) <= radius:
            current.append(price)
        else:
            clusters.append(current)
            current = [price]
    clusters.append(current)
    return [sum(c) / len(c) for c in clusters if len(c) >= min_touches]


def round_levels_near(price: float, step: float, radius: float) -> list[float]:
    if step <= 0:
        return []
    nearest = round(price / step) * step
    out: list[float] = [nearest]
    k = 1
    while k * step <= radius:
        out.append(nearest + k * step)
        out.append(nearest - k * step)
        k += 1
    return out


def get_levels_at(candles: list[dict], i: int, atr: float) -> list[float]:
    if atr <= 0:
        return []
    pivots = detect_pivots(
        candles, end_idx=i,
        pivot_left=SR_PIVOT_LEFT,
        pivot_right=SR_PIVOT_RIGHT,
        lookback=SR_LOOKBACK,
    )
    radius = SR_CLUSTER_ATR_MULT * atr
    swing = cluster_levels(pivots, radius, SR_MIN_TOUCHES)
    rounds = round_levels_near(candles[i]["close"], SR_ROUND_STEP, atr * 10.0)
    return swing + rounds


def find_anchor_level(
    side: str,
    candles: list[dict],
    i: int,
    levels: list[float],
    atr: float,
) -> float | None:
    if not levels or atr <= 0:
        return None
    band = SR_BAND_ATR_MULT * atr
    extreme = candles[i - 2]["low"] if side == "BUY" else candles[i - 2]["high"]
    candidates = [L for L in levels if abs(L - extreme) <= band]
    if not candidates:
        return None
    if side == "BUY":
        below = [L for L in candidates if L <= extreme + band]
        return max(below) if below else None
    else:
        above = [L for L in candidates if L >= extreme - band]
        return min(above) if above else None


def find_next_level(
    side: str, current: float, levels: list[float], min_distance: float
) -> float | None:
    if not levels or min_distance < 0:
        return None
    if side == "BUY":
        above = [L for L in levels if L >= current + min_distance]
        return min(above) if above else None
    else:
        below = [L for L in levels if L <= current - min_distance]
        return max(below) if below else None


# ------------------------------------------------------------------
# Failure detection
# ------------------------------------------------------------------


def detect_failure(
    side: str,
    candles: list[dict],
    pattern_end_idx: int,
    anchor: float,
    atr: float,
) -> int | None:
    """Look for failure within FAILURE_WINDOW bars after pattern_end_idx.

    For BUY 3WS at support: failure = close below anchor (bull broke).
    For SELL 3BC at resistance: failure = close above anchor (bear broke).

    Returns the index of the failure bar, or None.
    """
    pierce = FAILURE_PIERCE_MULT * atr
    for k in range(1, FAILURE_WINDOW + 1):
        idx = pattern_end_idx + k
        if idx >= len(candles):
            return None
        bar = candles[idx]
        if side == "BUY" and bar["close"] < anchor - pierce:
            return idx
        if side == "SELL" and bar["close"] > anchor + pierce:
            return idx
    return None


# ------------------------------------------------------------------
# Fade simulation
# ------------------------------------------------------------------


def simulate_fade(
    failure_side: str,        # original pattern side: 'BUY' = 3WS at support failed; we go SHORT
    fade_side: str,           # actual trade side after inversion
    candles: list[dict],
    pattern_start_idx: int,   # i-2 from detect_pattern
    pattern_end_idx: int,     # i (newest bar of trio)
    failure_idx: int,
    anchor: float,
    levels: list[float],
    atr: float,
    entry_mode: EntryMode,
) -> dict:
    """Run a fade trade.

    For failed 3WS (BUY pattern failed) -> we SELL.
    For failed 3BC (SELL pattern failed) -> we BUY.

    SL anchor = the pattern's extreme on the OPPOSITE side of fade direction
      (where the original pattern's thesis was strongest).
    """
    pattern_high = max(b["high"] for b in candles[pattern_start_idx : pattern_end_idx + 1])
    pattern_low  = min(b["low"]  for b in candles[pattern_start_idx : pattern_end_idx + 1])

    # ----- entry -----
    if failure_idx + 1 >= len(candles):
        return {"outcome": "no-next-bar", "filled": False}

    entry_price: float | None = None
    entry_idx: int | None = None

    if entry_mode == "fade_market":
        entry_price = candles[failure_idx + 1]["open"]
        entry_idx = failure_idx + 1
    elif entry_mode == "fade_2r":
        entry_price = candles[failure_idx + 1]["open"]
        entry_idx = failure_idx + 1
    else:  # fade_retest -- limit at anchor (the broken level acts as new resistance/support)
        for k in range(RETEST_FILL_BARS):
            idx = failure_idx + 1 + k
            if idx >= len(candles):
                break
            bar = candles[idx]
            if fade_side == "SELL" and bar["high"] >= anchor:
                entry_price = anchor
                entry_idx = idx
                break
            if fade_side == "BUY" and bar["low"] <= anchor:
                entry_price = anchor
                entry_idx = idx
                break
        if entry_price is None:
            return {"outcome": "not-filled", "filled": False}

    # ----- SL -----
    cushion = 0.20 * atr
    if fade_side == "SELL":
        sl = pattern_high + cushion  # original 3WS's top
    else:
        sl = pattern_low - cushion   # original 3BC's bottom

    risk = abs(entry_price - sl)
    if risk <= 0:
        return {"outcome": "zero-risk", "filled": False}

    # ----- TP -----
    if entry_mode == "fade_2r":
        if fade_side == "SELL":
            tp = entry_price - 2 * risk
        else:
            tp = entry_price + 2 * risk
    else:
        # next major level in the fade direction
        next_l = find_next_level(fade_side, entry_price, levels, atr * 0.30)
        if next_l is None:
            return {"outcome": "no-tp-level", "filled": False}
        tp = next_l

    # Sanity
    if fade_side == "SELL" and tp >= entry_price:
        return {"outcome": "tp-too-close", "filled": False}
    if fade_side == "BUY" and tp <= entry_price:
        return {"outcome": "tp-too-close", "filled": False}

    # ----- forward sim -----
    outcome = "timeout"
    exit_price: float | None = None
    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        if fade_side == "SELL":
            sl_hit = bar["high"] >= sl
            tp_hit = bar["low"] <= tp
        else:
            sl_hit = bar["low"] <= sl
            tp_hit = bar["high"] >= tp
        if sl_hit:
            outcome = "SL"
            exit_price = sl
            break
        if tp_hit:
            outcome = "TP"
            exit_price = tp
            break

    rr = abs(tp - entry_price) / risk

    return {
        "outcome": outcome,
        "filled": True,
        "fade_side": fade_side,
        "original_pattern": failure_side,
        "anchor": round(anchor, 2),
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
        "rr_target": round(rr, 3),
        "failure_bars": failure_idx - pattern_end_idx,
    }


# ------------------------------------------------------------------
# Variant runner
# ------------------------------------------------------------------


VARIANTS: list[dict[str, Any]] = [
    {"name": "fade_market", "entry": "fade_market"},
    {"name": "fade_retest", "entry": "fade_retest"},
    {"name": "fade_2r", "entry": "fade_2r"},
]


def run_variant(candles: list[dict], variant: dict[str, Any]) -> dict:
    entry_mode: EntryMode = variant["entry"]

    trades: list[dict] = []
    detected_patterns = 0
    no_anchor = 0
    no_failure = 0
    other_skip = 0

    for i in range(3, len(candles) - FAILURE_WINDOW - 2):
        side = detect_pattern(i, candles)
        if side is None:
            continue
        detected_patterns += 1

        atr = wilder_atr_at(i, candles)
        if atr is None or atr <= 0:
            other_skip += 1
            continue

        levels = get_levels_at(candles, i, atr)
        anchor = find_anchor_level(side, candles, i, levels, atr)
        if anchor is None:
            no_anchor += 1
            continue

        failure_idx = detect_failure(side, candles, i, anchor, atr)
        if failure_idx is None:
            no_failure += 1
            continue

        # Pattern failed -> fade it
        fade_side = "SELL" if side == "BUY" else "BUY"

        sim = simulate_fade(
            failure_side=side,
            fade_side=fade_side,
            candles=candles,
            pattern_start_idx=i - 2,
            pattern_end_idx=i,
            failure_idx=failure_idx,
            anchor=anchor,
            levels=levels,
            atr=atr,
            entry_mode=entry_mode,
        )
        if sim.get("filled"):
            trades.append(sim)
        else:
            other_skip += 1

    n_filled = len(trades)
    n_tp = sum(1 for t in trades if t["outcome"] == "TP")
    n_sl = sum(1 for t in trades if t["outcome"] == "SL")

    rr_wins: list[float] = [t["rr_target"] for t in trades if t["outcome"] == "TP"]
    sum_pos = sum(rr_wins)
    gross_loss = float(n_sl)
    net = sum_pos - gross_loss
    pf = sum_pos / gross_loss if gross_loss else (math.inf if n_tp else 0)
    wr = n_tp / n_filled if n_filled else 0
    mean_rr = sum(rr_wins) / len(rr_wins) if rr_wins else 0

    # Failure rate among detected-with-anchor
    qualified = detected_patterns - no_anchor
    failed = qualified - no_failure - other_skip
    failure_rate = failed / qualified if qualified else 0

    return {
        "detected_patterns": detected_patterns,
        "qualified_at_level": qualified,
        "no_anchor": no_anchor,
        "no_failure": no_failure,
        "other_skip": other_skip,
        "failure_rate_at_level": failure_rate,
        "n_filled": n_filled,
        "n_tp": n_tp,
        "n_sl": n_sl,
        "wr": wr,
        "mean_rr_target": mean_rr,
        "net_R": net,
        "pf": pf,
        "per_trade_R": net / n_filled if n_filled else 0,
        "gross_pos_R": sum_pos,
        "gross_neg_R": gross_loss,
    }


# ------------------------------------------------------------------


def fmt_pf(x: float) -> str:
    return "inf" if x == math.inf else f"{x:.2f}"


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Months: {months}")
    print(f"Variants: {[v['name'] for v in VARIANTS]}")

    all_results: dict[str, dict] = {}

    for slug in months:
        candles = json.loads((CACHE / f"{slug}-m5.json").read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        for variant in VARIANTS:
            key = f"{slug} | {variant['name']}"
            print(f"  running {key} ...")
            all_results[key] = run_variant(candles, variant)

    aggregates: dict[str, dict] = {}
    for variant in VARIANTS:
        keys = [k for k in all_results if k.endswith(f"| {variant['name']}")]
        agg = {
            "detected_patterns": sum(all_results[k]["detected_patterns"] for k in keys),
            "qualified_at_level": sum(all_results[k]["qualified_at_level"] for k in keys),
            "n_filled": sum(all_results[k]["n_filled"] for k in keys),
            "n_tp": sum(all_results[k]["n_tp"] for k in keys),
            "n_sl": sum(all_results[k]["n_sl"] for k in keys),
            "no_failure": sum(all_results[k]["no_failure"] for k in keys),
            "gross_pos_R": sum(all_results[k]["gross_pos_R"] for k in keys),
            "gross_neg_R": sum(all_results[k]["gross_neg_R"] for k in keys),
        }
        agg["wr"] = agg["n_tp"] / agg["n_filled"] if agg["n_filled"] else 0
        agg["net_R"] = agg["gross_pos_R"] - agg["gross_neg_R"]
        agg["pf"] = (
            agg["gross_pos_R"] / agg["gross_neg_R"]
            if agg["gross_neg_R"]
            else (math.inf if agg["n_tp"] else 0)
        )
        agg["per_trade_R"] = agg["net_R"] / agg["n_filled"] if agg["n_filled"] else 0
        if agg["n_tp"]:
            agg["mean_rr_target"] = sum(
                all_results[k]["mean_rr_target"] * all_results[k]["n_tp"]
                for k in keys
            ) / agg["n_tp"]
        else:
            agg["mean_rr_target"] = 0.0
        # pattern failure rate
        if agg["qualified_at_level"]:
            agg["failure_rate_at_level"] = (
                agg["qualified_at_level"] - agg["no_failure"]
            ) / agg["qualified_at_level"]
        else:
            agg["failure_rate_at_level"] = 0.0
        aggregates[variant["name"]] = agg

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase5-results.json").write_text(
        json.dumps({"per_month": all_results, "aggregates": aggregates}, indent=2, default=str),
        encoding="utf-8",
    )

    print()
    print("=== Aggregate (5 months) ===")
    print(f"{'variant':<14}  {'detect':>6}  {'qual':>5}  {'fail%':>6}  {'n':>4}  {'WR':>6}  {'meanRR':>7}  {'PF':>6}  {'net':>7}  {'per-tr':>8}")
    for v in VARIANTS:
        a = aggregates[v["name"]]
        print(
            f"{v['name']:<14}  {a['detected_patterns']:>6}  "
            f"{a['qualified_at_level']:>5}  "
            f"{a['failure_rate_at_level'] * 100:>5.1f}%  "
            f"{a['n_filled']:>4}  {a['wr'] * 100:>5.1f}%  "
            f"{a['mean_rr_target']:>7.3f}  {fmt_pf(a['pf']):>6}  "
            f"{a['net_R']:>7.2f}  {a['per_trade_R']:>+8.3f}"
        )

    md: list[str] = []
    md.append("# Phase 5 backtest -- FADE failed 3WS/3BC at major S/R\n\n")
    md.append("Phase 4 found 3WS at support has WR 21% on 1.27-extension targets;\n")
    md.append("3BC at resistance was similar. Hypothesis: market makers run liquidity\n")
    md.append("sweeps below obvious support before letting price continue. The failure\n")
    md.append("itself is the signal -- fade it instead of trade it.\n\n")

    md.append("## Strategy\n\n")
    md.append("```\n")
    md.append("1. Detect 3WS at major support (Phase 4's `sr_at_level` filter)\n")
    md.append("2. Wait FAILURE_WINDOW=3 bars for failure: close < anchor - 0.10*ATR\n")
    md.append("3. SHORT the breakdown:\n")
    md.append("   SL = pattern_high + 0.20*ATR  (above the bull thesis's strongest point)\n")
    md.append("   TP = next major support below (or fixed 2R for the *_2r variant)\n")
    md.append("4. Mirror for 3BC at resistance: failure = close above anchor; LONG\n")
    md.append("```\n\n")

    md.append("## Three variants\n\n")
    md.append("| Variant | Entry | TP target |\n")
    md.append("|---|---|---|\n")
    md.append("| `fade_market` | next-bar open after failure bar | next major level |\n")
    md.append("| `fade_retest` | limit at the broken anchor (price retest) | next major level |\n")
    md.append("| `fade_2r` | next-bar open after failure bar | fixed 2R |\n\n")

    md.append("## Pooled aggregate (Jan-May 2026)\n\n")
    md.append("```\n")
    md.append(f"{'variant':<14}  {'detect':>6}  {'qual':>5}  {'fail%':>6}  {'n':>4}  {'WR':>6}  {'meanRR':>7}  {'PF':>6}  {'net':>7}  {'per-tr':>8}\n")
    md.append("-" * 110 + "\n")
    for v in VARIANTS:
        a = aggregates[v["name"]]
        md.append(
            f"{v['name']:<14}  {a['detected_patterns']:>6}  "
            f"{a['qualified_at_level']:>5}  "
            f"{a['failure_rate_at_level'] * 100:>5.1f}%  "
            f"{a['n_filled']:>4}  {a['wr'] * 100:>5.1f}%  "
            f"{a['mean_rr_target']:>7.3f}  {fmt_pf(a['pf']):>6}  "
            f"{a['net_R']:>7.2f}  {a['per_trade_R']:>+8.3f}\n"
        )
    md.append("```\n\n")
    md.append("Column key:\n")
    md.append("- detect: total 3WS+3BC patterns detected\n")
    md.append("- qual: patterns at a major S/R level (anchor found)\n")
    md.append("- fail%: % of qualified patterns that failed within 3 bars\n")
    md.append("- n: filled fade trades\n")
    md.append("- WR: win rate of the fade\n\n")

    md.append("## Per-month detail\n\n")
    md.append("```\n")
    md.append(f"{'config':<28}  {'detect':>6}  {'qual':>5}  {'fail':>5}  {'n':>4}  {'WR':>6}  {'PF':>6}  {'net':>7}\n")
    md.append("-" * 90 + "\n")
    for slug in months:
        for v in VARIANTS:
            r = all_results[f"{slug} | {v['name']}"]
            md.append(
                f"{slug} | {v['name']:<14}  "
                f"{r['detected_patterns']:>6}  {r['qualified_at_level']:>5}  "
                f"{int((r['qualified_at_level'] - r['no_failure'])):>5}  "
                f"{r['n_filled']:>4}  {r['wr'] * 100:>5.1f}%  "
                f"{fmt_pf(r['pf']):>6}  {r['net_R']:>7.2f}\n"
            )
        md.append("\n")
    md.append("```\n\n")

    (OUT / "phase5-report.md").write_text("".join(md), encoding="utf-8")
    print()
    print(f"wrote {OUT / 'phase5-report.md'}")


if __name__ == "__main__":
    main()
