"""Per-month side-by-side: V2 (LSD+FVGC) vs v0.5.0 (momentum-candle).

Tests for portfolio diversification potential. If both strategies lose
the same months, they share regime risk. If they lose different months,
they're diversifying.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")


def main() -> None:
    p9 = json.loads((ROOT / "data" / "backtests" / "phase9-results.json").read_text())
    mm = json.loads((ROOT / "data" / "backtests" / "multi-month-results.json").read_text())

    v2 = p9["per_month"]["V2"]
    v05_key = "optimized_no_round | pullback_236"

    months = sorted(v2.keys())

    print(f"{'month':<10} {'V2_n':>5} {'V2_WR':>6} {'V2_netR':>8}  {'v05_n':>5} {'v05_WR':>7} {'v05_netR':>8}")
    print("-" * 75)

    v2_losing = []
    v05_losing = []
    both_losing = 0
    only_v2 = 0
    only_v05 = 0
    both_winning = 0

    for month in months:
        v2m = v2[month]
        v2_n = v2m["n_filled"]
        v2_wr = v2m["n_tp"] / v2_n * 100 if v2_n else 0.0
        v2_net = v2m["sum_rr"] - v2m["n_sl"]

        mm_key = f"{month} | optimized_no_round | pullback_236"
        v05 = mm.get(mm_key, {})
        v05_n = v05.get("n_filled", 0)
        v05_wr = v05.get("wr", 0.0) * 100
        v05_net = v05.get("net_R", 0.0)

        v2_loss = v2_net < 0 and v2_n > 0
        v05_loss = v05_net < 0 and v05_n > 0

        if v2_loss:
            v2_losing.append(month)
        if v05_loss:
            v05_losing.append(month)

        if v2_loss and v05_loss:
            both_losing += 1
            tag = "  <-both"
        elif v2_loss:
            only_v2 += 1
            tag = "  <-v2 only"
        elif v05_loss:
            only_v05 += 1
            tag = "  <-v05 only"
        elif v2_n > 0 and v05_n > 0:
            both_winning += 1
            tag = ""
        else:
            tag = ""

        print(
            f"{month:<10} {v2_n:>5} {v2_wr:>5.1f}% {v2_net:>+7.2f}R  "
            f"{v05_n:>5} {v05_wr:>6.1f}% {v05_net:>+7.2f}R{tag}"
        )

    print()
    print(f"V2 losing months:    {len(v2_losing)} ({', '.join(v2_losing)})")
    print(f"v0.5.0 losing months: {len(v05_losing)} ({', '.join(v05_losing)})")
    print()
    print(f"Both losing same month:  {both_losing}")
    print(f"V2 losing only:          {only_v2}")
    print(f"v0.5.0 losing only:      {only_v05}")
    print(f"Months both active and winning:  {both_winning}")

    # Combined portfolio at equal weighting
    print()
    print("Portfolio (V2 + v0.5.0, equal-weight, 1% risk each):")
    total_net = 0.0
    portfolio_loss_months = 0
    for month in months:
        v2m = v2[month]
        v2_net = v2m["sum_rr"] - v2m["n_sl"]
        mm_key = f"{month} | optimized_no_round | pullback_236"
        v05_net = mm.get(mm_key, {}).get("net_R", 0.0)
        combined = v2_net + v05_net
        total_net += combined
        if combined < 0:
            portfolio_loss_months += 1
    print(f"  total net R:        {total_net:+.2f}")
    print(f"  losing months:      {portfolio_loss_months} / {len(months)}")


if __name__ == "__main__":
    main()
