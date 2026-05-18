//+------------------------------------------------------------------+
//|                                       MomentumCandle_Proxy.mq5   |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Variant 2 — ATR / SMA PROXY.                                     |
//|                                                                  |
//| Same body% and close-wick filters, but range and volume are      |
//| compared against:                                                |
//|   * Wilder ATR(14) for range expansion                           |
//|   * SMA(20) of tick volume                                       |
//|                                                                  |
//| This is the variant the Python detector currently uses (the one  |
//| this project's owner correctly flagged as a deviation from the   |
//| source video). Side-by-side with MomentumCandle_Video.mq5 to     |
//| compare signal counts and outcomes on the same chart / strategy  |
//| tester runs.                                                     |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   2

#property indicator_label1  "BUY momentum (proxy)"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrAqua
#property indicator_width1  2

#property indicator_label2  "SELL momentum (proxy)"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrMagenta
#property indicator_width2  2

#include <MomentumCandleCommon.mqh>

//--- inputs --------------------------------------------------------
input double InpMinBodyPct        = 0.70;   // Min body / range
input double InpMaxCloseWickPct   = 0.10;   // Max close-side wick / range
input int    InpAtrPeriod         = 14;     // Wilder ATR period
input double InpAtrMult           = 1.0;    // Min range / ATR
input int    InpVolSmaPeriod      = 20;     // SMA period for tick volume
input double InpVolMult           = 1.5;    // Min tick_volume / SMA
input double InpMinConfidence     = 0.50;   // Hide setups below this score
input bool   InpEntryOnNextOpen   = true;   // true=next bar open, false=23.6 retracement
input bool   InpDrawLevels        = true;   // Draw entry/SL/TP horizontal lines per setup
input bool   InpAlertOnNew        = false;  // Pop a terminal alert on new setup
input int    InpMaxLabels         = 30;     // Cap label objects to keep chart fast
input string InpObjectPrefix      = "MCP_"; // Prefix for chart objects

//--- buffers (read by EAs via iCustom) -----------------------------
double BufBuy[];
double BufSell[];
double BufDirection[];
double BufConfidence[];

//--- state ---------------------------------------------------------
datetime g_last_alert_time = 0;
int      g_label_seq       = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufBuy,        INDICATOR_DATA);
   SetIndexBuffer(1, BufSell,       INDICATOR_DATA);
   SetIndexBuffer(2, BufDirection,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(3, BufConfidence, INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("MomentumCandle Proxy (body>=%.0f%%, range>=%.1fxATR(%d), vol>=%.1fxSMA(%d))",
                                   InpMinBodyPct * 100.0, InpAtrMult, InpAtrPeriod, InpVolMult, InpVolSmaPeriod));

   ArraySetAsSeries(BufBuy, true);
   ArraySetAsSeries(BufSell, true);
   ArraySetAsSeries(BufDirection, true);
   ArraySetAsSeries(BufConfidence, true);

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, InpObjectPrefix);
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
   ArraySetAsSeries((datetime &)time,        true);
   ArraySetAsSeries((double  &)open,         true);
   ArraySetAsSeries((double  &)high,         true);
   ArraySetAsSeries((double  &)low,          true);
   ArraySetAsSeries((double  &)close,        true);
   ArraySetAsSeries((long    &)tick_volume,  true);

   const int min_history = MathMax(InpAtrPeriod + 5, InpVolSmaPeriod + 5);
   if(rates_total < min_history)
      return 0;

   const int start = (prev_calculated > 1) ? rates_total - prev_calculated + 1 : rates_total - 2;
   for(int shift = start; shift >= 1; shift--)
     {
      EvaluateBar(shift, time, open, high, low, close, tick_volume);
     }

   BufBuy[0] = EMPTY_VALUE;
   BufSell[0] = EMPTY_VALUE;
   BufDirection[0] = 0.0;
   BufConfidence[0] = 0.0;

   return rates_total;
  }

