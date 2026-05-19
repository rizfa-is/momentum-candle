//+------------------------------------------------------------------+
//|                                  MomentumCandle_Visualizer.mq5   |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Visualization helper — shows the baseline the algorithm uses,    |
//| so you can see why a candle qualifies or fails at a glance.      |
//|                                                                  |
//| For each closed bar it draws two horizontal "whiskers" centered  |
//| on the bar's midpoint:                                           |
//|                                                                  |
//|   Gray whisker  = local-N mean range (the baseline)              |
//|   Color whisker = required range = baseline x InpRangeMult       |
//|                   GREEN if the candle clears every filter,       |
//|                   YELLOW if 3-of-4 pass (borderline),            |
//|                   RED if range itself fails.                     |
//|                                                                  |
//| If the candle pokes outside the color whisker on the long axis,  |
//| it passed the range filter. If the candle's body+wick geometry   |
//| also passes, the bar shows a small "OK" tag.                     |
//|                                                                  |
//| A top-left HUD prints live metrics for the most recently closed  |
//| bar with PASS/FAIL on each of the four filters, so you can see   |
//| exactly which condition rejected a candle that "looked like" a   |
//| momentum candle to your eye.                                     |
//|                                                                  |
//| Pure visual aid — no signal output buffers. Works alongside      |
//| MomentumCandle_Video and MomentumCandle_Proxy on the same chart. |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   2

//--- plot 1 — baseline whisker -------------------------------------
#property indicator_label1  "Baseline range"
#property indicator_type1   DRAW_HISTOGRAM2
#property indicator_color1  clrDimGray
#property indicator_style1  STYLE_SOLID
#property indicator_width1  4

//--- plot 2 — threshold whisker (colored) --------------------------
#property indicator_label2  "Threshold range"
#property indicator_type2   DRAW_COLOR_HISTOGRAM2
#property indicator_color2  clrLime,clrGold,clrCrimson
#property indicator_style2  STYLE_SOLID
#property indicator_width2  3

#include <MomentumCandleCommon.mqh>

//--- inputs --------------------------------------------------------
input double InpMinBodyPct      = 0.70;   // Min body / range
input double InpMaxCloseWickPct = 0.10;   // Max close-side wick / range
input double InpMaxFarWickPct   = 0.05;   // Max far-side (opposite) wick / range
input int    InpLocalLookback   = 5;      // Bars used for local mean baseline
input double InpRangeMult       = 1.5;    // Min range / local mean range
input double InpVolMult          = 1.5;   // Min tick_volume / local mean volume
input bool   InpShowBarLabels   = true;   // Per-bar small text with body% / R-mult / V-mult
input bool   InpShowHUD         = true;   // Top-left live readout
input int    InpMaxLabels       = 200;    // Cap label objects for chart speed
input string InpObjectPrefix    = "MCViz_"; // Prefix for chart objects

//--- buffers -------------------------------------------------------
double BufBaseTop[];        // baseline whisker top
double BufBaseBot[];        // baseline whisker bot
double BufThreshTop[];      // threshold whisker top
double BufThreshBot[];      // threshold whisker bot
double BufThreshColor[];    // threshold color index (0=lime, 1=gold, 2=crimson)

