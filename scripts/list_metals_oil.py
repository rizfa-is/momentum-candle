"""List MT5 symbols matching metals or oil patterns."""
import os
from pathlib import Path
ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
env = ROOT / ".env"
if env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
from mt5_mvp.client import init_mt5
import MetaTrader5 as mt5
if not init_mt5():
    raise SystemExit("MT5 init failed")
needles = ["XAG", "XAU", "XPD", "XPT", "OIL", "BRENT", "WTI", "BREN", "USOIL", "UKOIL", "CL", "WTICO"]
matches = []
for s in mt5.symbols_get():
    name = s.name.upper()
    if any(n in name for n in needles):
        matches.append((s.name, s.path, s.visible, s.trade_mode))
for n, p, v, t in matches:
    print(f"{n:<20} visible={v}  path={p}")
print(f"\ntotal: {len(matches)}")
mt5.shutdown()
