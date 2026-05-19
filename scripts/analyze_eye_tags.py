"""Analyze eye-tag worksheets: parse tags + features and produce a summary."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("usage: python analyze_eye_tags.py <path-to-worksheet.md>")
    sys.exit(1)

ws_path = Path(sys.argv[1])
src = ws_path.read_text(encoding="utf-8")

# --- Parse the candidate table -------------------------------------------
# Format: "  5  02:30  04:30  A     SELL   15.18    86%     6%  3.61x  1.90x  ALGO      STEV    0.820"
table_re = re.compile(
    r"^\s*(\d{1,3})\s+(\d{2}:\d{2})\s+(\d{2}:\d{2})\s+(\S+)\s+(BUY|SELL)\s+([\d.]+)\s+(\d+)%\s+(\d+)%\s+([\d.]+)x\s+([\d.]+)x\s+(\S+)\s+(\S+)\s+([\d.]+)\s*$",
    re.M | re.I,
)

features: dict[int, dict] = {}
for g in table_re.findall(src):
    features[int(g[0])] = {
        "time_utc": g[1],
        "time_brk": g[2],
        "sess": g[3],
        "side": g[4].upper(),
        "range": float(g[5]),
        "body_pct": int(g[6]) / 100.0,
        "wick_pct": int(g[7]) / 100.0,
        "R5": float(g[8]),
        "V5": float(g[9]),
        "flag": g[10],
        "ctx": "" if g[11] == "-" else g[11],
        "score": float(g[12]),
    }

# --- Parse the eye-tag block ---------------------------------------------
m = re.search(r"# eye-tags below.*?\n(.*?)(?:\n```|\Z)", src, re.S)
block = m.group(1) if m else ""
tag_re = re.compile(
    r"^\s*(\d{1,3})\s+(\d{2}:\d{2})\s+(YES|NO)(?:\s+(\S.*?))?\s*$",
    re.M | re.I,
)

tags: dict[int, dict] = {}
for g in tag_re.findall(block):
    tags[int(g[0])] = {
        "time": g[1],
        "verdict": g[2].upper(),
        "reason": (g[3] or "").strip(),
    }

yes_rows = [r for r, t in tags.items() if t["verdict"] == "YES"]
no_rows = [r for r, t in tags.items() if t["verdict"] == "NO"]

print(f"=== {ws_path.name} ===")
print(f"Candidate features parsed: {len(features)}")
print(f"Tags parsed: {len(tags)} (YES={len(yes_rows)}, NO={len(no_rows)})")
print()


# --- Distributions YES vs NO ---------------------------------------------
def stats(rows: list[int], key: str) -> tuple[float, float, float, int]:
    vals = [features[r][key] for r in rows if r in features]
    if not vals:
        return (0.0, 0.0, 0.0, 0)
    return (min(vals), sum(vals) / len(vals), max(vals), len(vals))


print("Feature distributions YES vs NO:")
print(
    f"{'Feature':<12}  {'YES n':>5}  {'YES min':>8}  {'YES mean':>9}  {'YES max':>8}  | "
    f"{'NO n':>5}  {'NO min':>8}  {'NO mean':>9}  {'NO max':>8}"
)
print("-" * 100)
for key in ("range", "body_pct", "wick_pct", "R5", "V5", "score"):
    ymin, ymean, ymax, yn = stats(yes_rows, key)
    nmin, nmean, nmax, nn = stats(no_rows, key)
    if key in ("body_pct", "wick_pct"):
        print(
            f"{key:<12}  {yn:>5}  {ymin * 100:>7.0f}%  {ymean * 100:>8.0f}%  {ymax * 100:>7.0f}%  | "
            f"{nn:>5}  {nmin * 100:>7.0f}%  {nmean * 100:>8.0f}%  {nmax * 100:>7.0f}%"
        )
    else:
        print(
            f"{key:<12}  {yn:>5}  {ymin:>8.2f}  {ymean:>9.2f}  {ymax:>8.2f}  | "
            f"{nn:>5}  {nmin:>8.2f}  {nmean:>9.2f}  {nmax:>8.2f}"
        )

print()

# --- Range floor detection -----------------------------------------------
yes_ranges = sorted(features[r]["range"] for r in yes_rows if r in features)
if yes_ranges:
    floor = min(yes_ranges)
    no_above_floor = [
        features[r] for r in no_rows if r in features and features[r]["range"] >= floor
    ]
    print(f"YES ranges sorted: {[round(r, 2) for r in yes_ranges]}")
    print(f"Min YES range: {floor:.2f}  -> proposed M5 size floor: {floor:.0f} pts")
    print(f"NO bars with range >= floor: {len(no_above_floor)} false positives")
    if no_above_floor:
        for f in no_above_floor[:5]:
            print(f"  NO @ {f['time_utc']} range={f['range']:.2f} body={f['body_pct'] * 100:.0f}% wick={f['wick_pct'] * 100:.0f}%")
print()

# --- Context tag presence -------------------------------------------------
print("Context tag distribution (YES vs NO):")
for letter in "STCEVR":
    y_count = sum(1 for r in yes_rows if r in features and letter in features[r]["ctx"])
    n_count = sum(1 for r in no_rows if r in features and letter in features[r]["ctx"])
    y_rate = (y_count / max(1, len(yes_rows))) * 100
    n_rate = (n_count / max(1, len(no_rows))) * 100
    label = {
        "S": "swing-extreme",
        "T": "trend-monotonic",
        "C": "consolidation",
        "E": "engulfing",
        "V": "velocity-flip",
        "R": "round-number",
    }[letter]
    print(f"  {letter}  {label:<18}  YES: {y_count}/{len(yes_rows)} ({y_rate:>3.0f}%)   NO: {n_count}/{len(no_rows)} ({n_rate:>3.0f}%)")

print()

# --- Session distribution -------------------------------------------------
print("Session distribution:")
for s in ("A", "L", "N", "-"):
    y_count = sum(1 for r in yes_rows if r in features and features[r]["sess"] == s)
    n_count = sum(1 for r in no_rows if r in features and features[r]["sess"] == s)
    label = {"A": "Asia", "L": "London", "N": "NY", "-": "off-window"}[s]
    print(f"  {label:<10}  YES: {y_count}/{len(yes_rows)}   NO: {n_count}/{len(no_rows)}")

print()

# --- Pattern breakdown ----------------------------------------------------
patt_counts: dict[str, int] = {}
for r in yes_rows:
    p = tags[r]["reason"].split()[0].lower() if tags[r]["reason"] else "unspecified"
    patt_counts[p] = patt_counts.get(p, 0) + 1
print("YES by pattern:", patt_counts)

print()
print("YES rows with full feature dump:")
for r in sorted(yes_rows):
    if r not in features:
        continue
    f = features[r]
    print(
        f"  row {r:>2}  t={f['time_utc']} sess={f['sess']} {f['side']:<4} "
        f"range={f['range']:>5.2f} body={f['body_pct'] * 100:>3.0f}% wick={f['wick_pct'] * 100:>3.0f}% "
        f"R5={f['R5']:>4.2f}x V5={f['V5']:>4.2f}x flag={f['flag']:<5} ctx={f['ctx'] or '-':<5} "
        f"pattern={tags[r]['reason']}"
    )
