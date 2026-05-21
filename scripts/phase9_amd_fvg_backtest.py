"""Phase 9 backtest -- AMD (LSD) + FVG only.

User asked to revisit the AMD model (Phase 6's LSD signal: London-sweep +
NY-displacement) combined with FVG (Fair Value Gap) alone, no other
confluences.

Phase 6 finding: LSD raw on 12 months was break-even
  169 trades, 63.3% WR, PF 1.01, +0.66R net.

Question: does FVG specifically lift it above PF > 1.40?

FVG definitions (3-candle imbalance):
  Bullish FVG @ idx: candles[idx].low > candles[idx-2].high
                     middle bar (idx-1) is the displacement
                     gap = (candles[idx-2].high, candles[idx].low)
  Bearish FVG @ idx: candles[idx].high < candles[idx-2].low

Five variants tested over 29 months (Jan 2024 - May 2026):
  V1  LSD raw                              baseline on 29 months
  V2  LSD + FVGC                           displacement bar creates FVG
  V3  LSD + FVGE                           entry inside unfilled FVG (last 50 bars)
  V4  LSD + FVGC + FVGE                    both confluences
  V5  LSD + FVGC + 1.5R fixed TP           FVG + ICT-style fixed exit

Entry mode locked at pullback_236 to match every other phase. SL/TP
defaults are the fib-based ones used everywhere; V5 substitutes a fixed
1.5R TP based on the SL distance.

Pre-committed decision rules:
  1. n_filled >= 50          (>=2/month average)
  2. PF > 1.40
  3. losing months <= 7/29   (~24%)
  4. mean RR per win >= 0.5

Note on FVGC look-ahead: a FVG is confirmed when bar idx+1 closes (it
needs the next bar to define the top/bottom of the gap). The backtest
inherits Phase 6's pullback fill window starting at idx+1, which yields
a 1-bar look-ahead vs strict live behavior. In live deployment the EA
would wait for the FVG-confirming bar to close, then arm the pullback
limit -- a 5-min delay. Since pullback fills typically take 30-60 min,
this is a small effect; we accept it as a known-small bias and document
it.
"""

from __future__ import annotations

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

# AMD spec (same as Phase 6)
ASIA_HOUR_END = 7
LONDON_HOUR_START = 7
LONDON_HOUR_END = 12
NY_HOUR_START = 12
NY_HOUR_END = 22

DISPLACEMENT_MIN_BODY_PCT = 0.60
DISPLACEMENT_MIN_RANGE_ATR = 1.0

# FVG spec
FVGE_LOOKBACK_BARS = 50    # how far back to look for unfilled FVGs in V3/V4


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass
class Signal:
    month: str
    idx: int
    time_utc: str
    side: str
    candle_low: float
    candle_high: float
    candle_range: float
    atr: float
    extras: dict = field(default_factory=dict)


@dataclass
class TradeResult:
    outcome: str
    filled: bool
    entry_price: float | None
    sl: float | None
    tp: float | None
    rr_win: float | None


# --------------------------------------------------------------------------
# Time / market helpers
# --------------------------------------------------------------------------


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def compute_atr14(candles: list[dict]) -> list[float]:
    n = len(candles)
    atr = [0.0] * n
    if n < 16:
        return atr
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


def group_by_day(candles: list[dict]) -> dict[str, list[int]]:
    by_day: dict[str, list[int]] = {}
    for i, c in enumerate(candles):
        d = utc(c["time"]).date().isoformat()
        by_day.setdefault(d, []).append(i)
    return by_day


# --------------------------------------------------------------------------
# LSD detection (copy from Phase 6 to keep this script self-contained)
# --------------------------------------------------------------------------


def detect_asian_range(candles: list[dict], day_indices: list[int]) -> tuple[float, float] | None:
    asia_idxs = [i for i in day_indices if utc(candles[i]["time"]).hour < ASIA_HOUR_END]
    if not asia_idxs:
        return None
    lo = min(candles[i]["low"] for i in asia_idxs)
    hi = max(candles[i]["high"] for i in asia_idxs)
    return lo, hi


