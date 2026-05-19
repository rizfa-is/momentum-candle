//+------------------------------------------------------------------+
//|                                       MomentumCandle_Simple.mq5  |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| The simplest possible momentum-candle indicator.                 |
//|                                                                  |
//| Three filters only:                                              |
//|   1. body / range          >= InpMinBodyPct                      |
//|   2. close-side wick / range <= InpMaxCloseWickPct               |
//|   3. body in absolute price points >= InpMinBodyPoints           |
//|                                                                  |
//| No range/volume/ATR/baseline. No pattern classification.         |
//| No fib levels. Just a green up-arrow on BUY momentum and a red   |
//| down-arrow on SELL momentum.                                     |
//|                                                                  |
//| Use this to test the eye-model's two simplest gates: shape       |
//| (body% + close-wick%) and absolute size floor (in price points). |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "BUY momentum"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_width1  2

#property indicator_label2  "SELL momentum"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrCrimson
#property indicator_width2  2

//--- inputs --------------------------------------------------------
input double InpMinBodyPct       = 0.70;   // Min body / range
input double InpMaxCloseWickPct  = 0.10;   // Max close-side wick / range
input double InpMinBodyPoints    = 8.0;    // Min body in price points (absolute floor)
input bool   InpAlertOnNew       = false;  // Pop terminal alert on new setup

//--- buffers -------------------------------------------------------
double BufBuy[];
double BufSell[];

//--- state ---------------------------------------------------------
datetime g_last_alert_time = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, BufBuy,  INDICATOR_DATA);
   SetIndexBuffer(1, BufSell, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);   // up arrow code
   PlotIndexSetInteger(1, PLOT_ARROW, 234);   // down arrow code
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("MomentumCandle Simple (body>=%.0f%%, wick<=%.0f%%, body>=%.1fpt)",
                                   InpMinBodyPct * 100.0,
                                   InpMaxCloseWickPct * 100.0,
                                   InpMinBodyPoints));

   ArraySetAsSeries(BufBuy,  true);
   ArraySetAsSeries(BufSell, true);
   return INIT_SUCCEEDED;
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
   ArraySetAsSeries(time,  true);
   ArraySetAsSeries(open,  true);
   ArraySetAsSeries(high,  true);
   ArraySetAsSeries(low,   true);
   ArraySetAsSeries(close, true);

   if(rates_total < 5) return 0;

   const int start = (prev_calculated > 1) ? rates_total - prev_calculated + 1 : rates_total - 2;
   for(int shift = start; shift >= 1; shift--)
     {
      EvaluateBar(shift, time, open, high, low, close);
     }

   // Forming bar always cleared.
   BufBuy[0]  = EMPTY_VALUE;
   BufSell[0] = EMPTY_VALUE;
   return rates_total;
  }

//+------------------------------------------------------------------+
//| EvaluateBar — apply three filters at `shift`.                    |
//+------------------------------------------------------------------+
void EvaluateBar(const int shift,
                 const datetime &time[],
                 const double  &open[],
                 const double  &high[],
                 const double  &low[],
                 const double  &close[])
  {
   BufBuy[shift]  = EMPTY_VALUE;
   BufSell[shift] = EMPTY_VALUE;

   const double o   = open[shift];
   const double h   = high[shift];
   const double lo  = low[shift];
   const double c   = close[shift];
   const double rng = h - lo;
   if(rng <= 0.0) return;

   const double body  = MathAbs(c - o);
   const double body_pct = body / rng;
   const bool   is_bull  = (c > o);
   const bool   is_bear  = (c < o);
   if(!is_bull && !is_bear) return;

   const double close_wick     = is_bull ? (h - c) : (c - lo);
   const double close_wick_pct = close_wick / rng;

   //--- three gates --------------------------------------------------
   if(body_pct < InpMinBodyPct) return;
   if(close_wick_pct > InpMaxCloseWickPct) return;

   // body in price points
   const double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double body_pts  = (point > 0.0) ? (body / point) : 0.0;
   if(body_pts < InpMinBodyPoints) return;

   //--- plot arrow --------------------------------------------------
   const double margin = rng * 0.10;
   if(is_bull)
      BufBuy[shift]  = lo - margin;
   else
      BufSell[shift] = h + margin;

   //--- alert (most recently closed bar only) -----------------------
   if(InpAlertOnNew && shift == 1 && time[shift] != g_last_alert_time)
     {
      g_last_alert_time = time[shift];
      Alert(StringFormat("[MC-Simple] %s %s body=%.0f%% wick=%.0f%% body_pts=%.1f",
                         _Symbol,
                         is_bull ? "BUY" : "SELL",
                         body_pct * 100.0,
                         close_wick_pct * 100.0,
                         body_pts));
     }
  }
