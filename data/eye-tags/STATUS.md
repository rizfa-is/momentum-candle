# Eye-tag dataset status

Single source of truth for the M5 XAUUSD eye-tag dataset progress.
Updated whenever a worksheet's eye-tag block is parsed.

## Source data

- Cache: `C:\Users\DELL\.local\share\opencode\tool-output\tool_e3c60fb800018NefI01GMfrDQg`
- 1500 M5 bars total
- Pulled: 2026-05-18 ~21:35 UTC

## Per-day progress

| Day | File | Bars | Candidates | Top-50 | Tagged | YES | Last update |
|---|---|---:|---:|---:|---|---:|---|
| Tue 2026-05-12 | `2026-05-12-tue.md` | 276 | 101 | 50 | NO  | — | — |
| Wed 2026-05-13 | `2026-05-13-wed.md` | 276 |  98 | 50 | NO  | — | — |
| Thu 2026-05-14 | `2026-05-14-thu.md` | 276 | 103 | 50 | NO  | — | — |
| Fri 2026-05-15 | `2026-05-15-fri.md` | 276 | 110 | 50 | NO  | — | — |
| Mon 2026-05-18 | `2026-05-18-mon.md` | 248 |  96 | 50 | NO  | — | — |

## Aggregate

- Days tagged: **0 / 5**
- Total YES tags: **0**
- Total bars considered: 1,352
- Total top-50 candidates across all days: 250

## Eye-tag format reference

```
<row#>  YES  <pattern>     # continuation, breakout, reversal
<row#>  NO   <reason>      # optional reason
```

Bars not listed default to **skipped** (= no eye-tag, neither YES nor NO).

## Recommended tagging order

```
1. Fri 2026-05-15   154-pt range  (most candidates, freshest memory)
2. Tue 2026-05-12   135-pt range
3. Mon 2026-05-18   104-pt          (today, partial)
4. Thu 2026-05-14    74-pt
5. Wed 2026-05-13    57-pt          (saved for last — false-positive control)
```

## Update protocol

When the user says "tags ready" (or similar) for a worksheet:

1. Parse the `# eye-tags below` block in that day's file.
2. Count YES tags, NO tags, by-pattern breakdown.
3. Update the row in this file's per-day table.
4. Update aggregate counts.
5. Commit both the worksheet (with tags) and this STATUS.md together.
6. Once all 5 days hit `Tagged: YES`, run the correlation analysis and propose Phase A+B encoding.

## Resume point

```
Pending: Fri 2026-05-15 — eye-tag the top-50 candidates in TradingView.
Then continue in this order: Tue 12 → Mon 18 → Thu 14 → Wed 13.

DO NOT make any code changes to the strategy detector until all 5 days
are tagged and analysis is complete. The four-rule eye-model is provisional
until validated against the full dataset.
```
