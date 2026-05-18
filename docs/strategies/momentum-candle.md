# Momentum-Candle Strategy

> Source: Indonesian masterclass video — *"Cara trading menggunakan momentum candle dari nol sampai mahir"* — https://www.youtube.com/watch?v=Utj8qRwNtgE
> Author claims ≥80% win rate on funded-account challenges using this technique.
> Default symbol: **XAUUSD**. Default timeframes: **M15** (preferred) or **M5** (faster).
>
> This document is the formal spec the `mt5_mvp.strategies.momentum_candle` detector and `scan_momentum_setups` MCP tool implement.

## 1. What is a momentum candle?

A candlestick that shows **strong directional movement** in a single period:

- **Body dominance** — body is 70–80% of total candle range (high − low).
- **Small wick on close side** — for a bullish momentum, almost no upper wick; bullish wick (low side) acceptable but small. Mirror for bearish.
- **Range expansion** — the candle's range is larger than recent surrounding candles.
- **Volume confirmation** — tick volume spikes vs. recent baseline (signals real buying/selling pressure rather than thin-liquidity drift).
- **Single direction** — open and close on opposite extremes; no chop within the bar's swing.

Visually: a long real body with tiny stubs at the close end. Big body, small or no wick on the side the close is at.

## 2. Concrete trigger thresholds (this MVP)

A candle at index `i` qualifies as a **momentum candle** when **all** the following hold:

| Rule | Formula | Default |
|---|---|---|
| Body dominance | `body / range >= MIN_BODY_PCT` | `0.70` |
| Close-side wick small | `close_side_wick / range <= MAX_CLOSE_WICK_PCT` | `0.10` |
| Range expansion | `range >= ATR_MULT × ATR(i, period=14)` | `1.0 × ATR` |
| Volume spike | `tick_volume[i] >= VOL_MULT × SMA(tick_volume, 20)[i]` | `1.5 ×` |
| Not the latest forming bar | `i < len(candles) - 1` | enforced |

Where:
- `body = abs(close − open)`
- `range = high − low` (must be > 0)
- `close_side_wick = high − close` for bullish, `close − low` for bearish.
- `ATR(i)` uses Wilder smoothing with period 14.
- `SMA(tick_volume, 20)` excludes the candle being evaluated.

Direction is `BUY` if `close > open`, `SELL` otherwise.

These thresholds are tunable via `scan_momentum_setups` parameters; the defaults match the author's "70–80% body" guidance plus the ATR/volume filters needed to keep noise out.

## 3. Three entry patterns

### 3.1 Breakout

**Context**: a tight consolidation (small bodies, narrow range) followed by a momentum candle that punches through the range.

**Detection signal**: average true range of the previous N candles (default N=5) is `<= 0.5 × ATR(14)`, and the momentum candle's close is beyond the prior N-bar range.

### 3.2 Pullback

**Context**: existing trend, price retraces to a recent swing low (BUY) or high (SELL), and a momentum candle forms there.

**Detection signal**: the momentum candle's low (BUY) or high (SELL) is within `0.382 × ATR` of a recent swing point computed over the prior 10 bars.

### 3.3 Trend continuation

**Context**: established trend, momentum candle prints in the trend direction with "empty space" on the chart (no recent candles overlapping the new range — i.e. fresh extension).

**Detection signal**: at least 5 of the prior 10 closes form a monotonic sequence in the momentum direction, **and** the momentum candle's close exceeds all closes in the prior 5 bars (BUY) / is below all of them (SELL).

If multiple patterns match, the detector picks the one with highest priority: **breakout > trend > pullback** (the order the video presents them and emphasises win rate).

## 4. Entry, SL, and TP — Fibonacci based

For a **BUY** momentum candle with `low = L`, `high = H`:

```
range = H − L
fib_236 = H − 0.236 × range          # 23.6% retracement entry
sl      = L − 0.10  × range          # below the low with breathing room
tp1     = H                          # the high (wick) — high-WR conservative target
tp2     = H + 0.27  × range          # 1.27 extension — aggressive target
```

For a **SELL** momentum candle (mirror):

```
range = H − L
fib_236 = L + 0.236 × range
sl      = H + 0.10  × range
tp1     = L
tp2     = L − 0.27  × range
```

### Entry mode

Two modes, both honoured by `Setup`:

| Mode | Description | Entry price |
|---|---|---|
| `next_open` | Place a market order on the **next bar's open** (post-trigger close). | `candles[i+1].open` if available, else `candles[i].close` (forming bar fallback). |
| `pullback_236` | Place a **limit order** at the 23.6% retracement and wait for fill. | `fib_236` |

