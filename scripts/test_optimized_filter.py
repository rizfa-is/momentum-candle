"""Run the optimized filter from `may2026-takeaways.md` against the May
2026 dataset and compare to the baseline filter.

Optimized filter (eight stacked rules):
  body / range          >= 0.86
  close-side wick / range <= 0.10
  far-side wick / range  <= 0.05
  body in points        >= 1000
  range in points       >= 1100   (= 11 USD)
  distance to nearest $50 round in [0, 15]
  session               != London
  trend_monotonic_prior_7 <= 4

Both entry modes (next_open + pullback_236) tested.

Reads the enriched per-signal data from `may2026-factor-analysis.json`
because the features are already computed there.

Writes:
  data/backtests/may2026-optimized.json
  data/backtests/may2026-optimized.md
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
SRC = ROOT / "data" / "backtests" / "may2026-factor-analysis.json"
OUT_JSON = ROOT / "data" / "backtests" / "may2026-optimized.json"
OUT_MD = ROOT / "data" / "backtests" / "may2026-optimized.md"


def passes_optimized(s: dict) -> bool:
    f = s["features"]
    if f["body_pct"] < 0.86:
        return False
    if f["close_wick_pct"] > 0.10:
        return False
    if f["far_wick_pct"] > 0.05:
        return False
    if f["body_points"] < 1000:
        return False
    if f["range"] < 11.0:
        return False
    if f["dist_to_round_50"] > 15.0:
        return False
    if f["session"] == "London":
        return False
    if f["trend_monotonic"] > 4:
        return False
    return True


def summarise(label: str, signals: list[dict], baseline_n: int) -> dict:
    filled = [s for s in signals if s.get("filled", True)]
    n_total = len(signals)
    n_filled = len(filled)
    n_tp2 = sum(1 for s in filled if s["outcome"] == "TP2")
    n_sl = sum(1 for s in filled if s["outcome"] == "SL")
    rr_wins = []
    for s in filled:
        if s["outcome"] != "TP2":
            continue
        risk = abs(s["entry_price"] - s["sl"])
        reward = abs(s["tp2"] - s["entry_price"])
        if risk > 0:
            rr_wins.append(reward / risk)
    sum_pos = sum(rr_wins)
    gross_loss = float(n_sl)
    net = sum_pos - gross_loss
    per_trade = net / n_filled if n_filled else 0
    pf = sum_pos / gross_loss if gross_loss else float("inf")
    wr = n_tp2 / n_filled if n_filled else 0
    be_wr = 1.0 / (1.0 + sum(rr_wins) / len(rr_wins)) if rr_wins else 0
    return {
        "label": label,
        "baseline_n": baseline_n,
        "n_total": n_total,
        "n_filled": n_filled,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "wr": wr,
        "be_wr": be_wr,
        "mean_rr_win": sum(rr_wins) / len(rr_wins) if rr_wins else 0,
        "net_R": net,
        "per_trade_R": per_trade,
        "pf": pf,
    }


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    next_results = raw["next_open"]
    pull_results = raw["pullback_236"]

    next_filtered = [s for s in next_results if passes_optimized(s)]
    pull_filtered = [s for s in pull_results if passes_optimized(s)]

    out_data = {
        "filter_rules": {
            "body_pct_min": 0.86,
            "close_wick_pct_max": 0.10,
            "far_wick_pct_max": 0.05,
            "body_points_min": 1000,
            "range_min_usd": 11.0,
            "dist_to_round_50_max": 15.0,
            "session_skip": ["London"],
            "trend_monotonic_max": 4,
        },
        "next_open_optimized": next_filtered,
        "pullback_236_optimized": pull_filtered,
    }
    OUT_JSON.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    n_summary = summarise("next_open optimized", next_filtered, len(next_results))
    p_summary = summarise("pullback_236 optimized", pull_filtered, len(pull_results))

    md: list[str] = []
    md.append("# May 2026 -- optimized filter results\n\n")
    md.append("Comparison of the 8-rule optimized filter (from `may2026-takeaways.md`) ")
    md.append("vs the original 3-rule baseline filter on the same May 2026 dataset.\n\n")
    md.append("## Filter rules applied\n\n")
    md.append("```\n")
    md.append("body / range            >= 0.86         (was 0.80)\n")
    md.append("close-side wick / range <= 0.10\n")
    md.append("far-side wick / range   <= 0.05         (NEW)\n")
    md.append("body in price points    >= 1000         (was 800)\n")
    md.append("range in USD            >= 11.0         (NEW)\n")
    md.append("distance to nearest $50 in [0, 15] USD  (NEW: avoid donut zone)\n")
    md.append("session                 != London       (NEW: skip 8-12 UTC)\n")
    md.append("trend_monotonic_prior_7 <= 4            (NEW: skip exhausted trends)\n")
    md.append("```\n\n")

    md.append("## Headline comparison\n\n")
    md.append("```\n")
    md.append(f"                                  baseline       optimized       delta\n")
    md.append(f"────────────────────────────────────────────────────────────────────────\n")
    md.append(f"NEXT_OPEN entry\n")
    md.append(f"  signals fired                   72             {n_summary['n_total']:>2}             {n_summary['n_total'] - 72:+d}\n")
    md.append(f"  filled                          72             {n_summary['n_filled']:>2}             {n_summary['n_filled'] - 72:+d}\n")
    md.append(f"  TP2 hit                         53 (73.6%)     {n_summary['n_tp2']:>2} ({n_summary['wr'] * 100:.1f}%)     {n_summary['wr'] * 100 - 73.6:+.1f}pp\n")
    md.append(f"  SL hit                          19 (26.4%)     {n_summary['n_sl']:>2} ({(1 - n_summary['wr']) * 100:.1f}%)     {(1 - n_summary['wr']) * 100 - 26.4:+.1f}pp\n")
    md.append(f"  Mean RR per win                 0.287          {n_summary['mean_rr_win']:.3f}           {n_summary['mean_rr_win'] - 0.287:+.3f}\n")
    md.append(f"  Net PnL                         -3.79 R        {n_summary['net_R']:+.2f} R         {n_summary['net_R'] + 3.79:+.2f} R\n")
    md.append(f"  Per-trade                       -0.053 R       {n_summary['per_trade_R']:+.3f} R        {n_summary['per_trade_R'] + 0.053:+.3f} R\n")
    md.append(f"  Profit factor                   0.80           {n_summary['pf']:.2f}            {n_summary['pf'] - 0.80:+.2f}\n")
    md.append(f"  Break-even WR                   77.7%          {n_summary['be_wr'] * 100:.1f}%          {n_summary['be_wr'] * 100 - 77.7:+.1f}pp\n")
    md.append(f"\n")
    md.append(f"PULLBACK_236 entry\n")
    md.append(f"  signals fired                   72             {p_summary['n_total']:>2}             {p_summary['n_total'] - 72:+d}\n")
    md.append(f"  filled                          65             {p_summary['n_filled']:>2}             {p_summary['n_filled'] - 65:+d}\n")
    md.append(f"  TP2 hit                         43 (66.2%)     {p_summary['n_tp2']:>2} ({p_summary['wr'] * 100:.1f}%)     {p_summary['wr'] * 100 - 66.2:+.1f}pp\n")
    md.append(f"  SL hit                          22 (33.8%)     {p_summary['n_sl']:>2} ({(1 - p_summary['wr']) * 100:.1f}%)     {(1 - p_summary['wr']) * 100 - 33.8:+.1f}pp\n")
    md.append(f"  Mean RR per win                 0.586          {p_summary['mean_rr_win']:.3f}           {p_summary['mean_rr_win'] - 0.586:+.3f}\n")
    md.append(f"  Net PnL                         +3.18 R        {p_summary['net_R']:+.2f} R         {p_summary['net_R'] - 3.18:+.2f} R\n")
    md.append(f"  Per-trade                       +0.049 R       {p_summary['per_trade_R']:+.3f} R        {p_summary['per_trade_R'] - 0.049:+.3f} R\n")
    md.append(f"  Profit factor                   1.14           {p_summary['pf']:.2f}            {p_summary['pf'] - 1.14:+.2f}\n")
    md.append(f"  Break-even WR                   63.1%          {p_summary['be_wr'] * 100:.1f}%          {p_summary['be_wr'] * 100 - 63.1:+.1f}pp\n")
    md.append("```\n\n")

    md.append("## Caveats\n\n")
    md.append("- **Overfit risk is real.** The same dataset was used to identify the filters and now to test them. ")
    md.append("Out-of-sample (April 2026 or earlier) is needed to confirm the lift survives.\n")
    md.append("- **Sample size shrinks** under the optimized filter. Wider confidence interval on the WR.\n")
    md.append("- **Spread cost still applies.** ~80-point InstaForex spread takes ~0.10R per pullback trade. ")
    md.append("Net real-money PF is roughly the reported PF minus 0.1.\n")
    md.append("- **Trade frequency matters.** A higher PF with fewer trades may not be commercially better than ")
    md.append("a lower PF with more trades; depends on capital deployment goals.\n\n")

    md.append("## Per-signal pass list\n\n")
    md.append("Signals that survive the optimized filter, with their actual outcomes:\n\n")
    md.append("```\n")
    md.append(f"{'#':>3}  {'time UTC':<19}  {'side':<4}  {'sess':<6}  {'body%':>5}  {'fwick%':>6}  {'body_pt':>7}  {'range':>5}  {'dist50':>6}  {'next_op':<7}  {'pullbk':<7}\n")
    md.append("-" * 110 + "\n")

    # Use the next_filtered list (same set as pull_filtered since same features)
    union_idx = sorted({s["idx"] for s in next_filtered}, key=lambda i: i)
    next_by_idx = {s["idx"]: s for s in next_filtered}
    pull_by_idx = {s["idx"]: s for s in pull_results}
    for n_, idx in enumerate(union_idx, 1):
        s = next_by_idx[idx]
        f = s["features"]
        p = pull_by_idx.get(idx, {})
        next_outcome = s.get("outcome", "?")
        pull_outcome = p.get("outcome") if p.get("filled", True) else "no-fill"
        md.append(
            f"{n_:>3}  {s['time_utc'][:19]:<19}  {s['side']:<4}  {f['session']:<6}  "
            f"{f['body_pct'] * 100:>4.0f}%  {f['far_wick_pct'] * 100:>5.0f}%  {f['body_points']:>7.0f}  "
            f"{f['range']:>5.2f}  {f['dist_to_round_50']:>6.2f}  {next_outcome:<7}  {str(pull_outcome):<7}\n"
        )
    md.append("```\n\n")

    OUT_MD.write_text("".join(md), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print()
    print("=== Summary ===")
    for label, summ in [("next_open", n_summary), ("pullback_236", p_summary)]:
        print(f"\n{label} optimized:")
        print(f"  signals: {summ['n_total']}, filled: {summ['n_filled']}")
        print(f"  WR: {summ['wr'] * 100:.1f}%   BE-WR: {summ['be_wr'] * 100:.1f}%")
        print(f"  Mean RR per win: {summ['mean_rr_win']:.3f}")
        print(f"  Net: {summ['net_R']:+.2f} R   Per trade: {summ['per_trade_R']:+.3f} R   PF: {summ['pf']:.2f}")


if __name__ == "__main__":
    main()
