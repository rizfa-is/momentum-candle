//+------------------------------------------------------------------+
//|                                            AmdFvgSignal.mq5      |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Detects the canonical ICT AMD sequence on the active chart:      |
//|                                                                  |
//|   1. ACCUMULATION                                                |
//|        Asian session (default 00:00-07:00 UTC) defines a range.  |
//|        At 07:00 UTC the range is locked; high/low become AccHi   |
//|        and AccLo for the rest of the day.                        |
//|                                                                  |
//|   2. MANIPULATION                                                |
//|        During London window (default 07:00-12:00 UTC) we wait    |
//|        for a sweep + close-back:                                 |
//|          BSL sweep:  bar.high > AccHi AND close back inside      |
//|          SSL sweep:  bar.low  < AccLo AND close back inside      |
//|        First match wins. Locks trade direction:                  |
//|          BSL  -> SHORT bias (price reverses down after sweep)    |
//|          SSL  -> LONG  bias (price reverses up after sweep)      |
//|                                                                  |
//|   3. FVG (entry trigger)                                         |
//|        From NY-open (12:00 UTC default) onwards we scan each     |
//|        closed bar for a 3-candle FVG in trade direction:         |
//|          Bullish FVG @ idx:  Low[idx]  > High[idx-2]             |
//|          Bearish FVG @ idx:  High[idx] <  Low[idx-2]             |
//|        First in-direction FVG fires the alert and locks state.   |
//|                                                                  |
//|   4. DISTRIBUTION                                                |
//|        Anything after the FVG fires is the distribution leg      |
//|        (drawn cosmetically; no further alerts).                  |
//|                                                                  |
//| Visuals                                                          |
//|   - Accumulation: shaded rectangle from session start to EOD     |
//|     (height = AccHi..AccLo).                                     |
//|   - Manipulation: small text "M" at the sweep bar, color-coded   |
//|     red (BSL) or green (SSL).                                    |
//|   - FVG: rectangle covering the gap, labelled "AMD-DOWN" /       |
//|     "AMD-UP" at the displacement bar.                            |
//|   - Once the FVG fires, an arrow is drawn at that bar.           |
//|                                                                  |
//| State resets at every new UTC day. Indicator is symbol/TF        |
//| agnostic (use it on M5, M15, H1; works on any pair you attach).  |
//|                                                                  |
//| Alert: fires once per day, when the FVG bar closes inside a      |
//| valid Acc -> Manip -> FVG sequence.                              |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

//--- inputs --------------------------------------------------------
input group "Sessions (UTC, end-hour exclusive)"
input int    InpAsiaStartHourUTC    = 0;     // Asia start hour
input int    InpAsiaEndHourUTC      = 7;     // Asia end hour (= London start)
input int    InpLondonEndHourUTC    = 12;    // London end hour (= NY start)
input int    InpNYEndHourUTC        = 22;    // NY end hour (sequence invalid after this)

input group "Detection"
input bool   InpRequireCloseBack    = true;  // Manip bar must close back inside range
input int    InpMaxSequencesPerDay  = 1;     // Cap completed AMD sequences per UTC day

input group "Visuals"
input bool   InpDrawAccBox          = true;  // Shaded box for accumulation range
input color  InpAccBoxColor         = clrSlateGray;
input int    InpAccBoxTransparency  = 80;    // 0=solid, 255=invisible (uses alpha)
input bool   InpDrawManipMarker     = true;  // "M" text at sweep bar
input color  InpManipBSLColor       = clrCrimson;     // BSL sweep (short bias)
input color  InpManipSSLColor       = clrLimeGreen;   // SSL sweep (long  bias)
input bool   InpDrawFvgBox          = true;
input color  InpFvgBullColor        = clrLimeGreen;
input color  InpFvgBearColor        = clrCrimson;
input int    InpFvgBoxBars          = 30;    // FVG box right-extent in bars
input bool   InpDrawSignalArrow     = true;
input color  InpSignalLongColor     = clrLimeGreen;
input color  InpSignalShortColor    = clrCrimson;

input group "Alerts"
input bool   InpAlertPopup          = true;
input bool   InpAlertSound          = true;
input string InpAlertSoundFile      = "alert.wav";
input bool   InpAlertPush           = false;
input bool   InpAlertEmail          = false;