def detect_london_sweep(
    candles: list[dict],
    day_indices: list[int],
    asia_low: float,
    asia_high: float,
) -> tuple[str, int] | None:
    london_idxs = [
        i for i in day_indices
        if LONDON_HOUR_START <= utc(candles[i]["time"]).hour < LONDON_HOUR_END
    ]
    for i in london_idxs:
        c = candles[i]
        if c["high"] > asia_high and c["close"] < asia_high and c["close"] > asia_low:
            return ("BSL", i)
        if c["low"] < asia_low and c["close"] > asia_low and c["close"] < asia_high:
            return ("SSL", i)
    return None


def detect_ny_displacement(
    candles: list[dict],
    day_indices: list[int],
    sweep_side: str,
    sweep_idx: int,
    atr: list[float],
    min_body_pct: float = DISPLACEMENT_MIN_BODY_PCT,
) -> int | None:
    expected = "SELL" if sweep_side == "BSL" else "BUY"
    ny_idxs = [
        i for i in day_indices
        if i > sweep_idx and NY_HOUR_START <= utc(candles[i]["time"]).hour < NY_HOUR_END
    ]
    for i in ny_idxs:
        c = candles[i]
        rng = c["high"] - c["low"]
        if rng <= 0:
            continue
        body = abs(c["close"] - c["open"])
        body_pct = body / rng
        if body_pct < min_body_pct:
            continue
        if atr[i] <= 0 or rng < DISPLACEMENT_MIN_RANGE_ATR * atr[i]:
            continue
        side = "BUY" if c["close"] > c["open"] else "SELL" if c["close"] < c["open"] else ""
        if side != expected:
            continue
        return i
    return None


def make_signal(month: str, candles: list[dict], idx: int, side: str, atr: list[float]) -> Signal:
    c = candles[idx]
    return Signal(
        month=month,
        idx=idx,
        time_utc=utc(c["time"]).isoformat(),
        side=side,
        candle_low=c["low"],
        candle_high=c["high"],
        candle_range=c["high"] - c["low"],
        atr=atr[idx] if idx < len(atr) else 0.0,
    )


def generate_lsd_signals(
    month: str,
    candles: list[dict],
    atr: list[float],
    min_body_pct: float = DISPLACEMENT_MIN_BODY_PCT,
) -> list[Signal]:
    signals: list[Signal] = []
    by_day = group_by_day(candles)
    for date in sorted(by_day.keys()):
        day_indices = by_day[date]
        ar = detect_asian_range(candles, day_indices)
        if not ar:
            continue
        asia_low, asia_high = ar
        sweep = detect_london_sweep(candles, day_indices, asia_low, asia_high)
        if not sweep:
            continue
        sweep_side, sweep_idx = sweep
        disp_idx = detect_ny_displacement(
            candles, day_indices, sweep_side, sweep_idx, atr, min_body_pct
        )
        if disp_idx is None:
            continue
        side = "SELL" if sweep_side == "BSL" else "BUY"
        signals.append(make_signal(month, candles, disp_idx, side, atr))
    return signals


# --------------------------------------------------------------------------
# FVG
# --------------------------------------------------------------------------


def detect_fvg(candles: list[dict], idx: int) -> dict | None:
    """3-candle FVG confirmed when bar idx closes.

    Returns:
      {"side": "bullish"|"bearish",
       "low": float,  "high": float,           # gap edges
       "displacement_idx": int}                # middle bar (the displacement)
    or None.
    """
    if idx < 2:
        return None
    a = candles[idx - 2]
    c = candles[idx]
    if c["low"] > a["high"]:
        return {
            "side": "bullish",
            "low": a["high"],
            "high": c["low"],
            "displacement_idx": idx - 1,
            "formed_at_idx": idx,
        }
    if c["high"] < a["low"]:
        return {
            "side": "bearish",
            "low": c["high"],
            "high": a["low"],
            "displacement_idx": idx - 1,
            "formed_at_idx": idx,
        }
    return None


def confl_fvgc(candles: list[dict], sig: Signal) -> bool:
    """Did the displacement bar at sig.idx create a fresh FVG in trade direction?

    FVG is "created by" the bar at sig.idx if it's the middle of an FVG
    confirmed at sig.idx + 1. Direction must match: bullish FVG for BUY,
    bearish for SELL.
    """
    if sig.idx + 1 >= len(candles):
        return False
    fvg = detect_fvg(candles, sig.idx + 1)
    if fvg is None:
        return False
    if fvg["displacement_idx"] != sig.idx:
        return False
    expected = "bullish" if sig.side == "BUY" else "bearish"
    return fvg["side"] == expected