//--- state ---------------------------------------------------------
int g_label_seq = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufBaseTop,     INDICATOR_DATA);
   SetIndexBuffer(1, BufBaseBot,     INDICATOR_DATA);
   SetIndexBuffer(2, BufThreshTop,   INDICATOR_DATA);
   SetIndexBuffer(3, BufThreshBot,   INDICATOR_DATA);
   SetIndexBuffer(4, BufThreshColor, INDICATOR_COLOR_INDEX);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0.0);

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("MC Visualizer (N=%d, R=%.1fx, V=%.1fx, body>=%.0f%%)",
                                   InpLocalLookback, InpRangeMult, InpVolMult, InpMinBodyPct * 100.0));

   ArraySetAsSeries(BufBaseTop,     true);
   ArraySetAsSeries(BufBaseBot,     true);
   ArraySetAsSeries(BufThreshTop,   true);
   ArraySetAsSeries(BufThreshBot,   true);
   ArraySetAsSeries(BufThreshColor, true);

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, InpObjectPrefix);
   if(InpShowHUD) Comment("");
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double  &open[],
                const double  &high[],
                const double  &low[],
                const double  &close[],
                const long    &tick_volume[],
                const long    &volume[],
                const int     &spread[])
  {
   ArraySetAsSeries(time,        true);
   ArraySetAsSeries(open,        true);
   ArraySetAsSeries(high,        true);
   ArraySetAsSeries(low,         true);
   ArraySetAsSeries(close,       true);
   ArraySetAsSeries(tick_volume, true);

   const int min_history = MathMax(InpLocalLookback + 5, 30);
   if(rates_total < min_history) return 0;

   const int start = (prev_calculated > 1) ? rates_total - prev_calculated + 1 : rates_total - 2;
   for(int shift = start; shift >= 1; shift--)
     {
      EvaluateBar(shift, time, open, high, low, close, tick_volume);
     }

   //--- forming bar — clear visuals ---------------------------------
   BufBaseTop[0]     = 0.0;
   BufBaseBot[0]     = 0.0;
   BufThreshTop[0]   = 0.0;
   BufThreshBot[0]   = 0.0;
   BufThreshColor[0] = 0.0;

   //--- HUD: read the most-recently-closed bar (shift 1) -----------
   if(InpShowHUD)
      UpdateHUD(time, open, high, low, close, tick_volume);

   return rates_total;
  }

//+------------------------------------------------------------------+
//| EvaluateBar — compute baseline + threshold + per-bar visuals.    |
//+------------------------------------------------------------------+
void EvaluateBar(const int shift,
                 const datetime &time[],
                 const double  &open[],
                 const double  &high[],
                 const double  &low[],
                 const double  &close[],
                 const long    &tick_volume[])
  {
   // Defaults
   BufBaseTop[shift]     = 0.0;
   BufBaseBot[shift]     = 0.0;
   BufThreshTop[shift]   = 0.0;
   BufThreshBot[shift]   = 0.0;
   BufThreshColor[shift] = 0.0;

   if(shift + InpLocalLookback >= ArraySize(close)) return;

   const double o   = open[shift];
   const double h   = high[shift];
   const double lo  = low[shift];
   const double c   = close[shift];
   const double rng = h - lo;
   if(rng <= 0.0) return;

   const double body     = MathAbs(c - o);
   const double body_pct = body / rng;
   const bool   is_bull  = (c > o);
   const double close_wick = is_bull ? (h - c) : (c - lo);
   const double close_wick_pct = close_wick / rng;
   const double far_wick = is_bull ? (o - lo) : (h - o);
   const double far_wick_pct = far_wick / rng;

   const double mean_range = MC_LocalMeanRange(shift, InpLocalLookback, high, low);
   if(mean_range <= 0.0) return;
   const double range_ratio = rng / mean_range;

   const double mean_vol = MC_LocalMeanVolume(shift, InpLocalLookback, tick_volume);
   if(mean_vol <= 0.0) return;
   const double vol_ratio = (double)tick_volume[shift] / mean_vol;

   //--- per-filter pass flags --------------------------------------
   const bool pass_body     = (body_pct       >= InpMinBodyPct);
   const bool pass_wick     = (close_wick_pct <= InpMaxCloseWickPct);
   const bool pass_far_wick = (far_wick_pct   <= InpMaxFarWickPct);
   const bool pass_range    = (range_ratio    >= InpRangeMult);
   const bool pass_vol      = (vol_ratio      >= InpVolMult);
   const int  pass_count = (pass_body ? 1 : 0) + (pass_wick ? 1 : 0)
                         + (pass_far_wick ? 1 : 0)
                         + (pass_range ? 1 : 0) + (pass_vol ? 1 : 0);

   //--- whisker geometry ------------------------------------------
   // Anchor whiskers at the bar's midpoint so the visual is
   // "here is what a normal-sized candle would look like centered
   // on this bar". A momentum candle pokes outside the colored
   // whisker on the long axis.
   const double mid             = (h + lo) * 0.5;
   const double base_half       = mean_range * 0.5;
   const double thresh_half     = mean_range * InpRangeMult * 0.5;

   BufBaseTop[shift]   = mid + base_half;
   BufBaseBot[shift]   = mid - base_half;
   BufThreshTop[shift] = mid + thresh_half;
   BufThreshBot[shift] = mid - thresh_half;

   //--- color the threshold whisker by overall qualification -----
   //  0 = LIME  : passes ALL four filters
   //  1 = GOLD  : 3 of 4 pass (borderline — visually a momentum)
   //  2 = CRIMSON: range filter itself failed (or 2 or fewer pass)
   //--- threshold whisker color updated for 5-filter scoring --------
   //  0 = LIME    : passes ALL 5 filters
   //  1 = GOLD    : 4 of 5 (borderline)
   //  2 = CRIMSON : 3 or fewer pass
   if(pass_count == 5)        BufThreshColor[shift] = 0.0;
   else if(pass_count == 4)   BufThreshColor[shift] = 1.0;
   else                       BufThreshColor[shift] = 2.0;

   //--- per-bar text labels --------------------------------------
   if(InpShowBarLabels && pass_count >= 4)
      DrawBarLabel(shift, time[shift], h, lo,
                   body_pct, close_wick_pct, far_wick_pct, range_ratio, vol_ratio,
                   pass_body, pass_wick, pass_far_wick, pass_range, pass_vol);
  }

