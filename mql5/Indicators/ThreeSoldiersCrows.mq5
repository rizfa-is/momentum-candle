//+------------------------------------------------------------------+
//|                                       ThreeSoldiersCrows.mq5     |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Three White Soldiers (bullish) and Three Black Crows (bearish)   |
//| candlestick pattern detector.                                    |
//|                                                                  |
//| Three White Soldiers (BUY signal):                               |
//|   * 3 consecutive bullish (close > open) candles                 |
//|   * Each close > previous close (rising staircase)               |
//|   * Each open within the previous candle's body (strict mode)    |
//|     OR each open below the previous candle's close (loose mode)  |
//|   * Each candle has body% >= InpMinBodyPct                       |
//|   * Each candle's upper wick <= InpMaxWickPct of range           |
//|   * Optional minimum body in price points (size floor)           |
//|                                                                  |
//| Three Black Crows (SELL signal):                                 |
//|   Mirror of the above for bearish candles.                       |
//|                                                                  |
//| Plots a green up-arrow below the third bullish candle of a       |
//| Three Soldiers pattern, and a red down-arrow above the third     |
//| bearish candle of a Three Crows pattern.                         |
//|                                                                  |
//| Optional session filter (Asia + NY only) per the eye-model       |
//| findings from the momentum-candle project.                       |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   2

#property indicator_label1  "Three White Soldiers"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_width1  2

#property indicator_label2  "Three Black Crows"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_width2  2

//--- inputs --------------------------------------------------------
input group "Filter toggles (all OFF by default -- enable to test combos)"
input bool   InpUseMinBodyPct    = false;  // enforce min body / range per candle
input double InpMinBodyPct       = 0.60;   //   threshold (when enabled)
input bool   InpUseMaxWickPct    = false;  // enforce max same-direction wick / range
input double InpMaxWickPct       = 0.25;   //   threshold (when enabled)
input bool   InpUseMinBodyPoints = false;  // enforce min body in absolute points
input double InpMinBodyPoints    = 500;    //   threshold (when enabled)
input bool   InpUseOpenRule      = false;  // enforce open-vs-prior-bar relationship
input bool   InpStrictOpen       = false;  //   strict: open inside prior body; loose: open below prior close
input bool   InpSkipEqualClose   = false;  // require strictly rising/falling closes (no flat or non-monotonic)

input group "Optional session filter"
input bool   InpUseSessionFilter = false;  // skip London chop window if true
input int    InpAsiaStartHourUTC = 23;
input int    InpAsiaEndHourUTC   = 8;
input int    InpNYStartHourUTC   = 12;
input int    InpNYEndHourUTC     = 22;

input group "Display"
input bool   InpAlertOnNew       = false;  // pop alert on new pattern
input bool   InpDrawLabels       = true;   // draw "3WS" / "3BC" text label
input string InpObjectPrefix     = "TSC_"; // prefix for chart objects
input int    InpMaxLabels        = 50;     // cap label objects for chart speed

//--- buffers -------------------------------------------------------
double BufBuy[];           // up arrow under third soldier
double BufSell[];          // down arrow above third crow
double BufDirection[];     // +1 = TWS, -1 = TBC, 0 = none (calc buffer)
double BufStrength[];      // 0..1 quality score (calc buffer)

//--- state ---------------------------------------------------------
datetime g_last_alert_time = 0;
int      g_label_seq       = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufBuy,       INDICATOR_DATA);
   SetIndexBuffer(1, BufSell,      INDICATOR_DATA);
   SetIndexBuffer(2, BufDirection, INDICATOR_CALCULATIONS);
   SetIndexBuffer(3, BufStrength,  INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   string flags = "";
   if(InpUseMinBodyPct)    flags += StringFormat(" body>=%.0f%%", InpMinBodyPct * 100.0);
   if(InpUseMaxWickPct)    flags += StringFormat(" wick<=%.0f%%", InpMaxWickPct * 100.0);
   if(InpUseMinBodyPoints) flags += StringFormat(" body>=%.0fpt", InpMinBodyPoints);
   if(InpUseOpenRule)      flags += InpStrictOpen ? " strict-open" : " loose-open";
   if(InpSkipEqualClose)   flags += " mono";
   if(InpUseSessionFilter) flags += " sessA+NY";
   if(StringLen(flags) == 0) flags = " RAW (no filters)";

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("Three Soldiers/Crows%s", flags));

   ArraySetAsSeries(BufBuy,       true);
   ArraySetAsSeries(BufSell,      true);
   ArraySetAsSeries(BufDirection, true);
   ArraySetAsSeries(BufStrength,  true);

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, InpObjectPrefix);
  }

