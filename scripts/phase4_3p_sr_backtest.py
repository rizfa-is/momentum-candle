"""Phase 4 backtest: ThreeSoldiersCrows + S/R combined strategy.

Tests whether combining the classical 3WS/3BC pattern with S/R-zone
context produces a tradeable strategy on M5 XAUUSD across Jan-May 2026.

Pattern definition:
  Three White Soldiers (BUY): 3 consecutive bullish candles
    - close > open on each
    - close[shift] > close[shift+1] > close[shift+2]  (rising)
    - body% >= MIN_BODY_PCT (per candle)
    - upper-wick% <= MAX_WICK_PCT (per candle)
    - body in points >= MIN_BODY_POINTS (per candle)
    - reversal context: bar at shift+3 must be bearish (BEAR-BULL-BULL-BULL)

  Three Black Crows (SELL): mirror.

  shift convention: shift=0 is the most recently CLOSED bar, the
  trio's NEWEST bar.

Strategy variants tested (6 total):

  pure_3p_market      no S/R    next-bar-open entry  pattern_low SL  1.27ext TP
  pure_3p_pullback    no S/R    50% retrace entry    pattern_low SL  1.27ext TP
  sr_at_level         at level  next-bar-open entry  level break SL  next level TP
  sr_at_level_2r      at level  next-bar-open entry  level break SL  2R TP
  sr_bounce           bouncing  next-bar-open entry  level break SL  next level TP
  sr_bounce_2r        bouncing  next-bar-open entry  level break SL  2R TP

S/R modes:
  no S/R     no level filter
  at level   bar1's outer extreme (low for BUY, high for SELL) is within
              SR_BAND * ATR(14) of a major support (BUY) / resistance (SELL)
  bouncing   bar1 PIERCED below the support and bar3 closed back above it
              (or mirror for SELL); strict rejection structure

S/R levels are computed at signal time using the same algorithm as
mt5_mvp.strategies.support_resistance.find_major_levels (no future
peek). Round-50 levels and multi-TF extremes from D1 are included.

Reads:  cache/2026-01-m5.json .. cache/2026-05-m5.json
Writes: data/backtests/phase4-results.json
        data/backtests/phase4-report.md
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

# Pattern thresholds (deliberately moderate so 3-bar trios fire often
# enough to study; tighter than the all-OFF defaults of the indicator
# but looser than full eye-model)
MIN_BODY_PCT = 0.55
MAX_WICK_PCT = 0.30
MIN_BODY_POINTS = 300  # 3.0 USD per candle on XAUUSD
USE_REVERSAL_CTX = True

# S/R parameters
SR_BAND_ATR_MULT = 0.6        # how close to a level counts as "at level"
SR_BOUNCE_MIN_PIERCE = 0.10   # bar1 must pierce >= this fraction of ATR below support
SR_LOOKBACK = 500
SR_CLUSTER_ATR_MULT = 0.5
SR_MIN_TOUCHES = 3
SR_PIVOT_LEFT = 10
SR_PIVOT_RIGHT = 10
SR_ROUND_STEP = 50.0


SrMode = Literal["none", "at_level", "bouncing"]
EntryMode = Literal["next_open", "pullback_50"]
SlMode = Literal["pattern_low", "level_break"]
TpMode = Literal["pattern_extension", "next_level", "fixed_2r"]


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
# Pattern detection (newest-first index convention)
# ------------------------------------------------------------------
# The trio occupies indices [i-2, i-1, i] in chronological order.
# i is the newest closed bar.
# bar1 = i-2 (oldest), bar2 = i-1, bar3 = i (newest).
# reversal-context bar = i-3.


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
    """Return 'BUY' (3WS) or 'SELL' (3BC) if bar i completes a pattern."""
    if i < 3:
        return None
    b1, b2, b3 = candles[i - 2], candles[i - 1], candles[i]

    # Three White Soldiers
    if is_bull_candle(b1) and is_bull_candle(b2) and is_bull_candle(b3):
        if not (b3["close"] > b2["close"] > b1["close"]):
            pass  # fall through
        else:
            if USE_REVERSAL_CTX:
                prev = candles[i - 3]
                if not (prev["close"] < prev["open"]):
                    return None
            return "BUY"

    # Three Black Crows
    if is_bear_candle(b1) and is_bear_candle(b2) and is_bear_candle(b3):
        if not (b3["close"] < b2["close"] < b1["close"]):
            return None
        if USE_REVERSAL_CTX:
            prev = candles[i - 3]
            if not (prev["close"] > prev["open"]):
                return None
        return "SELL"

    return None


# ------------------------------------------------------------------
# S/R level scan at signal time
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


# ------------------------------------------------------------------
# S/R confluence checks
# ------------------------------------------------------------------


def _bar1_extreme(side: str, candles: list[dict], i: int) -> float:
    """For BUY the relevant outer extreme is bar1's low; for SELL bar1's high."""
    return candles[i - 2]["low"] if side == "BUY" else candles[i - 2]["high"]


def find_anchor_level(
    side: str,
    candles: list[dict],
    i: int,
    levels: list[float],
    atr: float,
) -> float | None:
    """Return the level that anchors this pattern, or None."""
    if not levels or atr <= 0:
        return None
    band = SR_BAND_ATR_MULT * atr
    extreme = _bar1_extreme(side, candles, i)
    candidates = []
    for L in levels:
        if abs(L - extreme) <= band:
            candidates.append(L)
    if not candidates:
        return None
    if side == "BUY":
        # support = level near or below bar1's low; pick the highest
        # such level (the most relevant immediate support)
        candidates_below = [L for L in candidates if L <= extreme + band]
        if not candidates_below:
            return None
        return max(candidates_below)
    else:
        candidates_above = [L for L in candidates if L >= extreme - band]
        if not candidates_above:
            return None
        return min(candidates_above)


def is_bouncing(
    side: str, candles: list[dict], i: int, anchor: float, atr: float
) -> bool:
    """True if bar1 pierced through the anchor and bar3 closed back beyond it."""
    if anchor is None or atr <= 0:
        return False
    pierce_min = SR_BOUNCE_MIN_PIERCE * atr
    bar1 = candles[i - 2]
    bar3 = candles[i]
    if side == "BUY":
        # support; bar1 low pierced below anchor by at least pierce_min
        # bar3 close back above anchor
        return bar1["low"] <= anchor - pierce_min and bar3["close"] > anchor
    else:
        return bar1["high"] >= anchor + pierce_min and bar3["close"] < anchor


def find_next_level(
    side: str, current: float, levels: list[float], min_distance: float
) -> float | None:
    """For BUY: lowest level above current+min_distance.
    For SELL: highest level below current-min_distance."""
    if not levels or min_distance < 0:
        return None
    if side == "BUY":
        above = [L for L in levels if L >= current + min_distance]
        return min(above) if above else None
    else:
        below = [L for L in levels if L <= current - min_distance]
        return max(below) if below else None


# ------------------------------------------------------------------
# Trade simulation
# ------------------------------------------------------------------


def simulate(
    side: str,
    i: int,
    candles: list[dict],
    levels: list[float],
    atr: float,
    anchor: float | None,
    entry_mode: EntryMode,
    sl_mode: SlMode,
    tp_mode: TpMode,
) -> dict:
    bar1 = candles[i - 2]
    bar3 = candles[i]

    pattern_low = bar1["low"]
    pattern_high = bar1["high"] if side == "SELL" else max(b["high"] for b in candles[i - 2 : i + 1])
    if side == "BUY":
        pattern_high = max(b["high"] for b in candles[i - 2 : i + 1])
        pattern_low = min(b["low"] for b in candles[i - 2 : i + 1])
    else:
        pattern_high = max(b["high"] for b in candles[i - 2 : i + 1])
        pattern_low = min(b["low"] for b in candles[i - 2 : i + 1])
    pattern_range = pattern_high - pattern_low

    # ----- entry -----
    if i + 1 >= len(candles):
        return {"outcome": "no-next-bar", "filled": False}
    entry_price = None
    entry_idx = None
    if entry_mode == "next_open":
        entry_price = candles[i + 1]["open"]
        entry_idx = i + 1
    else:  # pullback_50
        # 50% retrace of bar3 = midpoint of bar3 body
        if side == "BUY":
            limit = (bar3["open"] + bar3["close"]) / 2
        else:
            limit = (bar3["open"] + bar3["close"]) / 2
        for k in range(PULLBACK_FILL_BARS):
            idx = i + 1 + k
            if idx >= len(candles):
                break
            bar = candles[idx]
            if side == "BUY" and bar["low"] <= limit:
                entry_price = limit
                entry_idx = idx
                break
            if side == "SELL" and bar["high"] >= limit:
                entry_price = limit
                entry_idx = idx
                break
        if entry_price is None:
            return {"outcome": "not-filled", "filled": False}

    # ----- SL -----
    if sl_mode == "pattern_low":
        if side == "BUY":
            sl = pattern_low - 0.10 * pattern_range
        else:
            sl = pattern_high + 0.10 * pattern_range
    else:  # level_break
        if anchor is None:
            return {"outcome": "no-anchor", "filled": False}
        cushion = 0.20 * atr  # small cushion below the anchor
        if side == "BUY":
            sl = anchor - cushion
        else:
            sl = anchor + cushion

    # ----- TP -----
    risk = abs(entry_price - sl)
    if risk <= 0:
        return {"outcome": "zero-risk", "filled": False}

    if tp_mode == "pattern_extension":
        if side == "BUY":
            tp = pattern_high + 0.27 * pattern_range
        else:
            tp = pattern_low - 0.27 * pattern_range
    elif tp_mode == "fixed_2r":
        if side == "BUY":
            tp = entry_price + 2 * risk
        else:
            tp = entry_price - 2 * risk
    else:  # next_level
        next_l = find_next_level(side, entry_price, levels, atr * 0.30)
        if next_l is None:
            return {"outcome": "no-tp-level", "filled": False}
        tp = next_l

    # Sanity: TP must be on the right side of entry by at least cushion
    if side == "BUY" and tp <= entry_price:
        return {"outcome": "tp-too-close", "filled": False}
    if side == "SELL" and tp >= entry_price:
        return {"outcome": "tp-too-close", "filled": False}

    # ----- forward simulation -----
    outcome = "timeout"
    exit_price: float | None = None
    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        if side == "BUY":
            sl_hit = bar["low"] <= sl
            tp_hit = bar["high"] >= tp
        else:
            sl_hit = bar["high"] >= sl
            tp_hit = bar["low"] <= tp
        if sl_hit:
            outcome = "SL"
            exit_price = sl
            break
        if tp_hit:
            outcome = "TP"
            exit_price = tp
            break

    rr = abs(tp - entry_price) / risk if risk > 0 else 0

    return {
        "outcome": outcome,
        "filled": True,
        "entry_price": round(entry_price, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "exit_price": round(exit_price, 2) if exit_price else None,
        "rr_target": round(rr, 3),
        "anchor": round(anchor, 2) if anchor is not None else None,
    }


# ------------------------------------------------------------------
# Variant runner
# ------------------------------------------------------------------


VARIANTS: list[dict[str, Any]] = [
    {
        "name": "pure_3p_market",
        "sr_mode": "none",
        "entry": "next_open",
        "sl": "pattern_low",
        "tp": "pattern_extension",
    },
    {
        "name": "pure_3p_pullback",
        "sr_mode": "none",
        "entry": "pullback_50",
        "sl": "pattern_low",
        "tp": "pattern_extension",
    },
    {
        "name": "sr_at_level",
        "sr_mode": "at_level",
        "entry": "next_open",
        "sl": "level_break",
        "tp": "next_level",
    },
    {
        "name": "sr_at_level_2r",
        "sr_mode": "at_level",
        "entry": "next_open",
        "sl": "level_break",
        "tp": "fixed_2r",
    },
    {
        "name": "sr_bounce",
        "sr_mode": "bouncing",
        "entry": "next_open",
        "sl": "level_break",
        "tp": "next_level",
    },
    {
        "name": "sr_bounce_2r",
        "sr_mode": "bouncing",
        "entry": "next_open",
        "sl": "level_break",
        "tp": "fixed_2r",
    },
]


def run_variant(candles: list[dict], variant: dict[str, Any]) -> dict:
    sr_mode: SrMode = variant["sr_mode"]
    entry_mode: EntryMode = variant["entry"]
    sl_mode: SlMode = variant["sl"]
    tp_mode: TpMode = variant["tp"]

    trades: list[dict] = []
    skipped_no_anchor = 0
    skipped_no_bounce = 0
    skipped_other = 0

    for i in range(3, len(candles) - 1):
        side = detect_pattern(i, candles)
        if side is None:
            continue
        atr = wilder_atr_at(i, candles)
        if atr is None or atr <= 0:
            skipped_other += 1
            continue

        levels = get_levels_at(candles, i, atr) if sr_mode != "none" or tp_mode == "next_level" else []

        anchor: float | None = None
        if sr_mode != "none":
            anchor = find_anchor_level(side, candles, i, levels, atr)
            if anchor is None:
                skipped_no_anchor += 1
                continue
            if sr_mode == "bouncing" and not is_bouncing(side, candles, i, anchor, atr):
                skipped_no_bounce += 1
                continue

        sim = simulate(
            side=side,
            i=i,
            candles=candles,
            levels=levels,
            atr=atr,
            anchor=anchor,
            entry_mode=entry_mode,
            sl_mode=sl_mode,
            tp_mode=tp_mode,
        )
        if sim.get("filled"):
            trades.append(sim)
        elif sim.get("outcome") in ("not-filled", "no-anchor", "no-tp-level", "tp-too-close", "zero-risk"):
            skipped_other += 1

    n_filled = len(trades)
    n_tp = sum(1 for t in trades if t["outcome"] == "TP")
    n_sl = sum(1 for t in trades if t["outcome"] == "SL")

    rr_wins: list[float] = []
    for t in trades:
        if t["outcome"] != "TP":
            continue
        rr_wins.append(t["rr_target"])
    sum_pos = sum(rr_wins)
    gross_loss = float(n_sl)
    net = sum_pos - gross_loss
    pf = sum_pos / gross_loss if gross_loss else (math.inf if n_tp else 0)
    wr = n_tp / n_filled if n_filled else 0
    mean_rr = sum(rr_wins) / len(rr_wins) if rr_wins else 0

    return {
        "n_filled": n_filled,
        "n_tp": n_tp,
        "n_sl": n_sl,
        "skipped_no_anchor": skipped_no_anchor,
        "skipped_no_bounce": skipped_no_bounce,
        "skipped_other": skipped_other,
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

    # Aggregate per variant
    aggregates: dict[str, dict] = {}
    for variant in VARIANTS:
        keys = [k for k in all_results if k.endswith(f"| {variant['name']}")]
        agg = {
            "n_filled": sum(all_results[k]["n_filled"] for k in keys),
            "n_tp": sum(all_results[k]["n_tp"] for k in keys),
            "n_sl": sum(all_results[k]["n_sl"] for k in keys),
            "skipped_no_anchor": sum(all_results[k]["skipped_no_anchor"] for k in keys),
            "skipped_no_bounce": sum(all_results[k]["skipped_no_bounce"] for k in keys),
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
        # Mean RR per win, weighted across months by win count
        total_wins = agg["n_tp"]
        if total_wins > 0:
            agg["mean_rr_target"] = sum(
                all_results[k]["mean_rr_target"] * all_results[k]["n_tp"]
                for k in keys
            ) / total_wins
        else:
            agg["mean_rr_target"] = 0.0
        aggregates[variant["name"]] = agg

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase4-results.json").write_text(
        json.dumps({"per_month": all_results, "aggregates": aggregates}, indent=2, default=str),
        encoding="utf-8",
    )

    # Print summary
    print()
    print("=== Aggregate (5 months) ===")
    print(f"{'variant':<22}  {'n':>4}  {'WR':>6}  {'meanRR':>7}  {'PF':>6}  {'net':>7}  {'per-trade':>10}  {'no-anchor':>10}  {'no-bounce':>10}")
    for v in VARIANTS:
        a = aggregates[v["name"]]
        print(
            f"{v['name']:<22}  {a['n_filled']:>4}  {a['wr'] * 100:>5.1f}%  "
            f"{a['mean_rr_target']:>7.3f}  {fmt_pf(a['pf']):>6}  "
            f"{a['net_R']:>+7.2f}  {a['per_trade_R']:>+8.3f} R  "
            f"{a['skipped_no_anchor']:>10}  {a['skipped_no_bounce']:>10}"
        )

    # Build markdown report
    md: list[str] = []
    md.append("# Phase 4 backtest -- ThreeSoldiersCrows + S/R combined\n\n")
    md.append("Tests whether combining the classical 3WS/3BC pattern with S/R-zone\n")
    md.append("context produces a tradeable strategy on M5 XAUUSD.\n\n")

    md.append("## Pattern config\n\n")
    md.append("```\n")
    md.append(f"Min body% per candle:        {MIN_BODY_PCT}\n")
    md.append(f"Max same-side wick%:          {MAX_WICK_PCT}\n")
    md.append(f"Min body in points:          {MIN_BODY_POINTS}  (= {MIN_BODY_POINTS * POINT:.1f} USD on XAUUSD)\n")
    md.append(f"Reversal context required:    {USE_REVERSAL_CTX}  (BEAR-BULL-BULL-BULL or mirror)\n")
    md.append(f"S/R band:                    {SR_BAND_ATR_MULT} * ATR(14)\n")
    md.append(f"Bounce min pierce:           {SR_BOUNCE_MIN_PIERCE} * ATR(14)\n")
    md.append(f"S/R cluster:                  {SR_CLUSTER_ATR_MULT} * ATR, min {SR_MIN_TOUCHES} touches\n")
    md.append("```\n\n")

    md.append("## Six variants tested\n\n")
    md.append("| Variant | S/R | Entry | SL | TP |\n")
    md.append("|---|---|---|---|---|\n")
    for v in VARIANTS:
        md.append(f"| `{v['name']}` | {v['sr_mode']} | {v['entry']} | {v['sl']} | {v['tp']} |\n")
    md.append("\n")

    md.append("## Pooled aggregate (Jan-May 2026)\n\n")
    md.append("```\n")
    md.append(f"{'variant':<22}  {'n':>4}  {'WR':>6}  {'meanRR':>7}  {'PF':>6}  {'net':>7}  {'per-trade':>10}\n")
    md.append("-" * 90 + "\n")
    for v in VARIANTS:
        a = aggregates[v["name"]]
        md.append(
            f"{v['name']:<22}  {a['n_filled']:>4}  {a['wr'] * 100:>5.1f}%  "
            f"{a['mean_rr_target']:>7.3f}  {fmt_pf(a['pf']):>6}  "
            f"{a['net_R']:>7.2f}  {a['per_trade_R']:>+8.3f} R\n"
        )
    md.append("```\n\n")

    md.append("## Per-month detail\n\n")
    md.append("```\n")
    md.append(f"{'config':<36}  {'n':>4}  {'WR':>6}  {'meanRR':>7}  {'PF':>6}  {'net':>7}\n")
    md.append("-" * 80 + "\n")
    for slug in months:
        for v in VARIANTS:
            r = all_results[f"{slug} | {v['name']}"]
            md.append(
                f"{slug} | {v['name']:<22}  {r['n_filled']:>4}  "
                f"{r['wr'] * 100:>5.1f}%  {r['mean_rr_target']:>7.3f}  "
                f"{fmt_pf(r['pf']):>6}  {r['net_R']:>7.2f}\n"
            )
        md.append("\n")
    md.append("```\n\n")

    (OUT / "phase4-report.md").write_text("".join(md), encoding="utf-8")
    print()
    print(f"wrote {OUT / 'phase4-report.md'}")


if __name__ == "__main__":
    main()
