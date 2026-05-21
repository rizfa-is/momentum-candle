"""Analyze MT5 account history CSV (semicolon-separated).

Determines whether the trades match the v0.5.0 momentum-candle strategy
or a different strategy entirely. Reports:
- symbol(s) traded
- timeframe inferred from entry timestamps
- presence of stop-loss
- lot scaling pattern (martingale/grid?)
- position concurrency
- average hold time
- net P/L and win rate
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def to_float(s: str | None) -> float | None:
    if not s:
        return None
    # MT5 sometimes uses non-breaking space as thousand separator
    cleaned = s.replace("\xa0", "").replace(" ", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None


def main(path: str) -> None:
    rows: list[dict] = []
    balance_rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            t = (row.get("Type") or "").strip()
            if t == "Balance":
                balance_rows.append(row)
                continue
            if t in ("Buy", "Sell"):
                rows.append(row)

    print(f"Total trades: {len(rows)}")
    print(f"Balance adjustments: {len(balance_rows)}")
    if balance_rows:
        bal_total = sum((to_float(r["Profit"]) or 0.0) for r in balance_rows)
        print(f"  Sum: {bal_total:+.2f}")

    if not rows:
        return

    # Symbols
    symbols = defaultdict(int)
    for r in rows:
        symbols[r["Symbol"]] += 1
    print(f"\nSymbols: {dict(symbols)}")

    # Timeframe inference -- look at minute distribution of entry times
    minute_buckets = defaultdict(int)
    for r in rows:
        dt = parse_dt(r["Time"])
        if dt:
            minute_buckets[dt.minute] += 1
    print(f"\nEntry minute distribution (top 8):")
    for m, n in sorted(minute_buckets.items(), key=lambda x: -x[1])[:8]:
        pct = n / len(rows) * 100
        print(f"  :{m:02d}  {n:>4}  ({pct:.1f}%)")

    # Stop-loss presence
    has_sl = sum(1 for r in rows if (r.get("S/L") or "").strip())
    print(f"\nTrades with stop-loss set: {has_sl} / {len(rows)} ({has_sl / len(rows) * 100:.1f}%)")

    # TP presence
    has_tp = sum(1 for r in rows if (r.get("T/P") or "").strip())
    print(f"Trades with TP set:        {has_tp} / {len(rows)} ({has_tp / len(rows) * 100:.1f}%)")

    # Side breakdown
    sides = defaultdict(int)
    for r in rows:
        sides[r["Type"]] += 1
    print(f"\nSide split: {dict(sides)}")

    # Lot scaling: detect "groups" closing at the same time with same TP
    groups = defaultdict(list)
    for r in rows:
        # closing time is the second Time column (DictReader handles it as Time_2 / unique key)
        # MT5 CSV has duplicate "Time" headers; csv module renames them
        # Look for the second time column
        keys = list(r.keys())
        close_time_key = next((k for k in keys[7:] if "Time" in (k or "")), None)
        # Fallback: positional
        close_time = list(r.values())[7]
        tp = (r.get("T/P") or "").strip()
        sym = r["Symbol"]
        side = r["Type"]
        groups[(sym, side, close_time, tp)].append(r)

    multi_groups = [g for g in groups.values() if len(g) > 1]
    avg_group_size = sum(len(g) for g in multi_groups) / len(multi_groups) if multi_groups else 0
    max_group_size = max((len(g) for g in groups.values()), default=0)
    print(f"\nLayering / grid pattern detection:")
    print(f"  Groups closing together: {len(multi_groups)}")
    print(f"  Avg trades per group:    {avg_group_size:.2f}")
    print(f"  Max trades in one group: {max_group_size}")

    # Lot ratio inside groups
    lot_ratios = []
    for g in multi_groups:
        if len(g) < 2:
            continue
        # sort by entry time ascending
        g_sorted = sorted(g, key=lambda r: parse_dt(r["Time"]) or datetime.min)
        for i in range(1, len(g_sorted)):
            prev_lot = to_float(g_sorted[i - 1]["Volume"]) or 0.0
            cur_lot = to_float(g_sorted[i]["Volume"]) or 0.0
            if prev_lot > 0:
                lot_ratios.append(cur_lot / prev_lot)
    if lot_ratios:
        avg_ratio = sum(lot_ratios) / len(lot_ratios)
        print(f"  Avg lot-step ratio: {avg_ratio:.2f}x  (1.0 = no scaling)")

    # Hold-time distribution
    holds = []
    for r in rows:
        t1 = parse_dt(r["Time"])
        # second time column from the row
        t2_raw = list(r.values())[7]
        t2 = parse_dt(t2_raw)
        if t1 and t2:
            holds.append((t2 - t1).total_seconds() / 60)
    if holds:
        holds_sorted = sorted(holds)
        med = holds_sorted[len(holds_sorted) // 2]
        avg = sum(holds_sorted) / len(holds_sorted)
        print(f"\nHold time (minutes):")
        print(f"  median:  {med:>7.1f}")
        print(f"  mean:    {avg:>7.1f}")
        print(f"  max:     {max(holds_sorted):>7.1f}")

    # P/L stats
    profits = [v for v in (to_float(r.get("Profit")) for r in rows) if v is not None]
    n_win = sum(1 for p in profits if p > 0)
    n_loss = sum(1 for p in profits if p < 0)
    n_be = sum(1 for p in profits if p == 0)
    gross_pos = sum(p for p in profits if p > 0)
    gross_neg = -sum(p for p in profits if p < 0)
    net = sum(profits)
    pf = gross_pos / gross_neg if gross_neg > 0 else float("inf")
    print(f"\nP/L:")
    print(f"  trades:  {len(profits)}")
    print(f"  wins:    {n_win} ({n_win / len(profits) * 100:.1f}%)")
    print(f"  losses:  {n_loss} ({n_loss / len(profits) * 100:.1f}%)")
    print(f"  BE:      {n_be}")
    print(f"  gross +: {gross_pos:+.2f}")
    print(f"  gross -: {-gross_neg:+.2f}")
    print(f"  net:     {net:+.2f}")
    print(f"  PF:      {pf:.2f}")

    # All [tp] comments?
    comments = defaultdict(int)
    for r in rows:
        comments[(r.get("Comment") or "").strip()] += 1
    print(f"\nComment distribution:")
    for c, n in sorted(comments.items(), key=lambda x: -x[1]):
        print(f"  {c!r:<20}  {n}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"data\history\2141713.history.csv")