input group "Misc"
input string InpObjectPrefix        = "AMD_";
input bool   InpDebugLog            = false;

//--- state machine -------------------------------------------------
enum AmdState
  {
   STATE_WAIT_ACC      = 0,  // building accumulation
   STATE_WAIT_MANIP    = 1,  // accumulation locked, waiting sweep
   STATE_WAIT_FVG      = 2,  // sweep confirmed, waiting FVG
   STATE_DONE          = 3,  // FVG fired; sequence complete for the day
   STATE_INVALIDATED   = 4   // missed the window; rest of day is dead
  };

enum SweepSide
  {
   SWEEP_NONE = 0,
   SWEEP_BSL  = 1,           // sweep buy-side liquidity (bias = SHORT)
   SWEEP_SSL  = 2            // sweep sell-side liquidity (bias = LONG)
  };

//--- per-day session state -----------------------------------------
struct DayState
  {
   datetime  day_utc_start;     // 00:00 UTC of the day this state covers
   AmdState  state;
   double    acc_hi;
   double    acc_lo;
   datetime  acc_lock_time;     // when accumulation locked (= London start)
   SweepSide sweep_side;
   datetime  sweep_time;
   double    sweep_extreme;
   datetime  fvg_time;
   double    fvg_low;
   double    fvg_high;
   int       sequences_today;
  };

DayState g_day = {0, STATE_WAIT_ACC, 0, 0, 0, SWEEP_NONE, 0, 0, 0, 0, 0, 0};
datetime g_last_evaluated_bar = 0;

//+------------------------------------------------------------------+
//| OnInit / OnDeinit                                                 |
//+------------------------------------------------------------------+
int OnInit()
  {
   ResetDayState(0);
   if(InpDebugLog)
      PrintFormat("[AMD] init: Asia %02d-%02d, London end %02d, NY end %02d (UTC)",
                  InpAsiaStartHourUTC, InpAsiaEndHourUTC, InpLondonEndHourUTC, InpNYEndHourUTC);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   DeleteAllOurObjects();
  }

//+------------------------------------------------------------------+
//| Object lifecycle helpers                                          |
//+------------------------------------------------------------------+
void DeleteAllOurObjects()
  {
   const int n = ObjectsTotal(0, -1, -1);
   for(int i = n - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, InpObjectPrefix) == 0)
         ObjectDelete(0, name);
     }
  }

string ObjName(const string suffix)
  {
   return StringFormat("%s%s", InpObjectPrefix, suffix);
  }

//+------------------------------------------------------------------+
//| UTC time helpers                                                  |
//+------------------------------------------------------------------+
datetime ServerToUtc(const datetime t_server)
  {
   const long offset = (long)TimeGMT() - (long)TimeCurrent();
   return (datetime)((long)t_server + offset);
  }

datetime DayStartUtc(const datetime t_utc)
  {
   MqlDateTime dt;
   TimeToStruct(t_utc, dt);
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return StructToTime(dt);
  }

int UtcHour(const datetime t_server)
  {
   const datetime t_utc = ServerToUtc(t_server);
   MqlDateTime dt;
   TimeToStruct(t_utc, dt);
   return dt.hour;
  }

bool InWindow(const int hour, const int start_h, const int end_h_exclusive)
  {
   if(start_h <= end_h_exclusive)
      return (hour >= start_h && hour < end_h_exclusive);
   // wraparound (e.g. 22 -> 6)
   return (hour >= start_h || hour < end_h_exclusive);
  }

//+------------------------------------------------------------------+
//| State management                                                  |
//+------------------------------------------------------------------+
void ResetDayState(const datetime day_start_utc)
  {
   g_day.day_utc_start = day_start_utc;
   g_day.state         = STATE_WAIT_ACC;
   g_day.acc_hi        = 0;
   g_day.acc_lo        = 0;
   g_day.acc_lock_time = 0;
   g_day.sweep_side    = SWEEP_NONE;
   g_day.sweep_time    = 0;
   g_day.sweep_extreme = 0;
   g_day.fvg_time      = 0;
   g_day.fvg_low       = 0;
   g_day.fvg_high      = 0;
   g_day.sequences_today = 0;
  }