//+------------------------------------------------------------------+
//| Time-of-day session check (UTC, with server-time offset)         |
//+------------------------------------------------------------------+
bool InActiveSession(const datetime t)
  {
   if(!InpUseSessionFilter) return true;
   const long offset = (long)TimeGMT() - (long)TimeCurrent();
   const datetime t_utc = (datetime)((long)t + offset);
   MqlDateTime dt;
   TimeToStruct(t_utc, dt);
   const int h = dt.hour;
   bool in_asia;
   if(InpAsiaStartHourUTC <= InpAsiaEndHourUTC)
      in_asia = (h >= InpAsiaStartHourUTC && h < InpAsiaEndHourUTC);
   else
      in_asia = (h >= InpAsiaStartHourUTC || h < InpAsiaEndHourUTC);
   bool in_ny;
   if(InpNYStartHourUTC <= InpNYEndHourUTC)
      in_ny = (h >= InpNYStartHourUTC && h < InpNYEndHourUTC);
   else
      in_ny = (h >= InpNYStartHourUTC || h < InpNYEndHourUTC);
   return in_asia || in_ny;
  }

//+------------------------------------------------------------------+
//| Per-bar pattern checks                                            |
//+------------------------------------------------------------------+

bool IsBullCandle(const int shift,
                  const double &open[], const double &high[],
                  const double &low[], const double &close[])
  {
   const double o = open[shift], c = close[shift];
   const double h = high[shift], l = low[shift];
   const double rng = h - l;
   if(rng <= 0.0) return false;
   if(c <= o) return false;

   const double body = c - o;

   if(InpUseMinBodyPct)
     {
      const double body_pct = body / rng;
      if(body_pct < InpMinBodyPct) return false;
     }

   if(InpUseMaxWickPct)
     {
      const double upper_wick = h - c;
      const double upper_pct = upper_wick / rng;
      if(upper_pct > InpMaxWickPct) return false;
     }

   if(InpUseMinBodyPoints && InpMinBodyPoints > 0)
     {
      const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(point > 0 && (body / point) < InpMinBodyPoints) return false;
     }
   return true;
  }

