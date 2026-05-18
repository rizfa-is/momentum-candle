//+------------------------------------------------------------------+
//|                                       MomentumCandleCommon.mqh   |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Shared helpers for the two momentum-candle indicators:           |
//|   MomentumCandle_Video.mq5  (faithful to source video)           |
//|   MomentumCandle_Proxy.mq5  (ATR/SMA proxy, my variant)          |
//|                                                                  |
//| The candle logic must match Python `mt5_mvp.strategies.momentum_ |
//| candle` so we can compare both implementations against the same  |
//| MT5 historical data.                                             |
//+------------------------------------------------------------------+

#property strict

#ifndef MOMENTUM_CANDLE_COMMON_MQH
#define MOMENTUM_CANDLE_COMMON_MQH

//--- pattern enum ---------------------------------------------------
enum MC_Pattern
  {
   MC_PATTERN_NONE      = 0,
   MC_PATTERN_BREAKOUT  = 1,  // tight consolidation broken
   MC_PATTERN_TREND     = 2,  // monotonic continuation
   MC_PATTERN_PULLBACK  = 3,  // retest of recent swing
  };

enum MC_Direction
  {
   MC_DIR_NONE = 0,
   MC_DIR_BUY  = 1,
   MC_DIR_SELL = -1,
  };

//--- result struct -------------------------------------------------
struct MC_Setup
  {
   datetime    trigger_time;
   int         shift;            // index in the chart (newest=0)
   MC_Direction direction;
   MC_Pattern  pattern;
   double      candle_open;
   double      candle_high;
   double      candle_low;
   double      candle_close;
   double      body_pct;
   double      range_ratio;      // range / baseline (ATR or local-mean range)
   double      volume_ratio;     // tick_volume / baseline
   double      close_wick_pct;
   double      entry;
   double      sl;
   double      tp1;
   double      tp2;
   double      rr_tp1;
   double      rr_tp2;
   double      confidence;
  };

//+------------------------------------------------------------------+
//| true_range — Wilder's TR for one bar                             |
//+------------------------------------------------------------------+
double MC_TrueRange(const double prev_close, const double high, const double low)
  {
   const double a = high - low;
   const double b = MathAbs(high - prev_close);
   const double c = MathAbs(low  - prev_close);
   double tr = a;
   if(b > tr) tr = b;
   if(c > tr) tr = c;
   return tr;
  }

//+------------------------------------------------------------------+
//| MC_WilderATR — Wilder ATR at bar `shift` over `period` lookback. |
//| `shift` is in the indicator's reverse-time orientation: 0 is     |
//| newest, larger = older. Returns 0.0 if not enough history.       |
//+------------------------------------------------------------------+
double MC_WilderATR(const int shift, const int period,
                    const double &high[], const double &low[],
                    const double &close[])
  {
   if(period <= 0) return 0.0;
   const int total = ArraySize(close);
   if(shift + period >= total) return 0.0;

   // Seed with simple mean of TR over the `period` bars ending at
   // shift+period (oldest in our window).
   double seed = 0.0;
   for(int k = 0; k < period; k++)
     {
      const int i        = shift + period - k;        // newer index
      const int prev_i   = i + 1;                     // older index (prev close)
      seed += MC_TrueRange(close[prev_i], high[i], low[i]);
     }
   seed /= period;

   // Wilder smooth toward the target shift.
   double atr = seed;
   for(int s = shift + period - 1; s >= shift; s--)
     {
      const int prev_i = s + 1;
      const double tr  = MC_TrueRange(close[prev_i], high[s], low[s]);
      atr = (atr * (period - 1) + tr) / period;
     }
   return atr;
  }

//+------------------------------------------------------------------+
//| MC_LocalMeanRange — average (high-low) of the N bars *before*    |
//| `shift`. Excludes the candle at `shift` itself.                  |
//+------------------------------------------------------------------+
double MC_LocalMeanRange(const int shift, const int n,
                         const double &high[], const double &low[])
  {
   if(n <= 0) return 0.0;
   const int total = ArraySize(high);
   if(shift + n >= total) return 0.0;

   double sum = 0.0;
   for(int k = 1; k <= n; k++)
      sum += (high[shift + k] - low[shift + k]);
   return sum / n;
  }