def confl_fvge(candles: list[dict], sig: Signal, lookback: int = FVGE_LOOKBACK_BARS) -> bool:
    """Does the pullback_236 entry price fall inside an unfilled FVG in trade direction?

    Considers FVGs formed in the lookback window before sig.idx (exclusive).
    "Unfilled" means price has not crossed the gap fully between FVG creation
    and sig.idx.
    """
    if sig.candle_range <= 0:
        return False
    if sig.side == "BUY":
        entry = sig.candle_high - 0.236 * sig.candle_range
        target_side = "bullish"
    else:
        entry = sig.candle_low + 0.236 * sig.candle_range
        target_side = "bearish"

    start = max(2, sig.idx - lookback)
    for i in range(start, sig.idx):
        fvg = detect_fvg(candles, i)
        if fvg is None or fvg["side"] != target_side:
            continue
        # Filled-check: did price cross fully between i and sig.idx?
        filled = False
        for j in range(i + 1, sig.idx):
            bar = candles[j]
            if target_side == "bullish":
                if bar["low"] <= fvg["low"]:
                    filled = True
                    break
            else:
                if bar["high"] >= fvg["high"]:
                    filled = True
                    break
        if filled:
            continue
        # In-zone check: entry between fvg.low and fvg.high
        if fvg["low"] <= entry <= fvg["high"]:
            return True
    return False


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


def simulate(
    candles: list[dict],
    sig: Signal,
    tp_mode: str = "fib_127",  # "fib_127" or "fixed_1.5R"
    entry_start_offset: int = 1,  # 1 = next bar; 2 = strict no-look-ahead for FVGC variants
) -> TradeResult:
    L = sig.candle_low
    H = sig.candle_high
    rng = sig.candle_range

    if sig.side == "BUY":
        sl = L - 0.10 * rng
        tp_fib = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp_fib = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    if sig.idx + entry_start_offset >= len(candles):
        return TradeResult("no-next-bar", False, None, sl, None, None)

    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        idx = sig.idx + entry_start_offset + k
        if idx >= len(candles):
            break
        bar = candles[idx]
        if sig.side == "BUY" and bar["low"] <= pullback_limit:
            entry_price = pullback_limit
            entry_idx = idx
            break
        if sig.side == "SELL" and bar["high"] >= pullback_limit:
            entry_price = pullback_limit
            entry_idx = idx
            break

    if entry_price is None or entry_idx is None:
        return TradeResult("not-filled", False, None, sl, tp_fib, None)

    risk = abs(entry_price - sl)
    if tp_mode == "fixed_1.5R":
        if sig.side == "BUY":
            tp = entry_price + 1.5 * risk
        else:
            tp = entry_price - 1.5 * risk
    else:
        tp = tp_fib

    outcome = "timeout"
    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bh, bl = bar["high"], bar["low"]
        if sig.side == "BUY":
            sl_hit = bl <= sl
            tp_hit = bh >= tp
        else:
            sl_hit = bh >= sl
            tp_hit = bl <= tp
        if sl_hit:
            outcome = "SL"
            break
        if tp_hit:
            outcome = "TP"
            break

    rr_win = None
    if outcome == "TP" and risk > 0:
        rr_win = abs(tp - entry_price) / risk

    return TradeResult(outcome, True, entry_price, sl, tp, rr_win)


# --------------------------------------------------------------------------
# Variants
# --------------------------------------------------------------------------


VARIANTS: list[dict[str, Any]] = [
    {"id": "V1", "label": "LSD raw",                 "filters": [],                "tp_mode": "fib_127",     "entry_offset": 1},
    {"id": "V2", "label": "LSD + FVGC",              "filters": ["FVGC"],          "tp_mode": "fib_127",     "entry_offset": 1},
    {"id": "V3", "label": "LSD + FVGE",              "filters": ["FVGE"],          "tp_mode": "fib_127",     "entry_offset": 1},
    {"id": "V4", "label": "LSD + FVGC + FVGE",       "filters": ["FVGC", "FVGE"],  "tp_mode": "fib_127",     "entry_offset": 1},
    {"id": "V5", "label": "LSD + FVGC + 1.5R TP",    "filters": ["FVGC"],          "tp_mode": "fixed_1.5R",  "entry_offset": 1},
    {"id": "V6", "label": "LSD + FVGC strict (idx+2)", "filters": ["FVGC"],        "tp_mode": "fib_127",     "entry_offset": 2},
]


