"""Phase 3 backtest: optimized + pullback_236 with vs without S/R confluence.

For each month (Jan-May 2026), runs the optimized 7-rule filter with
pullback_236 entry under THREE configurations:

  1. baseline      -- no S/R filter (the v0.5.0 deployable strategy)
  2. sr_band       -- signal must be within InpSrBandAtrMult * ATR
                       of a MAJOR S/R level (bidirectional)
  3. sr_confluence -- BUY signals must be near a SUPPORT level;
                       SELL signals must be near a RESISTANCE level
                       (directional confluence)

S/R levels are computed PER SIGNAL using the same algorithm as
mt5_mvp.strategies.support_resistance.find_major_levels with the
candle history available up to that signal's timestamp -- so we don't
peek at future bars.

Reads:  cache/2026-01-m5.json .. cache/2026-05-m5.json
Writes: data/backtests/phase3-results.json
        data/backtests/phase3-report.md
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

# S/R confluence parameters
SR_BAND_ATR_MULT = 0.5     # signal must be within 0.5 * ATR of a level
SR_LOOKBACK = 500          # bars used for pivot scan at each signal
SR_CLUSTER_ATR_MULT = 0.5
SR_MIN_TOUCHES = 3
SR_PIVOT_LEFT = 10
SR_PIVOT_RIGHT = 10
SR_ROUND_STEP = 50.0

EntryMode = Literal["next_open", "pullback_236"]


# --- Feature helpers (shared with prior backtests) -----------------------


def session_label(h: int) -> str:
    if h >= 23 or h < 8:
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


def passes_optimized_no_round(f: dict) -> bool:
    """The deployable filter -- 7 rules without dist_to_round_50."""
    return (
        f["body_pct"] >= 0.86
        and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05
        and f["body_points"] >= 1000
        and f["range"] >= 11.0
        and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


# --- ATR helper (Wilder) -------------------------------------------------


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


# --- S/R detection (single-tier scan up to idx) --------------------------


def detect_pivots(
    candles: list[dict],
    end_idx: int,
    pivot_left: int,
    pivot_right: int,
    lookback: int,
) -> list[tuple[float, str]]:
    """Detect swing highs/lows on candles[end_idx - lookback .. end_idx - pivot_right - 1].

    Returns list of (price, "H" or "L") tuples.
    """
    start_idx = max(pivot_left, end_idx - lookback)
    last_safe = end_idx - pivot_right
    pivots: list[tuple[float, str]] = []
    if last_safe <= start_idx:
        return pivots

    for i in range(start_idx, last_safe):
        h = candles[i]["high"]
        lo = candles[i]["low"]
        is_high = True
        is_low = True
        for k in range(1, pivot_left + 1):
            if candles[i - k]["high"] >= h:
                is_high = False
            if candles[i - k]["low"] <= lo:
                is_low = False
            if not is_high and not is_low:
                break
        if is_high or is_low:
            for k in range(1, pivot_right + 1):
                if candles[i + k]["high"] >= h:
                    is_high = False
                if candles[i + k]["low"] <= lo:
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
    """Greedy-merge pivots within radius. Return cluster mean prices
    where weight >= min_touches."""
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

    levels: list[float] = []
    for c in clusters:
        if len(c) < min_touches:
            continue
        levels.append(sum(c) / len(c))
    return levels


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


def find_sr_levels_at(
    candles: list[dict],
    signal_idx: int,
    atr: float,
) -> list[float]:
    """Compute the relevant S/R levels visible to a trader at signal_idx."""
    if atr <= 0:
        return []
    pivots = detect_pivots(
        candles,
        end_idx=signal_idx,
        pivot_left=SR_PIVOT_LEFT,
        pivot_right=SR_PIVOT_RIGHT,
        lookback=SR_LOOKBACK,
    )
    radius = SR_CLUSTER_ATR_MULT * atr
    swing_levels = cluster_levels(pivots, radius, SR_MIN_TOUCHES)

    # Round levels: only those near the current price (within ~10 ATRs)
    current_price = candles[signal_idx]["close"]
    round_levs = round_levels_near(current_price, SR_ROUND_STEP, atr * 10.0)

    return swing_levels + round_levs


def signal_near_level(
    side: str,
    candle: dict,
    levels: list[float],
    atr: float,
    band_atr_mult: float = SR_BAND_ATR_MULT,
    directional: bool = False,
) -> bool:
    """True if the signal candle's relevant extreme is within band of a level.

    For BUY: the candle's LOW is the entry-extreme. Trade is "near support"
    when low is within band of a level BELOW the candle's low (or near to it).
    For SELL: candle's HIGH similarly.

    `directional=True` requires the level to be on the correct side
    (support below for BUY, resistance above for SELL). When False,
    any nearby level qualifies.
    """
    if not levels or atr <= 0:
        return False
    band = band_atr_mult * atr
    if side == "BUY":
        ref = candle["low"]
        for L in levels:
            if directional:
                # support: level at or below candle low, within band
                if L <= ref + band and abs(L - ref) <= band:
                    return True
            else:
                if abs(L - ref) <= band:
                    return True
    else:  # SELL
        ref = candle["high"]
        for L in levels:
            if directional:
                # resistance: level at or above candle high, within band
                if L >= ref - band and abs(L - ref) <= band:
                    return True
            else:
                if abs(L - ref) <= band:
                    return True
    return False


# --- Trade simulation (pullback_236) -------------------------------------


def simulate_pullback(signal_idx: int, side: str, candles: list[dict]) -> dict:
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
        if side == "BUY":
            sl_hit = bar["low"] <= sl
            tp2_hit = bar["high"] >= tp2
        else:
            sl_hit = bar["high"] >= sl
            tp2_hit = bar["low"] <= tp2
        if sl_hit:
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


# --- Run one config ------------------------------------------------------


def run_config(
    candles: list[dict],
    sr_mode: str,
) -> dict:
    """sr_mode in {'baseline', 'sr_band', 'sr_confluence'}"""
    trades: list[dict] = []
    skipped_by_sr = 0

    for i in range(len(candles) - 1):
        f = compute_features(i, candles)
        if not f:
            continue
        if not passes_optimized_no_round(f):
            continue

        if sr_mode != "baseline":
            atr = wilder_atr_at(i, candles)
            if atr is None or atr <= 0:
                skipped_by_sr += 1
                continue
            levels = find_sr_levels_at(candles, i, atr)
            directional = sr_mode == "sr_confluence"
            if not signal_near_level(
                f["side"], candles[i], levels, atr,
                band_atr_mult=SR_BAND_ATR_MULT,
                directional=directional,
            ):
                skipped_by_sr += 1
                continue

        sim = simulate_pullback(i, f["side"], candles)
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
    pf = sum_pos / gross_loss if gross_loss else (math.inf if n_tp2 else 0)
    wr = n_tp2 / n_filled if n_filled else 0
    mean_rr = sum(rr_wins) / len(rr_wins) if rr_wins else 0

    return {
        "n_total": n_total,
        "n_filled": n_filled,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "skipped_by_sr": skipped_by_sr,
        "wr": wr,
        "mean_rr": mean_rr,
        "net_R": net,
        "pf": pf,
        "per_trade_R": net / n_filled if n_filled else 0,
        "gross_pos_R": sum_pos,
        "gross_neg_R": gross_loss,
    }


# --- Main ----------------------------------------------------------------


def fmt_pf(x: float) -> str:
    if x == math.inf:
        return "inf"
    return f"{x:.2f}"


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Months: {months}")

    sr_modes = ["baseline", "sr_band", "sr_confluence"]
    all_results: dict[str, dict] = {}

    for slug in months:
        candles = json.loads((CACHE / f"{slug}-m5.json").read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        for mode in sr_modes:
            key = f"{slug} | {mode}"
            print(f"  running {key} ...")
            all_results[key] = run_config(candles, mode)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase3-results.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )

    # Aggregate by mode
    aggregates: dict[str, dict] = {}
    for mode in sr_modes:
        keys = [k for k in all_results if k.endswith(f"| {mode}")]
        tot_filled = sum(all_results[k]["n_filled"] for k in keys)
        tot_tp2 = sum(all_results[k]["n_tp2"] for k in keys)
        tot_sl = sum(all_results[k]["n_sl"] for k in keys)
        tot_skip = sum(all_results[k]["skipped_by_sr"] for k in keys)
        tot_pos = sum(all_results[k]["gross_pos_R"] for k in keys)
        tot_neg = sum(all_results[k]["gross_neg_R"] for k in keys)
        net = tot_pos - tot_neg
        wr = tot_tp2 / tot_filled if tot_filled else 0
        pf = tot_pos / tot_neg if tot_neg else (math.inf if tot_tp2 else 0)
        aggregates[mode] = {
            "n_filled": tot_filled,
            "n_tp2": tot_tp2,
            "n_sl": tot_sl,
            "skipped_by_sr": tot_skip,
            "wr": wr,
            "net_R": net,
            "pf": pf,
            "per_trade_R": net / tot_filled if tot_filled else 0,
        }

    # Build report
    md: list[str] = []
    md.append("# Phase 3 backtest -- S/R confluence study\n\n")
    md.append("Tests whether adding an S/R-confluence filter on top of the\n")
    md.append("v0.5.0 deployable strategy (`optimized_no_round + pullback_236`)\n")
    md.append("meaningfully changes WR/PF.\n\n")

    md.append("## Configurations\n\n")
    md.append("- **baseline**       no S/R filter (the v0.5.0 deployable strategy)\n")
    md.append("- **sr_band**        signal candle's extreme within 0.5 * ATR of ANY major level\n")
    md.append("- **sr_confluence**  directional: BUY near support / SELL near resistance only\n\n")

    md.append("## Per-month results\n\n")
    md.append("```\n")
    md.append(
        f"{'config':<46}  {'sigs':>5}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  "
        f"{'skip':>5}  {'WR':>5}  {'meanRR':>6}  {'net':>7}  {'PF':>6}\n"
    )
    md.append("-" * 110 + "\n")
    for slug in months:
        for mode in sr_modes:
            key = f"{slug} | {mode}"
            r = all_results[key]
            label = f"{slug} | {mode:<14}"
            md.append(
                f"{label:<46}  {r['n_total']:>5}  {r['n_filled']:>5}  "
                f"{r['n_tp2']:>4}  {r['n_sl']:>4}  {r['skipped_by_sr']:>5}  "
                f"{r['wr'] * 100:>4.1f}%  {r['mean_rr']:>6.3f}  "
                f"{r['net_R']:>7.2f}  {fmt_pf(r['pf']):>6}\n"
            )
        md.append("\n")
    md.append("```\n\n")

    md.append("## Pooled aggregate (5 months)\n\n")
    md.append("```\n")
    md.append(
        f"{'config':<46}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  {'skip':>5}  "
        f"{'WR':>5}  {'net':>7}  {'PF':>6}  {'per-trade':>10}\n"
    )
    md.append("-" * 105 + "\n")
    for mode in sr_modes:
        r = aggregates[mode]
        md.append(
            f"ALL | {mode:<14}                              "
            f"{r['n_filled']:>5}  {r['n_tp2']:>4}  {r['n_sl']:>4}  "
            f"{r['skipped_by_sr']:>5}  {r['wr'] * 100:>4.1f}%  "
            f"{r['net_R']:>7.2f}  {fmt_pf(r['pf']):>6}  {r['per_trade_R']:>+8.3f} R\n"
        )
    md.append("```\n\n")

    # Verdict computed below
    base = aggregates["baseline"]
    band = aggregates["sr_band"]
    conf = aggregates["sr_confluence"]
    md.append("## Verdict\n\n")
    md.append(f"**Baseline** (no S/R filter): n={base['n_filled']}, WR {base['wr'] * 100:.1f}%, PF {fmt_pf(base['pf'])}, +{base['per_trade_R']:.3f} R/trade\n\n")
    md.append(f"**sr_band** (any nearby level): n={band['n_filled']}, WR {band['wr'] * 100:.1f}%, PF {fmt_pf(band['pf'])}, +{band['per_trade_R']:.3f} R/trade\n\n")
    md.append(f"**sr_confluence** (directional): n={conf['n_filled']}, WR {conf['wr'] * 100:.1f}%, PF {fmt_pf(conf['pf'])}, +{conf['per_trade_R']:.3f} R/trade\n\n")

    md.append("**Pre-committed decision rule** (set before this run):\n")
    md.append("- If sr_confluence PF >= baseline PF + 0.10  AND  WR change <= -3pp  -> ADOPT\n")
    md.append("- If sr_confluence PF >= baseline PF + 0.05  but volume drops >50%  -> CONDITIONAL ADOPT\n")
    md.append("- If sr_confluence PF < baseline PF + 0.05  OR  WR drops >5pp        -> REJECT\n\n")

    pf_lift = (conf["pf"] if conf["pf"] != math.inf else 99.99) - (base["pf"] if base["pf"] != math.inf else 99.99)
    wr_change_pp = (conf["wr"] - base["wr"]) * 100
    vol_change_pct = ((conf["n_filled"] - base["n_filled"]) / base["n_filled"] * 100) if base["n_filled"] else 0
    md.append(f"sr_confluence PF lift over baseline:  {pf_lift:+.2f}\n")
    md.append(f"sr_confluence WR change over baseline: {wr_change_pp:+.1f} pp\n")
    md.append(f"sr_confluence volume change:          {vol_change_pct:+.1f}%\n\n")

    if pf_lift >= 0.10 and wr_change_pp >= -3.0:
        verdict = "ADOPT"
    elif pf_lift >= 0.05 and vol_change_pct < -50.0:
        verdict = "CONDITIONAL ADOPT"
    else:
        verdict = "REJECT"
    md.append(f"**VERDICT: {verdict}**\n")

    (OUT / "phase3-report.md").write_text("".join(md), encoding="utf-8")
    print()
    print("=== Aggregate ===")
    for mode in sr_modes:
        r = aggregates[mode]
        print(f"  {mode:<16} n={r['n_filled']:>4}  WR={r['wr'] * 100:>4.1f}%  "
              f"PF={fmt_pf(r['pf'])}  net={r['net_R']:+.2f}R  per-trade={r['per_trade_R']:+.3f}R "
              f"skipped_by_sr={r['skipped_by_sr']}")
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