//+------------------------------------------------------------------+
//| MC_LocalMeanVolume — same, for tick volume.                       |
//+------------------------------------------------------------------+
double MC_LocalMeanVolume(const int shift, const int n,
                          const long &tick_volume[])
  {
   if(n <= 0) return 0.0;
   const int total = ArraySize(tick_volume);
   if(shift + n >= total) return 0.0;

   double sum = 0.0;
   for(int k = 1; k <= n; k++)
      sum += (double)tick_volume[shift + k];
   return sum / n;
  }

//+------------------------------------------------------------------+
//| MC_SmaVolume — SMA(period) of tick_volume over the bars *before* |
//| `shift`. Used by the ATR/SMA proxy variant.                       |
//+------------------------------------------------------------------+
double MC_SmaVolume(const int shift, const int period,
                    const long &tick_volume[])
  {
   if(period <= 0) return 0.0;
   const int total = ArraySize(tick_volume);
   if(shift + period >= total) return 0.0;

   double sum = 0.0;
   for(int k = 1; k <= period; k++)
      sum += (double)tick_volume[shift + k];
   return sum / period;
  }

//+------------------------------------------------------------------+
//| MC_ClipUnit — clamp x to [0,1].                                  |
//+------------------------------------------------------------------+
double MC_ClipUnit(const double x)
  {
   if(x < 0.0) return 0.0;
   if(x > 1.0) return 1.0;
   return x;
  }

//+------------------------------------------------------------------+
//| MC_FibLevels — fill entry/sl/tp1/tp2 in `s` from the candle's    |
//| OHLC. `entry_on_next_open` true => use opens[shift-1] as entry.  |
//+------------------------------------------------------------------+
void MC_FibLevels(MC_Setup &s,
                  const bool entry_on_next_open,
                  const double &open[],
                  const double &close[])
  {
   const double rng = s.candle_high - s.candle_low;
   if(rng <= 0.0) return;

   if(s.direction == MC_DIR_BUY)
     {
      s.sl  = s.candle_low  - 0.10 * rng;
      s.tp1 = s.candle_high;
      s.tp2 = s.candle_high + 0.27 * rng;
      if(entry_on_next_open && s.shift - 1 >= 0)
         s.entry = open[s.shift - 1];
      else
         s.entry = s.candle_high - 0.236 * rng;
     }
   else if(s.direction == MC_DIR_SELL)
     {
      s.sl  = s.candle_high + 0.10 * rng;
      s.tp1 = s.candle_low;
      s.tp2 = s.candle_low  - 0.27 * rng;
      if(entry_on_next_open && s.shift - 1 >= 0)
         s.entry = open[s.shift - 1];
      else
         s.entry = s.candle_low + 0.236 * rng;
     }

   const double risk = MathAbs(s.entry - s.sl);
   if(risk > 0.0)
     {
      s.rr_tp1 = MathAbs(s.tp1 - s.entry) / risk;
      s.rr_tp2 = MathAbs(s.tp2 - s.entry) / risk;
     }
  }

//+------------------------------------------------------------------+
//| MC_ScoreConfidence — 0..1 weighted score matching Python detector|
//+------------------------------------------------------------------+
double MC_ScoreConfidence(const double body_pct,
                          const double range_ratio,
                          const double volume_ratio,
                          const double close_wick_pct,
                          const MC_Pattern pattern,
                          const double range_threshold,
                          const double range_headroom,
                          const double vol_threshold,
                          const double vol_headroom,
                          const double max_close_wick_pct)
  {
   const double body_score  = MC_ClipUnit((body_pct - 0.70) / 0.30);
   const double range_score = MC_ClipUnit((range_ratio - range_threshold) / range_headroom);
   const double vol_score   = MC_ClipUnit((volume_ratio - vol_threshold) / vol_headroom);
   const double wick_score  = MC_ClipUnit(1.0 - close_wick_pct / max_close_wick_pct);
   double pattern_score     = 0.5;
   if(pattern == MC_PATTERN_BREAKOUT) pattern_score = 1.0;
   else if(pattern == MC_PATTERN_TREND) pattern_score = 0.7;

   return 0.30 * body_score
        + 0.30 * range_score
        + 0.20 * vol_score
        + 0.10 * pattern_score
        + 0.10 * wick_score;
  }