bool IsBearCandle(const int shift,
                  const double &open[], const double &high[],
                  const double &low[], const double &close[])
  {
   const double o = open[shift], c = close[shift];
   const double h = high[shift], l = low[shift];
   const double rng = h - l;
   if(rng <= 0.0) return false;
   if(c >= o) return false;

   const double body = o - c;

   if(InpUseMinBodyPct)
     {
      const double body_pct = body / rng;
      if(body_pct < InpMinBodyPct) return false;
     }

   if(InpUseMaxWickPct)
     {
      const double lower_wick = c - l;
      const double lower_pct = lower_wick / rng;
      if(lower_pct > InpMaxWickPct) return false;
     }

   if(InpUseMinBodyPoints && InpMinBodyPoints > 0)
     {
      const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(point > 0 && (body / point) < InpMinBodyPoints) return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Open-in-prior-body relationship                                   |
//+------------------------------------------------------------------+

bool BullOpenInsidePrior(const int curr, const int prior,
                         const double &open[], const double &close[])
  {
   if(!InpUseOpenRule) return true;  // no open-relationship constraint
   const double curr_open = open[curr];
   const double prior_open = open[prior];
   const double prior_close = close[prior];
   if(InpStrictOpen)
      return (curr_open > prior_open && curr_open < prior_close);
   return curr_open < prior_close;  // loose: any open below prior close (= still inside or below body)
  }

bool BearOpenInsidePrior(const int curr, const int prior,
                         const double &open[], const double &close[])
  {
   if(!InpUseOpenRule) return true;
   const double curr_open = open[curr];
   const double prior_open = open[prior];
   const double prior_close = close[prior];
   if(InpStrictOpen)
      return (curr_open < prior_open && curr_open > prior_close);
   return curr_open > prior_close;
  }

//+------------------------------------------------------------------+
//| Three-soldier check: shift is the most-recent bar of the trio    |
//+------------------------------------------------------------------+

bool IsThreeWhiteSoldiers(const int shift,
                          const double &open[], const double &high[],
                          const double &low[], const double &close[])
  {
   if(shift + 2 >= ArraySize(close)) return false;

   // Three bullish candles
   if(!IsBullCandle(shift,     open, high, low, close)) return false;
   if(!IsBullCandle(shift + 1, open, high, low, close)) return false;
   if(!IsBullCandle(shift + 2, open, high, low, close)) return false;

   // Rising closes
   if(InpSkipEqualClose)
     {
      if(!(close[shift]     > close[shift + 1])) return false;
      if(!(close[shift + 1] > close[shift + 2])) return false;
     }
   else
     {
      if(close[shift]     < close[shift + 1]) return false;
      if(close[shift + 1] < close[shift + 2]) return false;
     }

   // Open inside (or below close of) prior body
   if(!BullOpenInsidePrior(shift,     shift + 1, open, close)) return false;
   if(!BullOpenInsidePrior(shift + 1, shift + 2, open, close)) return false;

   return true;
  }

bool IsThreeBlackCrows(const int shift,
                       const double &open[], const double &high[],
                       const double &low[], const double &close[])
  {
   if(shift + 2 >= ArraySize(close)) return false;

   if(!IsBearCandle(shift,     open, high, low, close)) return false;
   if(!IsBearCandle(shift + 1, open, high, low, close)) return false;
   if(!IsBearCandle(shift + 2, open, high, low, close)) return false;

   if(InpSkipEqualClose)
     {
      if(!(close[shift]     < close[shift + 1])) return false;
      if(!(close[shift + 1] < close[shift + 2])) return false;
     }
   else
     {
      if(close[shift]     > close[shift + 1]) return false;
      if(close[shift + 1] > close[shift + 2]) return false;
     }

   if(!BearOpenInsidePrior(shift,     shift + 1, open, close)) return false;
   if(!BearOpenInsidePrior(shift + 1, shift + 2, open, close)) return false;

   return true;
  }

//+------------------------------------------------------------------+
//| Strength score 0..1                                               |
//| Higher when bodies are bigger, wicks smaller, momentum cleaner   |
//+------------------------------------------------------------------+

double PatternStrength(const int shift, const bool bullish,
                       const double &open[], const double &high[],
                       const double &low[], const double &close[])
  {
   double sum_body_pct = 0;
   double sum_wick_pct = 0;
   double total_range = 0;
   for(int k = 0; k < 3; k++)
     {
      const int s = shift + k;
      const double rng = high[s] - low[s];
      if(rng <= 0) return 0;
      const double body = MathAbs(close[s] - open[s]);
      const double wick = bullish ? (high[s] - close[s]) : (close[s] - low[s]);
      sum_body_pct += body / rng;
      sum_wick_pct += wick / rng;
      total_range  += rng;
     }
   const double avg_body_pct = sum_body_pct / 3;
   const double avg_wick_pct = sum_wick_pct / 3;

   // Total displacement = third close - first open (for bull); mirror for bear
   const double displacement = bullish
                                ? (close[shift] - open[shift + 2])
                                : (open[shift + 2] - close[shift]);
   const double avg_range = total_range / 3;
   const double displ_score = MathMax(0.0, MathMin(1.0, displacement / (avg_range * 2.5)));

   const double body_score = MathMax(0.0, MathMin(1.0, (avg_body_pct - InpMinBodyPct) / (1.0 - InpMinBodyPct)));
   const double wick_score = MathMax(0.0, MathMin(1.0, 1.0 - avg_wick_pct / InpMaxWickPct));

   return 0.40 * body_score + 0.25 * wick_score + 0.35 * displ_score;
  }

//+------------------------------------------------------------------+
//| Drawing                                                           |
//+------------------------------------------------------------------+

void DrawLabel(const string id, const datetime t, const double price,
               const string text, const color clr)
  {
   if(!InpDrawLabels) return;
   ObjectCreate(0, id, OBJ_TEXT, 0, t, price);
   ObjectSetString (0, id, OBJPROP_TEXT, text);
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, id, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, id, OBJPROP_BACK, false);
  }

void PruneLabels()
  {
   if(ObjectsTotal(0, 0, OBJ_TEXT) <= InpMaxLabels) return;
   for(int i = 0; i < ObjectsTotal(0, 0, OBJ_TEXT); i++)
     {
      const string nm = ObjectName(0, i, 0, OBJ_TEXT);
      if(StringFind(nm, InpObjectPrefix) != 0) continue;
      ObjectDelete(0, nm);
      i--;
      if(ObjectsTotal(0, 0, OBJ_TEXT) <= InpMaxLabels - 5) break;
     }
  }

//+------------------------------------------------------------------+
//| Evaluate one bar                                                  |
//+------------------------------------------------------------------+

void EvaluateBar(const int shift,
                 const datetime &time[],
                 const double &open[], const double &high[],
                 const double &low[], const double &close[])
  {
   BufBuy[shift]       = EMPTY_VALUE;
   BufSell[shift]      = EMPTY_VALUE;
   BufDirection[shift] = 0.0;
   BufStrength[shift]  = 0.0;

   if(!InActiveSession(time[shift])) return;

   if(IsThreeWhiteSoldiers(shift, open, high, low, close))
     {
      const double rng = high[shift] - low[shift];
      BufBuy[shift]       = low[shift] - rng * 0.20;
      BufDirection[shift] = 1.0;
      const double s = PatternStrength(shift, true, open, high, low, close);
      BufStrength[shift]  = s;

      const string id = StringFormat("%sTWS_%I64d", InpObjectPrefix, (long)time[shift]);
      DrawLabel(id, time[shift], low[shift] - rng * 0.30,
                StringFormat("3WS %.2f", s), clrLime);

      if(InpAlertOnNew && shift == 1 && time[shift] != g_last_alert_time)
        {
         g_last_alert_time = time[shift];
         Alert(StringFormat("[3WS] %s strength=%.2f", _Symbol, s));
        }
     }
   else if(IsThreeBlackCrows(shift, open, high, low, close))
     {
      const double rng = high[shift] - low[shift];
      BufSell[shift]      = high[shift] + rng * 0.20;
      BufDirection[shift] = -1.0;
      const double s = PatternStrength(shift, false, open, high, low, close);
      BufStrength[shift]  = s;

      const string id = StringFormat("%sTBC_%I64d", InpObjectPrefix, (long)time[shift]);
      DrawLabel(id, time[shift], high[shift] + rng * 0.30,
                StringFormat("3BC %.2f", s), clrCrimson);

      if(InpAlertOnNew && shift == 1 && time[shift] != g_last_alert_time)
        {
         g_last_alert_time = time[shift];
         Alert(StringFormat("[3BC] %s strength=%.2f", _Symbol, s));
        }
     }

   PruneLabels();
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                       |
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
   ArraySetAsSeries(time,  true);
   ArraySetAsSeries(open,  true);
   ArraySetAsSeries(high,  true);
   ArraySetAsSeries(low,   true);
   ArraySetAsSeries(close, true);

   if(rates_total < 5) return 0;

   const int start = (prev_calculated > 1) ? rates_total - prev_calculated + 1 : rates_total - 4;
   for(int shift = start; shift >= 1; shift--)
      EvaluateBar(shift, time, open, high, low, close);

   // Forming bar always cleared
   BufBuy[0]       = EMPTY_VALUE;
   BufSell[0]      = EMPTY_VALUE;
   BufDirection[0] = 0.0;
   BufStrength[0]  = 0.0;
   return rates_total;
  }