//+------------------------------------------------------------------+
//| DrawBarLabel — small text annotation above (or below) the bar.   |
//| Only draws for "interesting" bars (4+ filters pass) so the chart |
//| isn't littered with text on every candle.                        |
//+------------------------------------------------------------------+
void DrawBarLabel(const int shift,
                  const datetime t,
                  const double h,
                  const double lo,
                  const double body_pct,
                  const double close_wick_pct,
                  const double far_wick_pct,
                  const double range_ratio,
                  const double vol_ratio,
                  const bool pass_body,
                  const bool pass_close_wick,
                  const bool pass_far_wick,
                  const bool pass_range,
                  const bool pass_vol)
  {
   const string id = StringFormat("%sB%I64d", InpObjectPrefix, (long)t);

   string flags = "";
   flags += (pass_body       ? "B" : "b");
   flags += (pass_close_wick ? "W" : "w");
   flags += (pass_far_wick   ? "F" : "f");
   flags += (pass_range      ? "R" : "r");
   flags += (pass_vol        ? "V" : "v");

   const string txt = StringFormat("%s %.0f%% cw=%.0f%% fw=%.0f%% %.1fxR %.1fxV",
                                   flags, body_pct * 100.0,
                                   close_wick_pct * 100.0, far_wick_pct * 100.0,
                                   range_ratio, vol_ratio);

   const double price = h + (h - lo) * 0.30;

   if(ObjectFind(0, id) < 0)
      ObjectCreate(0, id, OBJ_TEXT, 0, t, price);
   else
     {
      ObjectSetInteger(0, id, OBJPROP_TIME, 0, t);
      ObjectSetDouble (0, id, OBJPROP_PRICE, 0, price);
     }

   const int passes = (pass_body ? 1 : 0) + (pass_close_wick ? 1 : 0)
                    + (pass_far_wick ? 1 : 0)
                    + (pass_range ? 1 : 0) + (pass_vol ? 1 : 0);
   const color clr = (passes == 5) ? clrLime : (passes == 4) ? clrGold : clrSilver;

   ObjectSetString (0, id, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, id, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, id, OBJPROP_BACK, false);

   PruneOldLabels();
  }

//+------------------------------------------------------------------+
void PruneOldLabels()
  {
   const int total = ObjectsTotal(0, 0, OBJ_TEXT);
   if(total <= InpMaxLabels) return;
   // Cheap prune: walk all matching objects and delete the oldest few.
   int removed = 0;
   for(int i = 0; i < ObjectsTotal(0, 0, OBJ_TEXT); i++)
     {
      const string nm = ObjectName(0, i, 0, OBJ_TEXT);
      if(StringFind(nm, InpObjectPrefix) != 0) continue;
      ObjectDelete(0, nm);
      i--;  // ObjectsTotal shrunk
      removed++;
      if(total - removed <= InpMaxLabels) break;
     }
  }

