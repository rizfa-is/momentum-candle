"""Phase 15 backtest -- M15 v0.5.0 optimization with train/test split.

User request: optimize v0.5.0 settings on M15 timeframe and test SL
placements at 78.6 / 90 / 100 percent retracement (tighter than current
110 percent which puts SL beyond the candle).

Grid: 4 entry profiles x 4 SL placements = 16 cells.

Entry profiles (M15)
--------------------
  A  strict  body 0.86, range 18 USD, body 1500pt   (v0.5.0 literal)
  B  firm    body 0.80, range 15 USD, body 1200pt
  C  medium  body 0.75, range 12 USD, body  900pt
  D  relax   body 0.70, range 10 USD, body  700pt

SL placements (BUY candle low L, high H, range R = H - L,
              entry e = H - 0.236 R)
----------------------------------------------------------
  S1  SL = H - 0.786 R   (78.6 fib retracement)        risk = 0.550 R
  S2  SL = H - 0.900 R   (90 percent)                  risk = 0.664 R
  S3  SL = H - 1.000 R  = L                           risk = 0.764 R
  S4  SL = L - 0.10 R   (current, beyond candle low)  risk = 0.864 R

TP fixed at fib 1.27 extension (Phase 13 confirmed optimum).
Entry fixed at fib 0.236 retracement.
Skip London (08-12 UTC) on all variants.
trend_monotonic_prior_7 <= 4 on all variants.
cwick_pct <= 0.10 and fwick_pct <= 0.05 on all variants.

Train / test split (the curve-fit safeguard)
--------------------------------------------
Train: 2024-01 to 2025-05  (17 months)
Test:  2025-06 to 2026-05  (12 months)

A cell PASSES only if it clears the threshold rules on BOTH halves
independently. This catches curve-fits that look great on the full
window because of one fortunate stretch.

Pre-committed thresholds per half
---------------------------------
  n_filled       >= 30
  PF              >  1.40
  mean_RR / win  >= 0.5
  sigs/mo        >= 6
  losing_months  <= 30 percent of trading months in that half
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
M15_BAR_SECONDS = 900

TRAIN_MONTHS = [
    "2024-01","2024-02","2024-03","2024-04","2024-05","2024-06",
    "2024-07","2024-08","2024-09","2024-10","2024-11","2024-12",
    "2025-01","2025-02","2025-03","2025-04","2025-05",
]
TEST_MONTHS = [
    "2025-06","2025-07","2025-08","2025-09","2025-10","2025-11",
    "2025-12","2026-01","2026-02","2026-03","2026-04","2026-05",
]


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def session_label(h: int) -> str:
    if 23 <= h or h < 8: return "Asia"
    if 8 <= h < 12:       return "London"
    if 12 <= h < 22:      return "NY"
    return "Off"


def aggregate_m5_to_m15(m5_candles: list[dict]) -> list[dict]:
    if not m5_candles: return []
    m15: dict[int, dict] = {}
    for c in m5_candles:
        slot = (c["time"] // M15_BAR_SECONDS) * M15_BAR_SECONDS
        if slot not in m15:
            m15[slot] = {
                "time": slot, "open": c["open"], "high": c["high"],
                "low": c["low"], "close": c["close"],
            }
        else:
            b = m15[slot]
            if c["high"] > b["high"]: b["high"] = c["high"]
            if c["low"] < b["low"]:   b["low"] = c["low"]
            b["close"] = c["close"]
    return sorted(m15.values(), key=lambda b: b["time"])


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


# Entry profile presets
ENTRY_PROFILES = {
    "A": {"label": "strict",  "body_pct": 0.86, "body_pts": 1500, "range": 18.0},
    "B": {"label": "firm",    "body_pct": 0.80, "body_pts": 1200, "range": 15.0},
    "C": {"label": "medium",  "body_pct": 0.75, "body_pts":  900, "range": 12.0},
    "D": {"label": "relax",   "body_pct": 0.70, "body_pts":  700, "range": 10.0},
}

# SL placement multipliers (fraction of range below entry for BUY,
# fraction above entry for SELL).
# entry = H - 0.236 R for BUY (so risk = 0.236 R + sl_below_low * R)
# We express SL as "fraction of range from H downwards":
#   S1 = 0.786 R below H  (78.6 fib)         => risk = 0.786 - 0.236 = 0.550 R
#   S2 = 0.900 R below H                     => risk = 0.664 R
#   S3 = 1.000 R below H (= L)               => risk = 0.764 R
#   S4 = 1.100 R below H (L - 0.10 R)        => risk = 0.864 R
SL_PLACEMENTS = {
    "S1": {"label": "78.6 fib",  "sl_frac": 0.786},
    "S2": {"label": "90 pct",    "sl_frac": 0.900},
    "S3": {"label": "100 (=L)",  "sl_frac": 1.000},
    "S4": {"label": "110 cur",   "sl_frac": 1.100},  # current behavior
}


def filter_pass(f: dict, ep: dict) -> bool:
    return (
        f["body_pct"] >= ep["body_pct"]
        and f["cwick_pct"] <= 0.10
        and f["fwick_pct"] <= 0.05
        and f["body_points"] >= ep["body_pts"]
        and f["range"] >= ep["range"]
        and f["session"] != "London"
        and f["trend_monotonic"] <= 4
    )


@dataclass
class TradeResult:
    outcome: str
    filled: bool
    rr_win: float = 0.0


def simulate(candles: list[dict], idx: int, side: str, sl_frac: float) -> TradeResult:
    sig = candles[idx]
    L, H = sig["low"], sig["high"]
    rng = H - L
    if side == "BUY":
        entry = H - 0.236 * rng
        sl    = H - sl_frac * rng
        tp    = H + 0.27 * rng
    else:
        entry = L + 0.236 * rng
        sl    = L + sl_frac * rng
        tp    = L - 0.27 * rng

    if idx + 1 >= len(candles):
        return TradeResult("no-next-bar", False)

    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        i = idx + 1 + k
        if i >= len(candles): break
        bar = candles[i]
        if side == "BUY" and bar["low"] <= entry:
            entry_price = entry; entry_idx = i; break
        if side == "SELL" and bar["high"] >= entry:
            entry_price = entry; entry_idx = i; break
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
            if bar["low"] <= sl:
                outcome = "SL"; break
            if bar["high"] >= tp:
                outcome = "TP"
                rr = abs(tp - entry_price) / risk
                break
        else:
            if bar["high"] >= sl:
                outcome = "SL"; break
            if bar["low"] <= tp:
                outcome = "TP"
                rr = abs(tp - entry_price) / risk
                break
    return TradeResult(outcome, True, rr)


@dataclass
class CellMetrics:
    n_signals: int = 0
    n_filled: int = 0
    n_tp: int = 0
    n_sl: int = 0
    n_to: int = 0
    sum_rr: float = 0.0
    months: dict = None  # month -> {"net": R, "n": filled}

    def __post_init__(self):
        if self.months is None:
            self.months = {}


def run_cell(months_data: dict[str, list[dict]], ep_id: str, sl_id: str) -> CellMetrics:
    ep = ENTRY_PROFILES[ep_id]
    sl = SL_PLACEMENTS[sl_id]
    cm = CellMetrics(months={})
    for month, m15 in months_data.items():
        month_metrics = {"net": 0.0, "n": 0, "tp": 0, "sl": 0}
        for idx in range(len(m15)):
            f = compute_features(idx, m15)
            if not f or not filter_pass(f, ep):
                continue
            cm.n_signals += 1
            res = simulate(m15, idx, f["side"], sl["sl_frac"])
            if not res.filled:
                continue
            cm.n_filled += 1
            month_metrics["n"] += 1
            if res.outcome == "TP":
                cm.n_tp += 1
                cm.sum_rr += res.rr_win
                month_metrics["net"] += res.rr_win
                month_metrics["tp"] += 1
            elif res.outcome == "SL":
                cm.n_sl += 1
                month_metrics["net"] -= 1.0
                month_metrics["sl"] += 1
            else:
                cm.n_to += 1
        cm.months[month] = month_metrics
    return cm


def aggregate_metrics(cm: CellMetrics, months_count: int) -> dict:
    n_fill = cm.n_filled
    sum_rr = cm.sum_rr
    n_sl = cm.n_sl
    n_tp = cm.n_tp
    pf = sum_rr / n_sl if n_sl else (float("inf") if n_tp else 0.0)
    wr = n_tp / n_fill if n_fill else 0.0
    mean_rr = sum_rr / n_tp if n_tp else 0.0
    net_R = sum_rr - n_sl
    losing = sum(1 for m in cm.months.values() if m["n"] > 0 and m["net"] < 0)
    trading = sum(1 for m in cm.months.values() if m["n"] > 0)
    sigs_per_month = n_fill / max(1, months_count)
    return {
        "n_signals": cm.n_signals,
        "n_filled": n_fill,
        "n_tp": n_tp,
        "n_sl": n_sl,
        "n_timeout": cm.n_to,
        "wr": wr,
        "mean_rr": mean_rr,
        "net_R": net_R,
        "per_trade_R": net_R / n_fill if n_fill else 0.0,
        "pf": pf,
        "losing_months": losing,
        "trading_months": trading,
        "sigs_per_month": sigs_per_month,
    }


def threshold_passes(agg: dict, n_min: int = 30) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    if agg["n_filled"] < n_min:
        ok = False; reasons.append(f"n={agg['n_filled']}<{n_min}")
    if agg["pf"] <= 1.40:
        ok = False; reasons.append(f"PF={agg['pf']:.2f}<=1.40")
    if agg["mean_rr"] < 0.5:
        ok = False; reasons.append(f"meanRR={agg['mean_rr']:.3f}<0.5")
    if agg["sigs_per_month"] < 6:
        ok = False; reasons.append(f"sigs/mo={agg['sigs_per_month']:.1f}<6")
    if agg["trading_months"] > 0:
        loss_pct = agg["losing_months"] / agg["trading_months"]
        if loss_pct > 0.30:
            ok = False; reasons.append(f"losM%={loss_pct*100:.0f}>30")
    return ok, reasons


def fmt_pf(x: float) -> str:
    if x == float("inf"): return "inf"
    return f"{x:.2f}"


def write_report(cells_train, cells_test, cells_full, out_md):
    md: list[str] = []
    md.append("# Phase 15 backtest -- M15 v0.5.0 optimization with train/test split\n\n")
    md.append("4 entry profiles x 4 SL placements = 16 cells.\n")
    md.append("Train: 2024-01..2025-05 (17 months). Test: 2025-06..2026-05 (12 months).\n\n")
    md.append("Pre-committed thresholds per half: n>=30, PF>1.40, meanRR>=0.5, ")
    md.append("sigs/mo>=6, losing_months<=30 percent.\n\n")
    md.append("## Result table\n\n")
    md.append("Each cell shows TRAIN | TEST | FULL aggregate.\n\n")
    md.append("```\n")
    md.append(f"{'cell':<5}  {'profile':<8}  {'SL':<10}  ")
    md.append(f"{'TR-n':>5} {'TR-WR':>6} {'TR-PF':>6} {'TR-net':>7} {'TR-sm':>5}  ")
    md.append(f"{'TE-n':>5} {'TE-WR':>6} {'TE-PF':>6} {'TE-net':>7} {'TE-sm':>5}  ")
    md.append(f"{'verdict':<14}\n")
    md.append("-" * 130 + "\n")

    for ep_id in "ABCD":
        for sl_id in ["S1","S2","S3","S4"]:
            cell = f"{ep_id}-{sl_id}"
            agg_tr = aggregate_metrics(cells_train[cell], len(TRAIN_MONTHS))
            agg_te = aggregate_metrics(cells_test[cell],  len(TEST_MONTHS))
            ok_tr, reasons_tr = threshold_passes(agg_tr, n_min=30)
            ok_te, reasons_te = threshold_passes(agg_te, n_min=20)
            both = "PASS" if (ok_tr and ok_te) else "REJECT"
            why = ""
            if not ok_tr: why = "TR: " + ",".join(reasons_tr)
            if not ok_te: why = ("TE: " + ",".join(reasons_te)) if not ok_tr else why + " | TE: " + ",".join(reasons_te)
            md.append(
                f"{cell:<5}  "
                f"{ENTRY_PROFILES[ep_id]['label']:<8}  "
                f"{SL_PLACEMENTS[sl_id]['label']:<10}  "
                f"{agg_tr['n_filled']:>5} {agg_tr['wr']*100:>5.1f}% {fmt_pf(agg_tr['pf']):>6} {agg_tr['net_R']:>+6.2f} {agg_tr['sigs_per_month']:>5.1f}  "
                f"{agg_te['n_filled']:>5} {agg_te['wr']*100:>5.1f}% {fmt_pf(agg_te['pf']):>6} {agg_te['net_R']:>+6.2f} {agg_te['sigs_per_month']:>5.1f}  "
                f"{both:<14}\n"
            )
    md.append("```\n\n")

    # Detail for cells that pass both
    md.append("## Cells passing BOTH train and test\n\n")
    pass_cells = []
    for ep_id in "ABCD":
        for sl_id in ["S1","S2","S3","S4"]:
            cell = f"{ep_id}-{sl_id}"
            agg_tr = aggregate_metrics(cells_train[cell], len(TRAIN_MONTHS))
            agg_te = aggregate_metrics(cells_test[cell],  len(TEST_MONTHS))
            ok_tr, _ = threshold_passes(agg_tr, n_min=30)
            ok_te, _ = threshold_passes(agg_te, n_min=20)
            if ok_tr and ok_te:
                pass_cells.append((cell, ep_id, sl_id, agg_tr, agg_te))
    if not pass_cells:
        md.append("None. No cell cleared the thresholds on both halves.\n\n")
    else:
        md.append(f"{len(pass_cells)} cells passed.\n\n")
        for cell, ep_id, sl_id, agg_tr, agg_te in pass_cells:
            agg_full = aggregate_metrics(cells_full[cell], len(TRAIN_MONTHS) + len(TEST_MONTHS))
            md.append(f"### {cell} -- {ENTRY_PROFILES[ep_id]['label']} entry, "
                      f"SL at {SL_PLACEMENTS[sl_id]['label']}\n\n```\n")
            md.append(f"  TRAIN  n={agg_tr['n_filled']} WR={agg_tr['wr']*100:.1f}% PF={fmt_pf(agg_tr['pf'])} "
                      f"net={agg_tr['net_R']:+.2f}R meanRR={agg_tr['mean_rr']:.3f} sigs/mo={agg_tr['sigs_per_month']:.1f}\n")
            md.append(f"  TEST   n={agg_te['n_filled']} WR={agg_te['wr']*100:.1f}% PF={fmt_pf(agg_te['pf'])} "
                      f"net={agg_te['net_R']:+.2f}R meanRR={agg_te['mean_rr']:.3f} sigs/mo={agg_te['sigs_per_month']:.1f}\n")
            md.append(f"  FULL   n={agg_full['n_filled']} WR={agg_full['wr']*100:.1f}% PF={fmt_pf(agg_full['pf'])} "
                      f"net={agg_full['net_R']:+.2f}R meanRR={agg_full['mean_rr']:.3f} sigs/mo={agg_full['sigs_per_month']:.1f}\n")
            md.append("```\n\n")
    out_md.write_text("".join(md), encoding="utf-8")


def main():
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("[0-9]*-m5.json"))
    months_data: dict[str, list[dict]] = {}
    for slug in months:
        m5 = json.loads((CACHE / f"{slug}-m5.json").read_text(encoding="utf-8"))
        m5.sort(key=lambda b: b["time"])
        months_data[slug] = aggregate_m5_to_m15(m5)

    train_data = {m: months_data[m] for m in TRAIN_MONTHS if m in months_data}
    test_data  = {m: months_data[m] for m in TEST_MONTHS if m in months_data}
    full_data  = months_data

    print(f"Train months: {len(train_data)}  Test months: {len(test_data)}")
    print(f"Total bars: train={sum(len(v) for v in train_data.values())} "
          f"test={sum(len(v) for v in test_data.values())}\n")

    cells_train: dict[str, CellMetrics] = {}
    cells_test:  dict[str, CellMetrics] = {}
    cells_full:  dict[str, CellMetrics] = {}

    print(f"{'cell':<5}  {'TR n':>4} {'TR PF':>6} {'TR sm':>5}  "
          f"{'TE n':>4} {'TE PF':>6} {'TE sm':>5}  {'verdict'}")
    print("-" * 90)
    for ep_id in "ABCD":
        for sl_id in ["S1","S2","S3","S4"]:
            cell = f"{ep_id}-{sl_id}"
            cells_train[cell] = run_cell(train_data, ep_id, sl_id)
            cells_test[cell]  = run_cell(test_data,  ep_id, sl_id)
            cells_full[cell]  = run_cell(full_data,  ep_id, sl_id)
            agg_tr = aggregate_metrics(cells_train[cell], len(TRAIN_MONTHS))
            agg_te = aggregate_metrics(cells_test[cell],  len(TEST_MONTHS))
            ok_tr, _ = threshold_passes(agg_tr, n_min=30)
            ok_te, _ = threshold_passes(agg_te, n_min=20)
            status = "PASS BOTH" if (ok_tr and ok_te) else "reject"
            print(f"{cell:<5}  {agg_tr['n_filled']:>4} {fmt_pf(agg_tr['pf']):>6} {agg_tr['sigs_per_month']:>5.1f}  "
                  f"{agg_te['n_filled']:>4} {fmt_pf(agg_te['pf']):>6} {agg_te['sigs_per_month']:>5.1f}  "
                  f"{status}")

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / "phase15-results.json"
    serializable = {}
    for cell in cells_train:
        serializable[cell] = {
            "train": aggregate_metrics(cells_train[cell], len(TRAIN_MONTHS)),
            "test":  aggregate_metrics(cells_test[cell],  len(TEST_MONTHS)),
            "full":  aggregate_metrics(cells_full[cell],  len(TRAIN_MONTHS)+len(TEST_MONTHS)),
        }
    out_json.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved to {out_json}")
    out_md = OUT / "phase15-report.md"
    write_report(cells_train, cells_test, cells_full, out_md)
    print(f"Saved report to {out_md}")


if __name__ == "__main__":
    main()