def passes_filter(candles: list[dict], sig: Signal, filters: list[str]) -> bool:
    if "FVGC" in filters and not confl_fvgc(candles, sig):
        return False
    if "FVGE" in filters and not confl_fvge(candles, sig):
        return False
    return True


# --------------------------------------------------------------------------
# Per-variant runner
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


def run_variant(variant: dict, months_data: dict[str, dict]) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    entry_offset = variant.get("entry_offset", 1)
    for month, data in months_data.items():
        candles = data["candles"]
        lsd = data["lsd"]
        m = MonthMetrics(month=month)
        for sig in lsd:
            if not passes_filter(candles, sig, variant["filters"]):
                continue
            m.n_signals += 1
            res = simulate(candles, sig, tp_mode=variant["tp_mode"], entry_start_offset=entry_offset)
            if not res.filled:
                m.n_unfilled += 1
                continue
            m.n_filled += 1
            if res.outcome == "TP":
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


def apply_rules(agg: dict) -> tuple[bool, list[str]]:
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
    return ok, reasons


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def fmt_pf(x: float) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.2f}"


def write_report(
    results: dict[str, dict],
    per_month_results: dict[str, dict[str, MonthMetrics]],
    months: list[str],
    out_md: Path,
) -> None:
    md: list[str] = []
    md.append("# Phase 9 backtest -- AMD (LSD) + FVG only\n\n")
    md.append(f"Window: {months[0]} to {months[-1]} ({len(months)} months M5 XAUUSD)\n\n")
    md.append("Five variants, pullback_236 entry, V5 uses fixed 1.5R TP.\n\n")
    md.append("Pre-committed rules: n>=50, PF>1.40, losing_months<=7/29, mean_RR>=0.5\n\n")

    md.append("## Pooled aggregate\n\n```\n")
    md.append(
        f"{'V':<4}  {'config':<28}  {'sigs':>5}  {'fill':>5}  "
        f"{'TP':>4}  {'SL':>4}  {'WR':>5}  {'meanRR':>7}  "
        f"{'netR':>7}  {'PF':>6}  {'losM':>6}  {'verdict':<8}\n"
    )
    md.append("-" * 110 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg)
        md.append(
            f"{v['id']:<4}  {v['label']:<28}  "
            f"{agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp']:>4}  {agg['n_sl']:>4}  "
            f"{agg['wr'] * 100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
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
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Loading {len(months)} months: {months[0]} -> {months[-1]}")

    months_data: dict[str, dict] = {}
    for slug in months:
        path = CACHE / f"{slug}-m5.json"
        candles = json.loads(path.read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        atr = compute_atr14(candles)
        lsd = generate_lsd_signals(slug, candles, atr)
        months_data[slug] = {"candles": candles, "atr": atr, "lsd": lsd}
        print(f"  {slug}: {len(candles)} bars, LSD signals={len(lsd)}")

    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    per_month_results: dict[str, dict[str, MonthMetrics]] = {}

    print("\nRunning variants...")
    for v in VARIANTS:
        per_month = run_variant(v, months_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, _ = apply_rules(agg)
        print(
            f"  {v['id']:<3} {v['label']:<28} "
            f"sigs={agg['n_signals']:>4}  n={agg['n_filled']:>4}  "
            f"WR={agg['wr'] * 100:>4.1f}%  PF={fmt_pf(agg['pf']):>5}  "
            f"netR={agg['net_R']:>+6.2f}  losM={agg['losing_months']}/{agg['trading_months']}  "
            f"{'PASS' if ok else 'REJECT'}"
        )

    json_path = OUT / "phase9-results.json"
    serializable = {
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved raw results to {json_path}")

    md_path = OUT / "phase9-report.md"
    write_report(results, per_month_results, months, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