`next_open` is the MVP default — easier to backtest, no waiting on fills.

The transcript notes "wider SL is better than tight". The `0.10 × range` cushion below the candle's low (above the high for SELL) is the implementation of that guidance.

### Risk:reward

- TP1 / |entry − SL|  ≈ 4–10R for a typical momentum candle (very high) — but only ~70-80% win rate at TP1 because price often reverses near the candle's extreme.
- TP2 / |entry − SL|  ≈ 5–15R, lower hit rate.

The MVP returns both; the Setup includes `rr_tp1` and `rr_tp2`.

## 5. Output schema

```python
@dataclass
class Setup:
    symbol: str
    timeframe: str
    direction: Literal["BUY", "SELL"]
    pattern: Literal["breakout", "pullback", "trend"]
    trigger_index: int             # index in the input candle list
    trigger_time: int              # epoch seconds
    candle_open: float
    candle_high: float
    candle_low: float
    candle_close: float
    body_pct: float
    range_atr_mult: float          # range / ATR(14)
    volume_ratio: float            # tick_volume / SMA20
    entry: float                   # depends on entry_mode
    sl: float
    tp1: float
    tp2: float
    rr_tp1: float
    rr_tp2: float
    confidence: float              # 0..1, see scoring below
    reason: str                    # one-line human explanation
```

### Confidence scoring (0..1)

```
score  = 0.30 × clip((body_pct      − 0.70) / 0.30, 0, 1)
       + 0.30 × clip((range_atr_mult − 1.0)  / 1.5,  0, 1)
       + 0.20 × clip((volume_ratio   − 1.5)  / 2.5,  0, 1)
       + 0.10 × (1.0 if pattern == "breakout" else 0.7 if pattern == "trend" else 0.5)
       + 0.10 × clip(1.0 − close_side_wick_pct / 0.10, 0, 1)
```

Bumped to 1.0 when all four metrics are at their max. Returns >= 0.50 are usable; >= 0.70 are strong. The detector returns all setups with `confidence >= MIN_CONFIDENCE` (default 0.50).

## 6. Filters & guardrails

- **Skip the latest forming bar** (its close is provisional). The detector evaluates indices `0..len-2`.
- **Skip bars with `range == 0`** — defensive.
- **Skip bars where ATR or SMA cannot be computed** (insufficient lookback).
- **Symbol-specific volume profile** — XAUUSD M15 typically has 5k–25k tick_volume. SMA20 baseline auto-adjusts.
- **No trade through major macro events** — out of scope for this detector. Caller should filter by economic calendar separately.

## 7. Anti-patterns (from the video)

- **FOMO entries without confirmation** — don't enter on a normal-sized candle just because price is moving.
- **Ignoring context** — a long-bodied candle in chop is not a momentum candle.
- **Tight stops** — counterproductive on momentum setups; the author recommends "give it room to breathe".
- **Multiple-timeframe spaghetti** — one timeframe is enough.

## 8. Out of scope for the MVP detector

- Real-time tick-level entries on the trigger bar's close (we use next-bar open or limit-order fill).
- Detection of "fake breakouts" (price returning to consolidation range after the breakout candle). Will add as a post-trade SL move in a future phase.
- Auto-execution. The detector returns Setups; placing orders is the caller's choice via `place_market_order`.
- Multi-symbol scanning. Single symbol per call; AI agent loops if needed.

## 9. Calling the detector

Once exposed as MCP:

```
scan_momentum_setups(symbol="XAUUSD", timeframe="M15", lookback=200,
                     min_body_pct=0.70, atr_mult=1.0, vol_mult=1.5,
                     entry_mode="next_open", min_confidence=0.50)
→ list[Setup]   (newest first)
```

Typical AI agent flow:

```
1. get_account                              → margin / equity check
2. scan_momentum_setups("XAUUSD", "M15")    → candidate setups
3. ...pick one, present to user...
4. place_market_order(symbol, side, vol, sl, tp)   (dry-run by default)
```

## 10. References

- Source video (Indonesian): https://www.youtube.com/watch?v=Utj8qRwNtgE
- Cached transcript: `cache/transcript-Utj8qRwNtgE.txt` (gitignored).
- Implementation: `src/mt5_mvp/strategies/momentum_candle.py`.
- Skill for AI activation: `.claude/skills/momentum-candle/SKILL.md`.
- Tests: `tests/test_momentum_candle.py`.
