"""Phase 6 backtest -- ICT/AMD portfolio (independent of v0.5.0).

Two new base signals:
  LSD  London Sweep, NY Displacement (operationalizes Accumulation-Manipulation-Distribution)
  SRR  Sweep-Rejection at major S/R (stop-hunt at obvious level)

Three optional confluences:
  F-SR  signal candle's extreme within 0.5 * ATR of any major level
  F-3P  3WS or 3BC pattern within last 5 bars matches signal direction
  F-PD  entry price in discount half (BUY) / premium half (SELL) of prior 4H range

14 variants generated; pullback_236 entry mode locked (RR comparable to v0.5.0).

Pre-committed decision rules (variant passes if ALL hold):
  1. Min trades over 12 months: >= 50  (>=4/month average, deployable cadence)
  2. Aggregate PF:               > 1.40
  3. Losing months:              <= 3 / 12
  4. Mean RR per win:            >= 0.5

Simulation engine matches multi_month_backtest (worst-case intra-bar ordering,
60-bar timeout, 10-bar pullback fill window). Signal SL/TP convention is the
fib-based one used everywhere else for cross-phase comparability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\CODING\Trading\mt5-mcp\momentum-candle")
CACHE = ROOT / "cache"
OUT = ROOT / "data" / "backtests"

POINT = 0.01
SIM_HORIZON_BARS = 60
PULLBACK_FILL_BARS = 10

# AMD spec
ASIA_HOUR_START = 0
ASIA_HOUR_END = 7        # exclusive: bars 00..06 UTC
LONDON_HOUR_START = 7
LONDON_HOUR_END = 12     # exclusive: bars 07..11 UTC
NY_HOUR_START = 12
NY_HOUR_END = 22         # exclusive: bars 12..21 UTC

# Displacement (looser than v0.5.0; sweep direction does the work)
DISPLACEMENT_MIN_BODY_PCT = 0.60
DISPLACEMENT_MIN_RANGE_ATR = 1.0

# SRR
SRR_MIN_WICK_TO_BODY = 0.50  # rejection wick beyond level >= 0.5 * body
SR_PIVOT_LEFT = 10
SR_PIVOT_RIGHT = 10
SR_LOOKBACK = 300            # bars of history to find pivots
SR_MIN_TOUCHES = 2           # pivots clustered to count as level
SR_CLUSTER_ATR_MULT = 0.5    # cluster radius
SR_TOUCH_FRESH_BARS = 200    # level "active" if last touched within this many bars

# Confluences
FSR_PROXIMITY_ATR_MULT = 0.5
F3P_LOOKBACK_BARS = 5
FPD_LOOKBACK_BARS = 48       # 4h on M5

# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass
class Signal:
    month: str
    idx: int                  # signal candle index in month's bar array
    time_utc: str
    side: str                 # 'BUY' or 'SELL'
    source: str               # 'LSD' or 'SRR'
    candle_low: float
    candle_high: float
    candle_range: float
    atr: float
    extras: dict = field(default_factory=dict)


@dataclass
class TradeResult:
    outcome: str              # 'TP2', 'SL', 'timeout', 'not-filled', 'no-next-bar'
    filled: bool
    entry_price: float | None
    sl: float | None
    tp2: float | None
    rr_win: float | None      # only set on TP2


# --------------------------------------------------------------------------
# Time / session helpers
# --------------------------------------------------------------------------


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def session_label(h: int) -> str:
    if ASIA_HOUR_START <= h < ASIA_HOUR_END:
        return "Asia"
    if LONDON_HOUR_START <= h < LONDON_HOUR_END:
        return "London"
    if NY_HOUR_START <= h < NY_HOUR_END:
        return "NY"
    return "Off"


# --------------------------------------------------------------------------
# Market math
# --------------------------------------------------------------------------


def compute_atr14(candles: list[dict]) -> list[float]:
    """ATR(14) using simple moving average of true range."""
    n = len(candles)
    atr = [0.0] * n
    if n < 16:
        return atr
    tr = [0.0] * n
    for i in range(1, n):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    s = sum(tr[1:15])
    atr[15] = s / 14
    for i in range(16, n):
        s = s - tr[i - 14] + tr[i - 1]
        atr[i] = s / 14
    return atr


# --------------------------------------------------------------------------
# Swing pivots + S/R clustering
# --------------------------------------------------------------------------


def precompute_pivots(candles: list[dict]) -> list[tuple[str, float] | None]:
    """For each bar, mark if it is a pivot high, pivot low, both, or none.
    A pivot is confirmed pivot_right bars after it forms.
    """
    n = len(candles)
    pivots: list[tuple[str, float] | None] = [None] * n
    for i in range(SR_PIVOT_LEFT, n - SR_PIVOT_RIGHT):
        h = candles[i]["high"]
        l = candles[i]["low"]
        is_ph = True
        is_pl = True
        for j in range(i - SR_PIVOT_LEFT, i + SR_PIVOT_RIGHT + 1):
            if j == i:
                continue
            if candles[j]["high"] > h:
                is_ph = False
            if candles[j]["low"] < l:
                is_pl = False
            if not is_ph and not is_pl:
                break
        if is_ph and is_pl:
            pivots[i] = ("both", h)  # collapse: store high; lows handled via second pass
        elif is_ph:
            pivots[i] = ("high", h)
        elif is_pl:
            pivots[i] = ("low", l)
    return pivots


def cluster_prices(prices: list[float], tolerance: float, min_touches: int) -> list[float]:
    if not prices or tolerance <= 0:
        return []
    sp = sorted(prices)
    clusters: list[float] = []
    current = [sp[0]]
    for p in sp[1:]:
        if p - current[-1] <= tolerance:
            current.append(p)
        else:
            if len(current) >= min_touches:
                clusters.append(sum(current) / len(current))
            current = [p]
    if len(current) >= min_touches:
        clusters.append(sum(current) / len(current))
    return clusters


def get_active_sr(
    pivots: list[tuple[str, float] | None],
    candles: list[dict],
    idx: int,
    atr_value: float,
) -> tuple[list[float], list[float]]:
    """Active resistance (above price) and support (below price) clusters at bar idx."""
    if atr_value <= 0:
        return [], []
    start = max(0, idx - SR_LOOKBACK)
    confirmed_end = idx - SR_PIVOT_RIGHT
    highs: list[float] = []
    lows: list[float] = []
    for i in range(start, confirmed_end):
        p = pivots[i]
        if p is None:
            continue
        if p[0] == "high":
            highs.append(p[1])
        elif p[0] == "low":
            lows.append(p[1])
        elif p[0] == "both":
            highs.append(p[1])
            lows.append(p[1])
    tol = SR_CLUSTER_ATR_MULT * atr_value
    return cluster_prices(highs, tol, SR_MIN_TOUCHES), cluster_prices(lows, tol, SR_MIN_TOUCHES)


# --------------------------------------------------------------------------
# AMD: Asian range, London sweep, NY displacement
# --------------------------------------------------------------------------


def group_by_day(candles: list[dict]) -> dict[str, list[int]]:
    """Return {YYYY-MM-DD: [bar indices in chronological order]}."""
    by_day: dict[str, list[int]] = {}
    for i, c in enumerate(candles):
        d = utc(c["time"]).date().isoformat()
        by_day.setdefault(d, []).append(i)
    return by_day


def detect_asian_range(candles: list[dict], day_indices: list[int]) -> tuple[float, float] | None:
    asia_idxs = [i for i in day_indices if utc(candles[i]["time"]).hour < ASIA_HOUR_END]
    if not asia_idxs:
        return None
    lo = min(candles[i]["low"] for i in asia_idxs)
    hi = max(candles[i]["high"] for i in asia_idxs)
    return lo, hi


def detect_london_sweep(
    candles: list[dict],
    day_indices: list[int],
    asia_low: float,
    asia_high: float,
) -> tuple[str, int] | None:
    """Return (side, bar_idx) where side='BSL' or 'SSL'. First sweep wins."""
    london_idxs = [
        i for i in day_indices
        if LONDON_HOUR_START <= utc(candles[i]["time"]).hour < LONDON_HOUR_END
    ]
    for i in london_idxs:
        c = candles[i]
        if c["high"] > asia_high and c["close"] < asia_high and c["close"] > asia_low:
            return ("BSL", i)
        if c["low"] < asia_low and c["close"] > asia_low and c["close"] < asia_high:
            return ("SSL", i)
    return None


def detect_ny_displacement(
    candles: list[dict],
    day_indices: list[int],
    sweep_side: str,
    sweep_idx: int,
    atr: list[float],
) -> int | None:
    """First displacement candle in NY in opposite direction. Returns bar idx or None."""
    expected = "SELL" if sweep_side == "BSL" else "BUY"
    ny_idxs = [
        i for i in day_indices
        if i > sweep_idx and NY_HOUR_START <= utc(candles[i]["time"]).hour < NY_HOUR_END
    ]
    for i in ny_idxs:
        c = candles[i]
        rng = c["high"] - c["low"]
        if rng <= 0:
            continue
        body = abs(c["close"] - c["open"])
        body_pct = body / rng
        if body_pct < DISPLACEMENT_MIN_BODY_PCT:
            continue
        if atr[i] <= 0 or rng < DISPLACEMENT_MIN_RANGE_ATR * atr[i]:
            continue
        side = "BUY" if c["close"] > c["open"] else "SELL" if c["close"] < c["open"] else ""
        if side != expected:
            continue
        return i
    return None


# --------------------------------------------------------------------------
# SRR: sweep-rejection at major S/R
# --------------------------------------------------------------------------


def detect_srr(
    candles: list[dict],
    idx: int,
    res_levels: list[float],
    sup_levels: list[float],
) -> tuple[str, float] | None:
    """Detect rejection at level. Returns (side, level) or None."""
    if idx < 1:
        return None
    c = candles[idx]
    pc = candles[idx - 1]["close"]
    rng = c["high"] - c["low"]
    body = abs(c["close"] - c["open"])
    if rng <= 0 or body <= 0:
        return None

    # Resistance rejection -> SELL
    for r in res_levels:
        if r <= pc:
            continue
        if c["high"] >= r and c["close"] < r and c["open"] < r:
            wick_beyond = c["high"] - max(c["open"], c["close"])
            if wick_beyond >= SRR_MIN_WICK_TO_BODY * body:
                return ("SELL", r)

    # Support rejection -> BUY
    for s in sup_levels:
        if s >= pc:
            continue
        if c["low"] <= s and c["close"] > s and c["open"] > s:
            wick_beyond = min(c["open"], c["close"]) - c["low"]
            if wick_beyond >= SRR_MIN_WICK_TO_BODY * body:
                return ("BUY", s)
    return None


# --------------------------------------------------------------------------
# Confluences
# --------------------------------------------------------------------------


def confl_fsr(
    candles: list[dict],
    sig: Signal,
    res_levels: list[float],
    sup_levels: list[float],
) -> bool:
    if sig.atr <= 0:
        return False
    tol = FSR_PROXIMITY_ATR_MULT * sig.atr
    if sig.side == "BUY":
        # buy candle's low should be near a support level
        return any(abs(sig.candle_low - s) <= tol for s in sup_levels)
    return any(abs(sig.candle_high - r) <= tol for r in res_levels)


def detect_3ws(candles: list[dict], idx: int) -> bool:
    if idx < 2:
        return False
    a, b, c = candles[idx - 2], candles[idx - 1], candles[idx]
    if not (a["close"] > a["open"] and b["close"] > b["open"] and c["close"] > c["open"]):
        return False
    if not (b["close"] > a["close"] and c["close"] > b["close"]):
        return False
    if not (b["open"] >= a["open"] and b["open"] <= a["close"]):
        return False
    if not (c["open"] >= b["open"] and c["open"] <= b["close"]):
        return False
    return True


def detect_3bc(candles: list[dict], idx: int) -> bool:
    if idx < 2:
        return False
    a, b, c = candles[idx - 2], candles[idx - 1], candles[idx]
    if not (a["close"] < a["open"] and b["close"] < b["open"] and c["close"] < c["open"]):
        return False
    if not (b["close"] < a["close"] and c["close"] < b["close"]):
        return False
    if not (b["open"] <= a["open"] and b["open"] >= a["close"]):
        return False
    if not (c["open"] <= b["open"] and c["open"] >= b["close"]):
        return False
    return True


def confl_f3p(candles: list[dict], sig: Signal) -> bool:
    """3WS in last 5 bars for BUY, 3BC for SELL."""
    detector = detect_3ws if sig.side == "BUY" else detect_3bc
    for k in range(F3P_LOOKBACK_BARS):
        i = sig.idx - k
        if i < 2:
            break
        if detector(candles, i):
            return True
    return False


def confl_fpd(candles: list[dict], sig: Signal) -> bool:
    """Entry price in discount half (BUY) or premium half (SELL) of prior 4H range."""
    start = sig.idx - FPD_LOOKBACK_BARS
    if start < 0:
        return False
    rng_high = max(c["high"] for c in candles[start:sig.idx])
    rng_low = min(c["low"] for c in candles[start:sig.idx])
    if rng_high <= rng_low:
        return False
    mid = (rng_high + rng_low) / 2
    # Entry price for pullback_236
    if sig.side == "BUY":
        entry = sig.candle_high - 0.236 * sig.candle_range
        return entry < mid
    entry = sig.candle_low + 0.236 * sig.candle_range
    return entry > mid


# --------------------------------------------------------------------------
# Simulation (pullback_236 only, same convention as multi_month)
# --------------------------------------------------------------------------


def simulate_pullback(candles: list[dict], sig: Signal) -> TradeResult:
    L = sig.candle_low
    H = sig.candle_high
    rng = sig.candle_range

    if sig.side == "BUY":
        sl = L - 0.10 * rng
        tp2 = H + 0.27 * rng
        pullback_limit = H - 0.236 * rng
    else:
        sl = H + 0.10 * rng
        tp2 = L - 0.27 * rng
        pullback_limit = L + 0.236 * rng

    if sig.idx + 1 >= len(candles):
        return TradeResult("no-next-bar", False, None, sl, tp2, None)

    entry_idx = None
    entry_price = None
    for k in range(PULLBACK_FILL_BARS):
        idx = sig.idx + 1 + k
        if idx >= len(candles):
            break
        bar = candles[idx]
        if sig.side == "BUY" and bar["low"] <= pullback_limit:
            entry_price = pullback_limit
            entry_idx = idx
            break
        if sig.side == "SELL" and bar["high"] >= pullback_limit:
            entry_price = pullback_limit
            entry_idx = idx
            break

    if entry_price is None or entry_idx is None:
        return TradeResult("not-filled", False, None, sl, tp2, None)

    outcome = "timeout"
    for k in range(SIM_HORIZON_BARS):
        idx = entry_idx + k
        if idx >= len(candles):
            outcome = "ran-out-of-data"
            break
        bar = candles[idx]
        bh, bl = bar["high"], bar["low"]
        if sig.side == "BUY":
            sl_hit = bl <= sl
            tp2_hit = bh >= tp2
        else:
            sl_hit = bh >= sl
            tp2_hit = bl <= tp2
        if sl_hit:  # worst-case intra-bar ordering
            outcome = "SL"
            break
        if tp2_hit:
            outcome = "TP2"
            break

    rr_win = None
    if outcome == "TP2":
        risk = abs(entry_price - sl)
        reward = abs(tp2 - entry_price)
        if risk > 0:
            rr_win = reward / risk

    return TradeResult(outcome, True, entry_price, sl, tp2, rr_win)


# --------------------------------------------------------------------------
# Signal generation
# --------------------------------------------------------------------------


def make_signal(
    month: str,
    candles: list[dict],
    idx: int,
    side: str,
    source: str,
    atr: list[float],
    extras: dict | None = None,
) -> Signal:
    c = candles[idx]
    rng = c["high"] - c["low"]
    return Signal(
        month=month,
        idx=idx,
        time_utc=utc(c["time"]).isoformat(),
        side=side,
        source=source,
        candle_low=c["low"],
        candle_high=c["high"],
        candle_range=rng,
        atr=atr[idx] if idx < len(atr) else 0.0,
        extras=extras or {},
    )


def generate_lsd_signals(
    month: str, candles: list[dict], atr: list[float]
) -> list[Signal]:
    signals: list[Signal] = []
    by_day = group_by_day(candles)
    for date in sorted(by_day.keys()):
        day_indices = by_day[date]
        ar = detect_asian_range(candles, day_indices)
        if not ar:
            continue
        asia_low, asia_high = ar
        sweep = detect_london_sweep(candles, day_indices, asia_low, asia_high)
        if not sweep:
            continue
        sweep_side, sweep_idx = sweep
        disp_idx = detect_ny_displacement(candles, day_indices, sweep_side, sweep_idx, atr)
        if disp_idx is None:
            continue
        side = "SELL" if sweep_side == "BSL" else "BUY"
        signals.append(
            make_signal(
                month, candles, disp_idx, side, "LSD", atr,
                extras={"sweep_side": sweep_side, "sweep_idx": sweep_idx,
                        "asia_low": round(asia_low, 2), "asia_high": round(asia_high, 2)},
            )
        )
    return signals


def generate_srr_signals(
    month: str,
    candles: list[dict],
    atr: list[float],
    pivots: list[tuple[str, float] | None],
) -> list[Signal]:
    signals: list[Signal] = []
    for idx in range(SR_LOOKBACK + SR_PIVOT_RIGHT, len(candles)):
        # Skip London (manipulation window)
        h = utc(candles[idx]["time"]).hour
        if LONDON_HOUR_START <= h < LONDON_HOUR_END:
            continue
        if atr[idx] <= 0:
            continue
        res_levels, sup_levels = get_active_sr(pivots, candles, idx, atr[idx])
        if not res_levels and not sup_levels:
            continue
        det = detect_srr(candles, idx, res_levels, sup_levels)
        if det is None:
            continue
        side, level = det
        signals.append(
            make_signal(
                month, candles, idx, side, "SRR", atr,
                extras={"level": round(level, 2)},
            )
        )
    return signals


# --------------------------------------------------------------------------
# Variants
# --------------------------------------------------------------------------


VARIANTS: list[dict[str, Any]] = [
    # LSD-based
    {"id": "V1",  "source": "LSD", "confluences": []},
    {"id": "V2",  "source": "LSD", "confluences": ["FSR"]},
    {"id": "V3",  "source": "LSD", "confluences": ["F3P"]},
    {"id": "V4",  "source": "LSD", "confluences": ["FPD"]},
    {"id": "V5",  "source": "LSD", "confluences": ["FSR", "F3P"]},
    {"id": "V6",  "source": "LSD", "confluences": ["FSR", "FPD"]},
    {"id": "V7",  "source": "LSD", "confluences": ["F3P", "FPD"]},
    {"id": "V8",  "source": "LSD", "confluences": ["FSR", "F3P", "FPD"]},
    # SRR-based
    {"id": "V9",  "source": "SRR", "confluences": []},
    {"id": "V10", "source": "SRR", "confluences": ["F3P"]},
    {"id": "V11", "source": "SRR", "confluences": ["FPD"]},
    {"id": "V12", "source": "SRR", "confluences": ["F3P", "FPD"]},
    # Combined
    {"id": "V13", "source": "OR",  "confluences": []},
    {"id": "V14", "source": "AND", "confluences": []},
]


def filter_signal(
    sig: Signal,
    candles: list[dict],
    pivots: list[tuple[str, float] | None],
    confluences: list[str],
) -> bool:
    if "FSR" in confluences:
        if sig.atr <= 0:
            return False
        res, sup = get_active_sr(pivots, candles, sig.idx, sig.atr)
        if not confl_fsr(candles, sig, res, sup):
            return False
    if "F3P" in confluences:
        if not confl_f3p(candles, sig):
            return False
    if "FPD" in confluences:
        if not confl_fpd(candles, sig):
            return False
    return True


def signals_for_variant(
    variant: dict,
    lsd: list[Signal],
    srr: list[Signal],
    candles: list[dict],
    pivots: list[tuple[str, float] | None],
) -> list[Signal]:
    confl = variant["confluences"]
    if variant["source"] == "LSD":
        return [s for s in lsd if filter_signal(s, candles, pivots, confl)]
    if variant["source"] == "SRR":
        return [s for s in srr if filter_signal(s, candles, pivots, confl)]
    if variant["source"] == "OR":
        # Pool both, dedupe by (idx, side); keep LSD if both
        seen = set()
        out: list[Signal] = []
        for s in lsd + srr:
            key = (s.idx, s.side)
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        return sorted(out, key=lambda s: s.idx)
    if variant["source"] == "AND":
        # Same-bar AND: both detectors fire on same idx with same side
        srr_keys = {(s.idx, s.side) for s in srr}
        return [s for s in lsd if (s.idx, s.side) in srr_keys]
    return []


# --------------------------------------------------------------------------
# Per-variant runner
# --------------------------------------------------------------------------


@dataclass
class MonthMetrics:
    month: str
    n_signals: int = 0
    n_filled: int = 0
    n_tp2: int = 0
    n_sl: int = 0
    n_to: int = 0
    n_unfilled: int = 0
    sum_rr: float = 0.0


def run_variant(
    variant: dict,
    months_data: dict[str, dict],
) -> dict[str, MonthMetrics]:
    per_month: dict[str, MonthMetrics] = {}
    for month, data in months_data.items():
        candles = data["candles"]
        pivots = data["pivots"]
        sigs = signals_for_variant(variant, data["lsd"], data["srr"], candles, pivots)
        m = MonthMetrics(month=month, n_signals=len(sigs))
        for sig in sigs:
            res = simulate_pullback(candles, sig)
            if not res.filled:
                m.n_unfilled += 1
                continue
            m.n_filled += 1
            if res.outcome == "TP2":
                m.n_tp2 += 1
                if res.rr_win is not None:
                    m.sum_rr += res.rr_win
            elif res.outcome == "SL":
                m.n_sl += 1
            else:
                m.n_to += 1
        per_month[month] = m
    return per_month


def aggregate(per_month: dict[str, MonthMetrics]) -> dict[str, Any]:
    months = list(per_month.values())
    n_sig = sum(m.n_signals for m in months)
    n_fill = sum(m.n_filled for m in months)
    n_tp2 = sum(m.n_tp2 for m in months)
    n_sl = sum(m.n_sl for m in months)
    n_to = sum(m.n_to for m in months)
    sum_rr = sum(m.sum_rr for m in months)

    losing_months = 0
    for m in months:
        if m.n_filled == 0:
            continue
        net = m.sum_rr - m.n_sl
        if net < 0:
            losing_months += 1

    pf = sum_rr / n_sl if n_sl else (float("inf") if n_tp2 else 0.0)
    wr = n_tp2 / n_fill if n_fill else 0.0
    mean_rr = sum_rr / n_tp2 if n_tp2 else 0.0
    net_R = sum_rr - n_sl
    per_trade = net_R / n_fill if n_fill else 0.0
    return {
        "n_signals": n_sig,
        "n_filled": n_fill,
        "n_tp2": n_tp2,
        "n_sl": n_sl,
        "n_timeout": n_to,
        "wr": wr,
        "mean_rr": mean_rr,
        "net_R": net_R,
        "per_trade_R": per_trade,
        "pf": pf,
        "losing_months": losing_months,
        "trading_months": sum(1 for m in months if m.n_filled > 0),
    }


# --------------------------------------------------------------------------
# Pre-committed decision rules
# --------------------------------------------------------------------------


def apply_rules(agg: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    ok = True
    if agg["n_filled"] < 50:
        ok = False
        reasons.append(f"n_filled={agg['n_filled']} < 50")
    if agg["pf"] <= 1.40:
        ok = False
        reasons.append(f"PF={agg['pf']:.2f} <= 1.40")
    if agg["losing_months"] > 3:
        ok = False
        reasons.append(f"losing_months={agg['losing_months']} > 3")
    if agg["mean_rr"] < 0.5:
        ok = False
        reasons.append(f"mean_rr={agg['mean_rr']:.3f} < 0.5")
    return ok, reasons


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def fmt_pf(x: float) -> str:
    if x == float("inf"):
        return "inf"
    return f"{x:.2f}"


def write_report(
    results: dict[str, dict],
    per_month_results: dict[str, dict[str, MonthMetrics]],
    out_md: Path,
) -> None:
    md: list[str] = []
    md.append("# Phase 6 backtest -- ICT/AMD portfolio (independent of v0.5.0)\n\n")
    md.append("Two new base signals (LSD, SRR), three optional confluences (F-SR, F-3P, F-PD),\n")
    md.append("14 variants. Pullback_236 entry mode locked. Same simulation engine as multi_month.\n\n")
    md.append("Pre-committed decision rules: n>=50 trades, PF>1.40, losing_months<=3/12, meanRR>=0.5\n\n")

    md.append("## Pooled aggregate (12 months: 2025-06 to 2026-05)\n\n")
    md.append("```\n")
    md.append(
        f"{'V':<4}  {'src':<4}  {'confl':<14}  "
        f"{'sigs':>5}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  "
        f"{'WR':>5}  {'meanRR':>7}  {'netR':>7}  {'PF':>6}  {'losM':>5}  {'verdict':<12}\n"
    )
    md.append("-" * 105 + "\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, _ = apply_rules(agg)
        confl = "+".join(v["confluences"]) if v["confluences"] else "-"
        md.append(
            f"{v['id']:<4}  {v['source']:<4}  {confl:<14}  "
            f"{agg['n_signals']:>5}  {agg['n_filled']:>5}  "
            f"{agg['n_tp2']:>4}  {agg['n_sl']:>4}  "
            f"{agg['wr'] * 100:>4.1f}%  {agg['mean_rr']:>6.3f}  "
            f"{agg['net_R']:>+6.2f}R  {fmt_pf(agg['pf']):>6}  "
            f"{agg['losing_months']:>3}/{agg['trading_months']:<2}  "
            f"{'PASS' if ok else 'REJECT':<12}\n"
        )
    md.append("```\n\n")

    md.append("## Per-variant detail\n\n")
    for v in VARIANTS:
        agg = results[v["id"]]
        ok, reasons = apply_rules(agg)
        md.append(f"### {v['id']} -- source={v['source']}, confluences={v['confluences']}\n\n")
        md.append("```\n")
        md.append(f"{'month':<10}  {'sigs':>5}  {'fill':>5}  {'TP2':>4}  {'SL':>4}  {'WR':>5}  {'netR':>7}  {'PF':>6}\n")
        for month, m in per_month_results[v["id"]].items():
            n_pos_R = m.sum_rr
            n_neg_R = float(m.n_sl)
            net = n_pos_R - n_neg_R
            wr = m.n_tp2 / m.n_filled if m.n_filled else 0.0
            pf = n_pos_R / n_neg_R if n_neg_R else (float("inf") if m.n_tp2 else 0.0)
            md.append(
                f"{month:<10}  {m.n_signals:>5}  {m.n_filled:>5}  "
                f"{m.n_tp2:>4}  {m.n_sl:>4}  {wr * 100:>4.1f}%  "
                f"{net:>+6.2f}R  {fmt_pf(pf):>6}\n"
            )
        md.append(f"\nVERDICT: {'PASS' if ok else 'REJECT'}")
        if reasons:
            md.append("  -- " + "; ".join(reasons))
        md.append("\n```\n\n")

    out_md.write_text("".join(md), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    months = sorted(p.stem.replace("-m5", "") for p in CACHE.glob("*-m5.json"))
    print(f"Loading {len(months)} months: {months[0]} -> {months[-1]}")

    months_data: dict[str, dict] = {}
    for slug in months:
        path = CACHE / f"{slug}-m5.json"
        candles = json.loads(path.read_text(encoding="utf-8"))
        candles.sort(key=lambda b: b["time"])
        atr = compute_atr14(candles)
        pivots = precompute_pivots(candles)
        lsd = generate_lsd_signals(slug, candles, atr)
        srr = generate_srr_signals(slug, candles, atr, pivots)
        months_data[slug] = {
            "candles": candles, "atr": atr, "pivots": pivots,
            "lsd": lsd, "srr": srr,
        }
        print(f"  {slug}: {len(candles)} bars, LSD={len(lsd)}, SRR={len(srr)}")

    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    per_month_results: dict[str, dict[str, MonthMetrics]] = {}

    print("\nRunning 14 variants...")
    for v in VARIANTS:
        per_month = run_variant(v, months_data)
        agg = aggregate(per_month)
        results[v["id"]] = agg
        per_month_results[v["id"]] = per_month
        ok, reasons = apply_rules(agg)
        confl = "+".join(v["confluences"]) if v["confluences"] else "-"
        print(
            f"  {v['id']:<4} {v['source']:<4} {confl:<14} "
            f"n={agg['n_filled']:>4}  WR={agg['wr'] * 100:>4.1f}%  "
            f"PF={fmt_pf(agg['pf']):>5}  netR={agg['net_R']:>+6.2f}  "
            f"losM={agg['losing_months']}/{agg['trading_months']}  "
            f"{'PASS' if ok else 'REJECT'}"
        )

    json_path = OUT / "phase6-results.json"
    serializable = {
        "aggregate": results,
        "per_month": {
            vid: {month: m.__dict__ for month, m in pm.items()}
            for vid, pm in per_month_results.items()
        },
    }
    json_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(f"\nSaved raw results to {json_path}")

    md_path = OUT / "phase6-report.md"
    write_report(results, per_month_results, md_path)
    print(f"Saved report to {md_path}")


if __name__ == "__main__":
    main()
