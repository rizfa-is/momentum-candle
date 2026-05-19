"""Quick parser for eye-tag worksheet. Counts YES/NO and pattern breakdown."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("usage: python parse_eye_tags.py <path-to-worksheet.md>")
    sys.exit(1)

path = Path(sys.argv[1])
src = path.read_text(encoding="utf-8")

# Find the eye-tag block (after "# eye-tags below")
m = re.search(r"# eye-tags below.*?\n(.*?)(?:\n```|\Z)", src, re.S)
if not m:
    print("No eye-tag block found")
    sys.exit(1)

block = m.group(1)

# Match: <row#>  <HH:MM>  <YES|NO>  <reason ...>
line_re = re.compile(
    r"^\s*(\d{1,3})\s+(\d{2}:\d{2})\s+(YES|NO)(?:\s+(\S.*?))?\s*$",
    re.M | re.I,
)

tags = []
for g in line_re.findall(block):
    tags.append(
        {
            "row": int(g[0]),
            "time": g[1],
            "verdict": g[2].upper(),
            "reason": (g[3] or "").strip(),
        }
    )

yes = [t for t in tags if t["verdict"] == "YES"]
no = [t for t in tags if t["verdict"] == "NO"]

print(f"File: {path.name}")
print(f"Total tags parsed: {len(tags)}")
print(f"  YES: {len(yes)}")
print(f"  NO : {len(no)}")
print()

patt_counts: dict[str, int] = {}
for t in yes:
    p = t["reason"].split()[0].lower() if t["reason"] else "unspecified"
    patt_counts[p] = patt_counts.get(p, 0) + 1

if patt_counts:
    print("YES by pattern:", patt_counts)
    print()

if yes:
    print("YES rows:")
    for t in yes:
        print(f"  row {t['row']:>2}  ({t['time']})  {t['reason']}")
