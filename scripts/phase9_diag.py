"""Quick diagnostic on Phase 9 V2 — is FVGC keeping the good signals?

Splits the 440 V1 (LSD raw) trades into:
  - kept by FVGC (V2's 263 trades)
  - dropped by FVGC (the other 177 trades)

If FVGC is real edge, the dropped 177 should perform clearly worse than
the kept 263. If FVGC is noise, both halves should look similar.

Also re-runs FVGE separately with diagnostics so we know why it fired 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from phase9_amd_fvg_backtest import (  # noqa: E402
    CACHE,
    compute_atr14,
    confl_fvgc,
    confl_fvge,
    detect_fvg,
    generate_lsd_signals,
    simulate,
)


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Months: {len(months)}\n")

    kept_results = []
    dropped_results = []

    fvge_total_fvgs_before_lsd = 0
    fvge_lsd_with_zone_overlap = 0
    fvge_lsd_passing = 0

    for slug in months:
        candles = json.loads((CACHE / f"{slug}-m5.json").read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        atr = compute_atr14(candles)
        lsd = generate_lsd_signals(slug, candles, atr)

        # Diagnose FVGE
        for sig in lsd:
            for i in range(max(2, sig.idx - 50), sig.idx):
                fvg = detect_fvg(candles, i)
                if fvg:
                    fvge_total_fvgs_before_lsd += 1
            if confl_fvge(candles, sig):
                fvge_lsd_passing += 1
            # quick overlap check: just do FVGE with no fill check
            if sig.candle_range > 0:
                if sig.side == "BUY":
                    entry = sig.candle_high - 0.236 * sig.candle_range
                    target = "bullish"
                else:
                    entry = sig.candle_low + 0.236 * sig.candle_range
                    target = "bearish"
                for i in range(max(2, sig.idx - 50), sig.idx):
                    fvg = detect_fvg(candles, i)
                    if fvg and fvg["side"] == target and fvg["low"] <= entry <= fvg["high"]:
                        fvge_lsd_with_zone_overlap += 1
                        break

        for sig in lsd:
            res = simulate(candles, sig, "fib_127")
            row = {
                "month": slug,
                "outcome": res.outcome,
                "filled": res.filled,
                "rr_win": res.rr_win,
                "fvgc": confl_fvgc(candles, sig),
            }
            if row["fvgc"]:
                kept_results.append(row)
            else:
                dropped_results.append(row)

    def summarise(label: str, rows: list[dict]) -> None:
        n_total = len(rows)
        filled = [r for r in rows if r["filled"]]
        n_filled = len(filled)
        n_tp = sum(1 for r in filled if r["outcome"] == "TP")
        n_sl = sum(1 for r in filled if r["outcome"] == "SL")
        n_to = n_filled - n_tp - n_sl
        sum_rr = sum(r["rr_win"] for r in filled if r["rr_win"] is not None)
        net = sum_rr - n_sl
        wr = n_tp / n_filled if n_filled else 0.0
        pf = sum_rr / n_sl if n_sl else (float("inf") if n_tp else 0.0)
        per_trade = net / n_filled if n_filled else 0.0
        print(f"=== {label} ===")
        print(f"  total signals:   {n_total}")
        print(f"  filled:          {n_filled}")
        print(f"  TP / SL / TO:    {n_tp} / {n_sl} / {n_to}")
        print(f"  WR:              {wr * 100:.1f}%")
        print(f"  PF:              {pf if pf != float('inf') else 'inf'}")
        print(f"  net R:           {net:+.2f}")
        print(f"  per-trade R:     {per_trade:+.3f}")
        print()

    summarise("Kept by FVGC (V2)", kept_results)
    summarise("Dropped by FVGC (V1 minus V2)", dropped_results)

    print("=== FVGE diagnostic ===")
    print(f"  FVGs in 50-bar window before any LSD signal: {fvge_total_fvgs_before_lsd}")
    print(f"  LSD signals with any zone overlap (no fill check): {fvge_lsd_with_zone_overlap}")
    print(f"  LSD signals passing full FVGE rule (with fill check): {fvge_lsd_passing}")


if __name__ == "__main__":
    main()