//+------------------------------------------------------------------+
//| Accumulation building                                             |
//+------------------------------------------------------------------+
void UpdateAccumulation(const int shift)
  {
   const double bh = iHigh (_Symbol, _Period, shift);
   const double bl = iLow  (_Symbol, _Period, shift);
   if(g_day.acc_hi == 0 || bh > g_day.acc_hi) g_day.acc_hi = bh;
   if(g_day.acc_lo == 0 || bl < g_day.acc_lo) g_day.acc_lo = bl;
  }

void LockAccumulation(const datetime t_server)
  {
   g_day.acc_lock_time = t_server;
   g_day.state = STATE_WAIT_MANIP;

   if(InpDrawAccBox && g_day.acc_hi > 0 && g_day.acc_lo > 0)
     {
      const string name = ObjName(StringFormat("ACC_%d", (int)g_day.day_utc_start));
      // Box from start of day to end of day (NY end as right edge for clarity)
      const datetime right = t_server + (datetime)((InpNYEndHourUTC - InpAsiaEndHourUTC) * 3600);
      const datetime left  = t_server - (datetime)((InpAsiaEndHourUTC - InpAsiaStartHourUTC) * 3600);
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, left, g_day.acc_hi, right, g_day.acc_lo);
      ObjectSetInteger(0, name, OBJPROP_COLOR, InpAccBoxColor);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString (0, name, OBJPROP_TOOLTIP, StringFormat("Accumulation %.5f .. %.5f",
                                                              g_day.acc_hi, g_day.acc_lo));
     }

   if(InpDebugLog)
      PrintFormat("[AMD] ACC locked %s  hi=%.5f  lo=%.5f",
                  TimeToString(t_server, TIME_DATE | TIME_MINUTES),
                  g_day.acc_hi, g_day.acc_lo);
  }

//+------------------------------------------------------------------+
//| Manipulation detection                                            |
//+------------------------------------------------------------------+
void CheckManipulation(const int shift, const datetime t_server)
  {
   const double bh = iHigh (_Symbol, _Period, shift);
   const double bl = iLow  (_Symbol, _Period, shift);
   const double bc = iClose(_Symbol, _Period, shift);

   bool bsl_hit = false;
   bool ssl_hit = false;

   // BSL sweep: high pierces above AccHi, close back inside
   if(bh > g_day.acc_hi)
     {
      if(!InpRequireCloseBack || (bc < g_day.acc_hi && bc > g_day.acc_lo))
         bsl_hit = true;
     }
   // SSL sweep: low pierces below AccLo, close back inside
   if(bl < g_day.acc_lo)
     {
      if(!InpRequireCloseBack || (bc > g_day.acc_lo && bc < g_day.acc_hi))
         ssl_hit = true;
     }

   if(!bsl_hit && !ssl_hit) return;

   // If both fired (rare wide bar), bias toward whichever extreme is further
   SweepSide chosen = SWEEP_NONE;
   double extreme = 0;
   if(bsl_hit && ssl_hit)
     {
      const double over = bh - g_day.acc_hi;
      const double under = g_day.acc_lo - bl;
      if(over >= under) { chosen = SWEEP_BSL; extreme = bh; }
      else              { chosen = SWEEP_SSL; extreme = bl; }
     }
   else if(bsl_hit) { chosen = SWEEP_BSL; extreme = bh; }
   else             { chosen = SWEEP_SSL; extreme = bl; }

   g_day.sweep_side    = chosen;
   g_day.sweep_time    = t_server;
   g_day.sweep_extreme = extreme;
   g_day.state         = STATE_WAIT_FVG;

   if(InpDrawManipMarker)
     {
      const string name = ObjName(StringFormat("MANIP_%d", (int)t_server));
      const double anchor = (chosen == SWEEP_BSL) ? extreme : extreme;
      ObjectCreate(0, name, OBJ_TEXT, 0, t_server, anchor);
      ObjectSetString (0, name, OBJPROP_TEXT, "M");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 12);
      ObjectSetInteger(0, name, OBJPROP_COLOR,
                       chosen == SWEEP_BSL ? InpManipBSLColor : InpManipSSLColor);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR,
                       chosen == SWEEP_BSL ? ANCHOR_LOWER : ANCHOR_UPPER);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
     }

   if(InpDebugLog)
      PrintFormat("[AMD] MANIP %s side=%s extreme=%.5f",
                  TimeToString(t_server, TIME_DATE | TIME_MINUTES),
                  chosen == SWEEP_BSL ? "BSL(short)" : "SSL(long)",
                  extreme);
  }

