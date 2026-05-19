# Session notes — momentum-candle project

Living checkpoint. Read this at the start of any new session before deriving
anything from scratch.

## Current state — 2026-05-19 (DATASET WRAPPED)

### Tags & versions on origin/main

- `v0.2.0-python-mvp` — Python MCP MVP (8 tools, 16 tests passing)
- `bb8eee5` — MQL5 indicators compile clean (Video + Proxy + Backtest EA)
- `53c3786` — MomentumCandle_Visualizer indicator + docs
- `868dd23` — five eye-tag worksheets generated (250 candidates)
- `f16e421` — opencode auto-load + STATUS.md tracker
- `7d07c0b` — Fri 2026-05-15 tagged (6 YES / 44 NO)
- `73e552c` — Thu 2026-05-14 tagged (2 YES / 48 NO) — reversal exception confirmed
- `130b144` — Mon 2026-05-18 tagged (8 YES / 42 NO) — model converged

### Dataset wrap

3 of 5 days tagged. Tue 12 + Wed 13 deferred. Model deemed sufficient on
**16 YES / 134 NO** to encode into indicators.

| Day | Range pts | YES | Notes |
|---|---:|---:|---|
| Thu 2026-05-14 | 74 | 2 | both Asian-session reversals (weak-body type) |
| Fri 2026-05-15 | 154 | 6 | 3 Asia, 1 London, 2 NY; 3 breakouts, 2 reversals, 1 cont |
| Mon 2026-05-18 | 104 | 8 | richest day; collapse + NY rally; first non-size NO |

### Final eye-model (after 3 days of empirical tagging)

```python
def is_momentum_candle(bar, prior_bars):
    # Hard size floor — calibrated empirically on M5 XAUUSD
    if bar.range < 10.0:
        return False

    # Off-window reject (only safely droppable hour: 22-23 UTC)
    if 22 <= bar.utc_hour < 23:
        return False

    if has_reversal_context(bar, prior_bars):
        # Hammer / shooting-star or strong-body reversal
        return bar.body_pct >= 0.50 and bar.wick_pct <= 0.37
    else:
        # Continuation / breakout
        return bar.body_pct >= 0.75 and bar.wick_pct <= 0.15
        # User addition 2026-05-19: also enforce far-side (away) wick <= 5%
        # — applies to ALL three indicators via InpMaxFarWickPct=0.05.

def has_reversal_context(bar, prior_bars):
    return engulfs_prior_bar(bar, prior_bars[-1]) \
        or near_swing_extreme(bar, prior_bars[-20:])
```

This model passes ALL 16 YES and rejects ALL 134 NO across the 3 tagged
days. It's the encoded expression of the user's eye.

### What was dropped from the original 4-rule hypothesis

| Original idea | Verdict |
|---|---|
| 20-pt absolute size floor | DROPPED → 10 pts (with reversal context) |
| Volume V5 ≥ 1.5× | DROPPED — V5 mean YES 1.27× vs NO 1.16× (no signal) |
| Round-number proximity (R) | DROPPED — negative correlation |
| Velocity-flip (V) | DROPPED — negative correlation (1.7× more in NO) |
| Consolidation tag (C) | DROPPED — weak negative |
| Swing-extreme (S) | MARGINAL — kept inside reversal_context |
| Engulfing (E) | KEPT — primary reversal context signal |
| Trend-monotonic (T) | KEPT — 1.6× lift, primary continuation context |
| Session filter | RELAXED — only 22-23 UTC is hard reject |

### New input across all three indicators (2026-05-19)

`InpMaxFarWickPct = 0.05` — far-side (away) wick must be ≤ 5% of range, in
addition to existing close-side wick filter. User feedback: "wick should be
below 5%, both lower or higher". Applied to MomentumCandle_Video, _Proxy,
_Visualizer (the visualizer's HUD shows pass/fail on this too).

### Stats from current algo against the dataset

- 1,352 total bars across 5 days (3 tagged)
- 250 candidates examined (top-50 per day × 5 days)
- 16 YES, 134 NO from user
- Original algo (body≥70 + wick≤10 + R5≥1.5 + V5≥1.5): only 5 of 1,352 pass
  → eye-vs-algo overlap was just 1 bar across 3 days

## Workflow rules

- **uv path on Windows:**
  `C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`
- **MetaEditor compile path:** `C:\Program Files\MetaTrader\MetaEditor64.exe`
- **MT5 terminal path:** `C:\Program Files\MetaTrader\terminal64.exe`
- **MT5 data folder:**
  `C:\Users\DELL\AppData\Roaming\MetaQuotes\Terminal\F762D69EEEA9B4430D7F17C82167C844`
- **5-day cache:** `C:\Users\DELL\.local\share\opencode\tool-output\tool_e3c60fb800018NefI01GMfrDQg`

## Composite score formula (used in worksheets)

```
score = body_pct * 0.4
      + min(R5/3, 1.0) * 0.3
      + min(V5/3, 1.0) * 0.2
      + min(range/30, 1.0) * 0.1
```

## Resume point

**Dataset wrapped.** Next focus is whichever the user picks:

1. **Encode the eye-model into MQL5/Python** — bump to `v0.3.0-eye-aligned`.
   Translate the final model above into MomentumCandle_Eye.mq5 +
   `mt5_mvp.strategies.eye_model.py`. Side-by-side with Video and Proxy.

2. **Continue eye-tagging Tue 12 + Wed 13** — adds Tue (high-vol) and Wed
   (quiet day, false-positive control). Strengthens model statistics from
   16 YES to ~25 YES.

3. **Apply far-wick filter live** — already done 2026-05-19 across the
   three indicators (Video, Proxy, Visualizer). Recompile next time MT5
   refreshes.

User indicated the dataset is "enough" — option 1 is the natural next step.
