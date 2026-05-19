"""Pull April 2026 M5 XAUUSD candles directly via MetaTrader5 copy_rates_range.

The MCP `get_candles_latest` tool maxes at 5000 bars which doesn't reach
April 1 from the current date. This one-shot uses copy_rates_range to
pull a full month.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")

# Load .env
env = ROOT / ".env"
for line in env.read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, v = s.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip())

from mt5_mvp.client import init_mt5  # noqa: E402

import MetaTrader5 as mt5  # noqa: E402

if not init_mt5():
    raise SystemExit("MT5 init failed")

start = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
end = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

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

out = ROOT / "cache" / "april2026-m5.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(bars), encoding="utf-8")

print(f"Pulled {len(bars)} M5 bars for April 2026")
print(f"Earliest: {datetime.fromtimestamp(bars[0]['time'], tz=timezone.utc).isoformat()}")
print(f"Latest:   {datetime.fromtimestamp(bars[-1]['time'], tz=timezone.utc).isoformat()}")
print(f"Saved to {out}")

mt5.shutdown()