//+------------------------------------------------------------------+
//| FVG detection (3-candle imbalance, confirmed at idx)              |
//|   shift_idx is the 'C' bar (most recent).                         |
//|   shift_idx + 2 is the 'A' bar (oldest in the trio).              |
//+------------------------------------------------------------------+
bool DetectFvgAt(const int shift_idx, const bool want_bullish,
                 double &out_low, double &out_high)
  {
   const double a_h = iHigh(_Symbol, _Period, shift_idx + 2);
   const double a_l = iLow (_Symbol, _Period, shift_idx + 2);
   const double c_h = iHigh(_Symbol, _Period, shift_idx);
   const double c_l = iLow (_Symbol, _Period, shift_idx);

   if(want_bullish)
     {
      if(c_l > a_h)
        {
         out_low  = a_h;
         out_high = c_l;
         return true;
        }
     }
   else
     {
      if(c_h < a_l)
        {
         out_low  = c_h;
         out_high = a_l;
         return true;
        }
     }
   return false;
  }

void FireFvgSignal(const int shift_idx, const datetime t_server,
                   const bool is_bullish, const double f_lo, const double f_hi)
  {
   g_day.fvg_time     = t_server;
   g_day.fvg_low      = f_lo;
   g_day.fvg_high     = f_hi;
   g_day.state        = STATE_DONE;
   g_day.sequences_today++;

   const datetime mid_bar_time = iTime(_Symbol, _Period, shift_idx + 1);

   if(InpDrawFvgBox)
     {
      const string name = ObjName(StringFormat("FVG_%d", (int)t_server));
      const datetime right = t_server +
         (datetime)(InpFvgBoxBars * PeriodSeconds(_Period));
      ObjectCreate(0, name, OBJ_RECTANGLE, 0,
                   mid_bar_time, f_hi, right, f_lo);
      ObjectSetInteger(0, name, OBJPROP_COLOR,
                       is_bullish ? InpFvgBullColor : InpFvgBearColor);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString (0, name, OBJPROP_TOOLTIP,
                       StringFormat("FVG %.5f .. %.5f (%s)",
                                    f_lo, f_hi, is_bullish ? "bullish" : "bearish"));
     }

   if(InpDrawSignalArrow)
     {
      const string aname = ObjName(StringFormat("ARR_%d", (int)t_server));
      const double anchor = is_bullish ? iLow(_Symbol, _Period, shift_idx)
                                       : iHigh(_Symbol, _Period, shift_idx);
      ObjectCreate(0, aname, OBJ_ARROW, 0, t_server, anchor);
      ObjectSetInteger(0, aname, OBJPROP_ARROWCODE, is_bullish ? 233 : 234);
      ObjectSetInteger(0, aname, OBJPROP_COLOR,
                       is_bullish ? InpSignalLongColor : InpSignalShortColor);
      ObjectSetInteger(0, aname, OBJPROP_WIDTH, 3);
      ObjectSetInteger(0, aname, OBJPROP_ANCHOR,
                       is_bullish ? ANCHOR_TOP : ANCHOR_BOTTOM);
      ObjectSetInteger(0, aname, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, aname, OBJPROP_SELECTABLE, false);
     }

   const string label = is_bullish ? "AMD-UP" : "AMD-DOWN";
   const string lname = ObjName(StringFormat("LBL_%d", (int)t_server));
   ObjectCreate(0, lname, OBJ_TEXT, 0, t_server,
                is_bullish ? iLow(_Symbol, _Period, shift_idx)
                           : iHigh(_Symbol, _Period, shift_idx));
   ObjectSetString (0, lname, OBJPROP_TEXT, label);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE, 10);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,
                    is_bullish ? InpSignalLongColor : InpSignalShortColor);
   ObjectSetInteger(0, lname, OBJPROP_ANCHOR,
                    is_bullish ? ANCHOR_UPPER : ANCHOR_LOWER);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);

   const string msg = StringFormat("[%s %s] AMD complete: %s on %s @ %s",
                                   _Symbol,
                                   EnumToString((ENUM_TIMEFRAMES)_Period),
                                   label,
                                   TimeToString(t_server, TIME_DATE | TIME_MINUTES),
                                   DoubleToString(iClose(_Symbol, _Period, shift_idx), _Digits));
   if(InpAlertPopup) Alert(msg);
   if(InpAlertSound) PlaySound(InpAlertSoundFile);
   if(InpAlertPush)  SendNotification(msg);
   if(InpAlertEmail) SendMail("AMD signal", msg);
   if(InpDebugLog)   Print(msg);
  }