//+------------------------------------------------------------------+
//| UpdateHUD — top-left live status of the last closed bar.         |
//+------------------------------------------------------------------+
void UpdateHUD(const datetime &time[],
               const double  &open[],
               const double  &high[],
               const double  &low[],
               const double  &close[],
               const long    &tick_volume[])
  {
   const int shift = 1;
   if(shift + InpLocalLookback >= ArraySize(close))
     {
      Comment("MC Visualizer — not enough history yet");
      return;
     }

   const double o   = open[shift];
   const double h   = high[shift];
   const double lo  = low[shift];
   const double c   = close[shift];
   const double rng = h - lo;
   if(rng <= 0.0)
     {
      Comment("MC Visualizer — last bar has zero range");
      return;
     }

   const double body         = MathAbs(c - o);
   const double body_pct     = body / rng;
   const bool   is_bull      = (c > o);
   const string side         = is_bull ? "BULL" : "BEAR";
   const double close_wick   = is_bull ? (h - c) : (c - lo);
   const double cwick_pct    = close_wick / rng;
   const double far_wick     = is_bull ? (o - lo) : (h - o);
   const double fwick_pct    = far_wick / rng;
   const double mean_range   = MC_LocalMeanRange(shift, InpLocalLookback, high, low);
   const double range_ratio  = (mean_range > 0.0) ? rng / mean_range : 0.0;
   const double mean_vol     = MC_LocalMeanVolume(shift, InpLocalLookback, tick_volume);
   const double vol_ratio    = (mean_vol > 0.0) ? (double)tick_volume[shift] / mean_vol : 0.0;

   const bool pb  = (body_pct      >= InpMinBodyPct);
   const bool pcw = (cwick_pct     <= InpMaxCloseWickPct);
   const bool pfw = (fwick_pct     <= InpMaxFarWickPct);
   const bool pr  = (range_ratio   >= InpRangeMult);
   const bool pv  = (vol_ratio     >= InpVolMult);
   const int  pc  = (pb ? 1 : 0) + (pcw ? 1 : 0) + (pfw ? 1 : 0)
                  + (pr ? 1 : 0) + (pv ? 1 : 0);

   string verdict;
   if(pc == 5)      verdict = "QUALIFIES";
   else if(pc == 4) verdict = "BORDERLINE (4 of 5)";
   else             verdict = StringFormat("REJECTED (%d of 5 passed)", pc);

   string fail = "";
   if(!pb)  fail += " body";
   if(!pcw) fail += " close-wick";
   if(!pfw) fail += " far-wick";
   if(!pr)  fail += " range";
   if(!pv)  fail += " volume";
   if(StringLen(fail) > 0) fail = StringFormat("\n  Failing: %s", fail);

   Comment(StringFormat(
      "==== MC Visualizer ====\n"
      "Inputs: N=%d  body>=%.0f%%  cwick<=%.0f%%  fwick<=%.0f%%  range>=%.2fx  vol>=%.2fx\n"
      "\n"
      "Last closed bar (%s):  %s  range=%.2f\n"
      "  body       = %5.1f%%   %s  (need >= %.0f%%)\n"
      "  close-wick = %5.1f%%   %s  (need <= %.0f%%)\n"
      "  far-wick   = %5.1f%%   %s  (need <= %.0f%%)\n"
      "  range      = %5.2fx    %s  (need >= %.2fx)\n"
      "  volume     = %5.2fx    %s  (need >= %.2fx)\n"
      "\n"
      "Verdict: %s%s",
      InpLocalLookback,
      InpMinBodyPct * 100.0, InpMaxCloseWickPct * 100.0, InpMaxFarWickPct * 100.0,
      InpRangeMult, InpVolMult,
      TimeToString(time[shift], TIME_DATE | TIME_MINUTES), side, rng,
      body_pct   * 100.0, pb  ? "PASS" : "FAIL", InpMinBodyPct      * 100.0,
      cwick_pct  * 100.0, pcw ? "PASS" : "FAIL", InpMaxCloseWickPct * 100.0,
      fwick_pct  * 100.0, pfw ? "PASS" : "FAIL", InpMaxFarWickPct   * 100.0,
      range_ratio,        pr  ? "PASS" : "FAIL", InpRangeMult,
      vol_ratio,          pv  ? "PASS" : "FAIL", InpVolMult,
      verdict, fail));
  }