//+------------------------------------------------------------------+
void EvaluateBar(const int shift,
                 const datetime &time[],
                 const double  &open[],
                 const double  &high[],
                 const double  &low[],
                 const double  &close[],
                 const long    &tick_volume[])
  {
   BufBuy[shift]        = EMPTY_VALUE;
   BufSell[shift]       = EMPTY_VALUE;
   BufDirection[shift]  = 0.0;
   BufConfidence[shift] = 0.0;

   if(shift + InpAtrPeriod + 1 >= ArraySize(close)) return;
   if(shift + InpVolSmaPeriod  >= ArraySize(close)) return;

   const double o   = open[shift];
   const double h   = high[shift];
   const double lo  = low[shift];
   const double c   = close[shift];
   const double rng = h - lo;
   if(rng <= 0.0) return;

   const double body     = MathAbs(c - o);
   const double body_pct = body / rng;
   const MC_Direction dir = (c > o) ? MC_DIR_BUY : (c < o) ? MC_DIR_SELL : MC_DIR_NONE;
   if(dir == MC_DIR_NONE) return;

   const double close_wick     = (dir == MC_DIR_BUY) ? (h - c) : (c - lo);
   const double close_wick_pct = close_wick / rng;
   if(body_pct < InpMinBodyPct) return;
   if(close_wick_pct > InpMaxCloseWickPct) return;

   //--- ATR(14) baseline -------------------------------------------
   const double atr = MC_WilderATR(shift, InpAtrPeriod, high, low, close);
   if(atr <= 0.0) return;
   const double range_ratio = rng / atr;
   if(range_ratio < InpAtrMult) return;

   //--- SMA(20) of tick volume -------------------------------------
   const double vol_sma = MC_SmaVolume(shift, InpVolSmaPeriod, tick_volume);
   if(vol_sma <= 0.0) return;
   const double vol_ratio = (double)tick_volume[shift] / vol_sma;
   if(vol_ratio < InpVolMult) return;

   //--- pattern classification (uses ATR as baseline) --------------
   const MC_Pattern pattern = MC_ClassifyPattern(
                                 shift, dir,
                                 5, 10, 5, 10,
                                 0.382, 1.2,
                                 atr,
                                 high, low, close);

   //--- assemble setup --------------------------------------------
   MC_Setup s;
   s.trigger_time   = time[shift];
   s.shift          = shift;
   s.direction      = dir;
   s.pattern        = pattern;
   s.candle_open    = o;
   s.candle_high    = h;
   s.candle_low     = lo;
   s.candle_close   = c;
   s.body_pct       = body_pct;
   s.range_ratio    = range_ratio;
   s.volume_ratio   = vol_ratio;
   s.close_wick_pct = close_wick_pct;
   s.entry          = 0.0;
   s.sl             = 0.0;
   s.tp1            = 0.0;
   s.tp2            = 0.0;
   s.rr_tp1         = 0.0;
   s.rr_tp2         = 0.0;

   MC_FibLevels(s, InpEntryOnNextOpen, open, close);

   s.confidence = MC_ScoreConfidence(
                     body_pct, range_ratio, vol_ratio, close_wick_pct,
                     pattern,
                     /*range_threshold*/ InpAtrMult,
                     /*range_headroom*/ 1.5,
                     /*vol_threshold*/  InpVolMult,
                     /*vol_headroom*/   2.5,
                     /*max_close_wick_pct*/ InpMaxCloseWickPct);

   if(s.confidence < InpMinConfidence) return;

   BufDirection[shift]  = (dir == MC_DIR_BUY) ? 1.0 : -1.0;
   BufConfidence[shift] = s.confidence;
   if(dir == MC_DIR_BUY)
      BufBuy[shift]  = lo - rng * 0.10;
   else
      BufSell[shift] = h  + rng * 0.10;

   DrawSetup(s);

   if(InpAlertOnNew && shift == 1 && time[shift] != g_last_alert_time)
     {
      g_last_alert_time = time[shift];
      Alert(StringFormat("[MC-Proxy] %s %s conf=%.2f body=%.0f%% rng=%.2fxATR vol=%.2fxSMA (%s)",
                         _Symbol,
                         (dir == MC_DIR_BUY) ? "BUY" : "SELL",
                         s.confidence, body_pct * 100.0, range_ratio, vol_ratio,
                         PatternName(pattern)));
     }
  }

//+------------------------------------------------------------------+
void DrawSetup(const MC_Setup &s)
  {
   if(!InpDrawLevels) return;

   const string id  = StringFormat("%s%d_%I64d", InpObjectPrefix, g_label_seq++, (long)s.trigger_time);
   const datetime t1 = s.trigger_time;
   const datetime t2 = t1 + 30 * PeriodSeconds();

   DrawHLine(id + "_ENT", t1, t2, s.entry, clrSkyBlue,    "ENT");
   DrawHLine(id + "_SL",  t1, t2, s.sl,    clrOrangeRed,  "SL");
   DrawHLine(id + "_TP1", t1, t2, s.tp1,   clrAqua,       "TP1");
   DrawHLine(id + "_TP2", t1, t2, s.tp2,   clrTeal,       "TP2");

   const string lbl = StringFormat("%s%I64d_lbl", InpObjectPrefix, (long)s.trigger_time);
   const double y   = (s.direction == MC_DIR_BUY) ? s.candle_low - (s.candle_high - s.candle_low) * 0.20
                                                   : s.candle_high + (s.candle_high - s.candle_low) * 0.20;
   ObjectCreate(0, lbl, OBJ_TEXT, 0, t1, y);
   ObjectSetString(0, lbl, OBJPROP_TEXT,
                   StringFormat("%s %.2f  body=%.0f%% rng=%.2fxATR vol=%.2fxSMA",
                                (s.direction == MC_DIR_BUY) ? "BUY" : "SELL",
                                s.confidence, s.body_pct * 100.0, s.range_ratio, s.volume_ratio));
   ObjectSetInteger(0, lbl, OBJPROP_COLOR,
                    (s.direction == MC_DIR_BUY) ? clrAqua : clrMagenta);
   ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, lbl, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);

   PruneOldObjects();
  }

//+------------------------------------------------------------------+
void DrawHLine(const string id, const datetime t1, const datetime t2,
               const double price, const color clr, const string text)
  {
   ObjectCreate(0, id, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, id, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, id, OBJPROP_BACK, true);
   ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, false);
   ObjectSetString (0, id, OBJPROP_TEXT, text);
  }

//+------------------------------------------------------------------+
void PruneOldObjects()
  {
   const int total = ObjectsTotal(0, 0, -1);
   if(total <= InpMaxLabels * 6) return;
   for(int i = 0; i < total; i++)
     {
      const string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, InpObjectPrefix) != 0) continue;
      ObjectDelete(0, nm);
      if(ObjectsTotal(0, 0, -1) <= InpMaxLabels * 5) break;
     }
  }

//+------------------------------------------------------------------+
string PatternName(const MC_Pattern p)
  {
   if(p == MC_PATTERN_BREAKOUT) return "breakout";
   if(p == MC_PATTERN_TREND)    return "trend";
   if(p == MC_PATTERN_PULLBACK) return "pullback";
   return "none";
  }