void CheckFvg(const int shift_idx, const datetime t_server)
  {
   // FVG only valid in trade direction implied by sweep
   const bool want_bullish = (g_day.sweep_side == SWEEP_SSL);

   double f_lo, f_hi;
   if(!DetectFvgAt(shift_idx, want_bullish, f_lo, f_hi))
      return;

   FireFvgSignal(shift_idx, t_server, want_bullish, f_lo, f_hi);

   if(g_day.sequences_today >= InpMaxSequencesPerDay)
      g_day.state = STATE_DONE;
  }

//+------------------------------------------------------------------+
//| Per-bar evaluator. Caller provides shift to the just-closed bar   |
//| (= 1 for live ticks; 0 indexing also handled in OnCalculate).     |
//+------------------------------------------------------------------+
void EvaluateBar(const int shift)
  {
   const datetime t_server = iTime(_Symbol, _Period, shift);
   if(t_server == 0) return;

   const datetime t_utc       = ServerToUtc(t_server);
   const datetime day_start   = DayStartUtc(t_utc);
   const int      hour        = UtcHour(t_server);

   //--- new UTC day -> reset state
   if(g_day.day_utc_start != day_start)
      ResetDayState(day_start);

   //--- past NY end without a sequence -> invalidate
   if(g_day.state != STATE_DONE && g_day.state != STATE_INVALIDATED &&
      hour >= InpNYEndHourUTC)
     {
      g_day.state = STATE_INVALIDATED;
      return;
     }

   //--- accumulate
   if(g_day.state == STATE_WAIT_ACC)
     {
      if(InWindow(hour, InpAsiaStartHourUTC, InpAsiaEndHourUTC))
         UpdateAccumulation(shift);
      else if(hour >= InpAsiaEndHourUTC && hour < InpLondonEndHourUTC &&
              g_day.acc_hi > 0 && g_day.acc_lo > 0)
         LockAccumulation(t_server);
      return;
     }

   //--- manipulation
   if(g_day.state == STATE_WAIT_MANIP)
     {
      if(hour >= InpAsiaEndHourUTC && hour < InpLondonEndHourUTC)
         CheckManipulation(shift, t_server);
      else if(hour >= InpLondonEndHourUTC)
        {
         // London window closed without a sweep: invalidate for the day
         g_day.state = STATE_INVALIDATED;
         if(InpDebugLog)
            PrintFormat("[AMD] no sweep before %02d UTC -> INVALIDATED", InpLondonEndHourUTC);
        }
      return;
     }

   //--- FVG
   if(g_day.state == STATE_WAIT_FVG)
     {
      if(hour >= InpLondonEndHourUTC && hour < InpNYEndHourUTC)
         CheckFvg(shift, t_server);
      return;
     }
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                        |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 4) return rates_total;

   // Walk closed bars only. Shift 1 = most recent closed bar.
   // On first pass, replay the recent history so visuals match.
   if(prev_calculated == 0)
     {
      // Replay last ~5 days worth of closed bars (cheap).
      const int replay = MathMin(rates_total - 2, 2880);
      for(int sh = replay; sh >= 1; sh--)
         EvaluateBar(sh);
      g_last_evaluated_bar = iTime(_Symbol, _Period, 1);
      return rates_total;
     }

   const datetime t1 = iTime(_Symbol, _Period, 1);
   if(t1 != 0 && t1 != g_last_evaluated_bar)
     {
      EvaluateBar(1);
      g_last_evaluated_bar = t1;
     }
   return rates_total;
  }
//+------------------------------------------------------------------+