//+------------------------------------------------------------------+
//| MC_ClassifyPattern — picks strongest matching pattern.            |
//| Mirrors Python: breakout > trend > pullback (else pullback).     |
//+------------------------------------------------------------------+
MC_Pattern MC_ClassifyPattern(const int shift,
                              const MC_Direction dir,
                              const int consolidation_lookback,
                              const int trend_lookback,
                              const int trend_min_monotonic,
                              const int pullback_lookback,
                              const double pullback_tolerance,
                              const double consolidation_tolerance,
                              const double range_baseline,
                              const double &high[],
                              const double &low[],
                              const double &close[])
  {
   //--- breakout: tight prior N, current close beyond range ---
   if(shift + consolidation_lookback < ArraySize(close))
     {
      double w_high = high[shift + 1];
      double w_low  = low[shift + 1];
      for(int k = 2; k <= consolidation_lookback; k++)
        {
         if(high[shift + k] > w_high) w_high = high[shift + k];
         if(low[shift + k]  < w_low)  w_low  = low[shift + k];
        }
      const double w_range = w_high - w_low;
      if(w_range > 0.0 && w_range <= consolidation_tolerance * range_baseline)
        {
         if(dir == MC_DIR_BUY  && close[shift] > w_high) return MC_PATTERN_BREAKOUT;
         if(dir == MC_DIR_SELL && close[shift] < w_low)  return MC_PATTERN_BREAKOUT;
        }
     }

   //--- trend continuation: enough monotonic prior diffs + 5-bar extreme ---
   if(shift + trend_lookback < ArraySize(close))
     {
      int monotonic = 0;
      for(int k = 1; k <= trend_lookback; k++)
        {
         const double diff = close[shift + k - 1] - close[shift + k];
         if(dir == MC_DIR_BUY  && diff > 0) monotonic++;
         if(dir == MC_DIR_SELL && diff < 0) monotonic++;
        }
      if(monotonic >= trend_min_monotonic)
        {
         double extreme = close[shift + 1];
         for(int k = 2; k <= 5 && shift + k < ArraySize(close); k++)
           {
            if(dir == MC_DIR_BUY  && close[shift + k] > extreme) extreme = close[shift + k];
            if(dir == MC_DIR_SELL && close[shift + k] < extreme) extreme = close[shift + k];
           }
         if(dir == MC_DIR_BUY  && close[shift] > extreme) return MC_PATTERN_TREND;
         if(dir == MC_DIR_SELL && close[shift] < extreme) return MC_PATTERN_TREND;
        }
     }

   //--- pullback: candle low/high within tolerance of recent swing ---
   if(shift + pullback_lookback < ArraySize(close))
     {
      if(dir == MC_DIR_BUY)
        {
         double recent_low = low[shift + 1];
         for(int k = 2; k <= pullback_lookback; k++)
            if(low[shift + k] < recent_low) recent_low = low[shift + k];
         if(MathAbs(low[shift] - recent_low) <= pullback_tolerance * range_baseline)
            return MC_PATTERN_PULLBACK;
        }
      else
        {
         double recent_high = high[shift + 1];
         for(int k = 2; k <= pullback_lookback; k++)
            if(high[shift + k] > recent_high) recent_high = high[shift + k];
         if(MathAbs(high[shift] - recent_high) <= pullback_tolerance * range_baseline)
            return MC_PATTERN_PULLBACK;
        }
     }

   return MC_PATTERN_PULLBACK;  // fallback — weakest pattern weight
  }

#endif // MOMENTUM_CANDLE_COMMON_MQH
