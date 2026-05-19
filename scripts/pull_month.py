"""Generic month puller. Usage:

    uv run python scripts/pull_month.py 2026 1
    uv run python scripts/pull_month.py 2026 2
    uv run python scripts/pull_month.py 2026 3

Pulls the entire month of M5 XAUUSD via copy_rates_range and saves
to cache/<YYYY-MM>-m5.json.
"""

from __future__ import annotations

import calendar
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")

env = ROOT / ".env"
for line in env.read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: pull_month.py <year> <month>")
        sys.exit(1)
    year = int(sys.argv[1])
    month = int(sys.argv[2])
    last_day = calendar.monthrange(year, month)[1]

    from mt5_mvp.client import init_mt5
    import MetaTrader5 as mt5

    if not init_mt5():
        raise SystemExit("MT5 init failed")

    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M5, start, end)
    if rates is None or len(rates) == 0:
        raise SystemExit(f"copy_rates_range returned no data: {mt5.last_error()}")

    bars = []
    for r in rates:
        bars.append(
            {
                "time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "tick_volume": int(r[5]),
                "spread": int(r[6]),
                "real_volume": int(r[7]),
            }
        )
    bars.sort(key=lambda b: b["time"])

    slug = f"{year:04d}-{month:02d}"
    out = ROOT / "cache" / f"{slug}-m5.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bars), encoding="utf-8")

    earliest = datetime.fromtimestamp(bars[0]["time"], tz=timezone.utc)
    latest = datetime.fromtimestamp(bars[-1]["time"], tz=timezone.utc)
    print(f"Pulled {len(bars)} bars for {slug}")
    print(f"  earliest: {earliest.isoformat()}")
    print(f"  latest:   {latest.isoformat()}")
    print(f"  saved to: {out}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
