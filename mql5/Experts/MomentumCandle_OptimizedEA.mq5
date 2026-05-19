//+------------------------------------------------------------------+
//|                                MomentumCandle_OptimizedEA.mq5    |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Self-contained EA implementing the deployable strategy from the  |
//| 5-month multi-month backtest.                                    |
//|                                                                  |
//| Strategy summary (optimized_no_round + pullback_236 + cap=1):    |
//|                                                                  |
//|   FILTER (7 rules, all must pass on a CLOSED candle):            |
//|     1. body / range          >= InpMinBodyPct       (0.86)       |
//|     2. close-side wick / range <= InpMaxCloseWickPct (0.10)      |
//|     3. far-side wick / range  <= InpMaxFarWickPct   (0.05)       |
//|     4. body in price points  >= InpMinBodyPoints    (1000)       |
//|     5. range in USD          >= InpMinRangeUsd      (11.0)       |
//|     6. session UTC           != London (08-12 UTC)               |
//|     7. trend_monotonic_prior_7 <= InpMaxMonotonic   (4)          |
//|                                                                  |
//|   ENTRY: limit order at 23.6% fib retracement of signal candle.  |
//|     Canceled if not filled within InpPullbackBars   (10) bars.   |
//|                                                                  |
//|   EXIT: TP at 1.27 fib extension, SL at -0.10 below candle low   |
//|     (mirror for SELL). Time stop at InpMaxHoldMinutes (30).      |
//|                                                                  |
//|   POSITION CAP: max 1 simultaneous position with this magic.     |
//|                                                                  |
//| Backtest support: 5-month aggregate (Jan-May 2026, n=189):       |
//|   WR 72.5%, PF 1.54, +0.149R per trade gross.                    |
//|   After ~0.10R/trade spread cost: +0.05R per trade net.          |
//|   ~38 trades/month average, ~1 losing month per 5.               |
//|                                                                  |
//| Run on XAUUSD M5 only at the verified parameters. Other          |
//| symbols / timeframes have not been tested.                       |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//--- inputs --------------------------------------------------------
input group "Filter (signal qualification)"
input double InpMinBodyPct       = 0.86;   // Min body / range
input double InpMaxCloseWickPct  = 0.10;   // Max close-side wick / range
input double InpMaxFarWickPct    = 0.05;   // Max far-side (opposite) wick / range
input double InpMinBodyPoints    = 1000;   // Min body in price points
input double InpMinRangeUsd      = 11.0;   // Min range (high-low) in USD
input bool   InpUseSessionFilter = true;   // Skip London window
input int    InpAsiaStartHourUTC = 23;     // Asia start (UTC)
input int    InpAsiaEndHourUTC   = 8;
input int    InpNYStartHourUTC   = 12;
input int    InpNYEndHourUTC     = 22;
input int    InpMaxMonotonic     = 4;      // Max trend_monotonic_prior_7

input group "Entry / exit"
input int    InpPullbackBars     = 10;     // Pullback limit lifetime in bars
input int    InpMaxHoldMinutes   = 30;     // Hard time-stop in minutes
input double InpRiskPercent      = 1.0;    // Account % to risk per trade (0 = use fixed lot)
input double InpFixedLot         = 0.10;   // Fixed lot when InpRiskPercent = 0
input double InpMaxLotSize       = 1.00;   // Hard ceiling on calculated lot

input group "Misc"
input long   InpMagic            = 920001; // Magic number
input string InpComment          = "MC-Opt"; // Trade comment prefix
input bool   InpDebugLog         = false;  // Verbose journal logging

//--- runtime -------------------------------------------------------
CTrade   g_trade;
datetime g_last_seen_bar = 0;

//--- pending pullback state (only one trade at a time) -------------
struct PendingTrade
  {
   bool       active;
   datetime   trigger_time;
   int        bars_remaining;
   string     side;           // "BUY" or "SELL"
   double     candle_low;
   double     candle_high;
   double     candle_range;
   double     entry_price;    // 23.6 retracement
   double     sl;
   double     tp;
  };

PendingTrade g_pending = {false, 0, 0, "", 0, 0, 0, 0, 0, 0};

//+------------------------------------------------------------------+
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_pending.active = false;
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
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

int CountOwnPositions()
  {
   int n = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| Compute body in price points (uses SYMBOL_POINT)                 |
//+------------------------------------------------------------------+
double BodyInPoints(const double body)
  {
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) return 0.0;
   return body / point;
  }

//+------------------------------------------------------------------+
//| TrendMonotonicCount -- count of prior 7 close-to-close            |
//| transitions matching `direction` (BUY = up moves, SELL = down).  |
//+------------------------------------------------------------------+
int TrendMonotonicCount(const string direction, const int trigger_shift)
  {
   // shifts trigger+1 .. trigger+8 = 8 bars, 7 transitions
   int count = 0;
   for(int k = 1; k <= 7; k++)
     {
      const double newer = iClose(_Symbol, _Period, trigger_shift + k);
      const double older = iClose(_Symbol, _Period, trigger_shift + k + 1);
      if(direction == "BUY"  && newer > older) count++;
      if(direction == "SELL" && newer < older) count++;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Filter check on the bar at `shift`. Returns side or "".          |
//+------------------------------------------------------------------+
string EvaluateFilter(const int shift)
  {
   const double o   = iOpen (_Symbol, _Period, shift);
   const double h   = iHigh (_Symbol, _Period, shift);
   const double lo  = iLow  (_Symbol, _Period, shift);
   const double c   = iClose(_Symbol, _Period, shift);
   const double rng = h - lo;
   if(rng <= 0.0) return "";

   const double body = MathAbs(c - o);
   const double body_pct = body / rng;

   string side = "";
   if(c > o) side = "BUY";
   else if(c < o) side = "SELL";
   else return "";

   const double close_wick = (side == "BUY") ? (h - c) : (c - lo);
   const double far_wick   = (side == "BUY") ? (o - lo) : (h - o);
   const double cwick_pct  = close_wick / rng;
   const double fwick_pct  = far_wick / rng;

   if(body_pct  < InpMinBodyPct)      return "";
   if(cwick_pct > InpMaxCloseWickPct) return "";
   if(fwick_pct > InpMaxFarWickPct)   return "";
   if(BodyInPoints(body) < InpMinBodyPoints) return "";
   if(rng < InpMinRangeUsd) return "";
   if(!InActiveSession(iTime(_Symbol, _Period, shift))) return "";
   if(TrendMonotonicCount(side, shift) > InpMaxMonotonic) return "";

   return side;
  }

//+------------------------------------------------------------------+
//| Calculate lot size based on risk model                            |
//+------------------------------------------------------------------+
double CalcLotSize(const double sl_distance)
  {
   if(InpRiskPercent <= 0.0)
      return NormalizeLot(InpFixedLot);

   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   const double risk_money = balance * InpRiskPercent / 100.0;

   const double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0 || tick_value <= 0 || sl_distance <= 0) return NormalizeLot(InpFixedLot);

   const double money_per_lot_per_dist = (sl_distance / tick_size) * tick_value;
   if(money_per_lot_per_dist <= 0) return NormalizeLot(InpFixedLot);

   double lots = risk_money / money_per_lot_per_dist;
   if(lots > InpMaxLotSize) lots = InpMaxLotSize;
   return NormalizeLot(lots);
  }

double NormalizeLot(const double raw)
  {
   const double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double vstp = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lot = raw;
   if(lot < vmin) lot = vmin;
   if(lot > vmax) lot = vmax;
   if(vstp > 0.0)
      lot = MathFloor(lot / vstp) * vstp;
   return lot;
  }

//+------------------------------------------------------------------+
//| Try to fill the pending pullback on the live tick                 |
//+------------------------------------------------------------------+
void TryFillPending()
  {
   if(!g_pending.active) return;

   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   bool fill = false;
   if(g_pending.side == "BUY" && ask <= g_pending.entry_price) fill = true;
   if(g_pending.side == "SELL" && bid >= g_pending.entry_price) fill = true;
   if(!fill) return;

   if(CountOwnPositions() > 0)
     {
      // somehow already in a position; abort
      g_pending.active = false;
      return;
     }

   const double sl_distance = MathAbs(g_pending.entry_price - g_pending.sl);
   const double lot = CalcLotSize(sl_distance);
   if(lot <= 0.0) { g_pending.active = false; return; }

   const long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double min_dist  = stops_level * point;
   const double live_price = (g_pending.side == "BUY") ? ask : bid;
   if(MathAbs(live_price - g_pending.sl) < min_dist) { g_pending.active = false; return; }
   if(MathAbs(g_pending.tp - live_price) < min_dist) { g_pending.active = false; return; }

   const string c = StringFormat("%s/%s", InpComment, g_pending.side);
   bool ok = false;
   if(g_pending.side == "BUY")
      ok = g_trade.Buy(lot, _Symbol, ask, g_pending.sl, g_pending.tp, c);
   else
      ok = g_trade.Sell(lot, _Symbol, bid, g_pending.sl, g_pending.tp, c);

   if(InpDebugLog)
      PrintFormat("[MC-Opt] %s fill at %s -> %s lot=%.2f SL=%s TP=%s ok=%d",
                  g_pending.side,
                  DoubleToString(live_price, _Digits),
                  DoubleToString(g_pending.entry_price, _Digits),
                  lot,
                  DoubleToString(g_pending.sl, _Digits),
                  DoubleToString(g_pending.tp, _Digits),
                  ok);

   g_pending.active = false;
  }

//+------------------------------------------------------------------+
//| Force-close positions older than InpMaxHoldMinutes                |
//+------------------------------------------------------------------+
void EnforceTimeStops()
  {
   if(InpMaxHoldMinutes <= 0) return;
   const datetime now = TimeCurrent();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      const datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(now - opened >= InpMaxHoldMinutes * 60)
        {
         g_trade.PositionClose(ticket);
         if(InpDebugLog)
            PrintFormat("[MC-Opt] time-stop close ticket=%I64u opened=%s now=%s",
                        ticket,
                        TimeToString(opened, TIME_DATE | TIME_MINUTES),
                        TimeToString(now, TIME_DATE | TIME_MINUTES));
        }
     }
  }

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
  {
   //--- enforce time-stop on every tick ---------------------------
   EnforceTimeStops();

   //--- try to fill any pending pullback on every tick -----------
   TryFillPending();

   //--- once per new bar: evaluate the most-recently-closed bar --
   const datetime t1 = iTime(_Symbol, _Period, 1);
   if(t1 == 0 || t1 == g_last_seen_bar) return;
   g_last_seen_bar = t1;

   // Decrement pullback bar countdown
   if(g_pending.active)
     {
      g_pending.bars_remaining--;
      if(g_pending.bars_remaining <= 0)
        {
         if(InpDebugLog)
            PrintFormat("[MC-Opt] pullback expired without fill (%s @ %s)",
                        g_pending.side,
                        DoubleToString(g_pending.entry_price, _Digits));
         g_pending.active = false;
        }
     }

   //--- only one position at a time -------------------------------
   if(CountOwnPositions() > 0) return;
   if(g_pending.active) return;

   //--- evaluate filter on bar shift=1 (last closed bar) ---------
   const string side = EvaluateFilter(1);
   if(side == "") return;

   const double H = iHigh(_Symbol, _Period, 1);
   const double L = iLow (_Symbol, _Period, 1);
   const double rng = H - L;

   //--- arm a pullback limit at 23.6 retracement -----------------
   if(side == "BUY")
     {
      g_pending.entry_price = H - 0.236 * rng;
      g_pending.sl = L - 0.10 * rng;
      g_pending.tp = H + 0.27 * rng;
     }
   else
     {
      g_pending.entry_price = L + 0.236 * rng;
      g_pending.sl = H + 0.10 * rng;
      g_pending.tp = L - 0.27 * rng;
     }
   g_pending.side = side;
   g_pending.candle_low = L;
   g_pending.candle_high = H;
   g_pending.candle_range = rng;
   g_pending.trigger_time = t1;
   g_pending.bars_remaining = InpPullbackBars;
   g_pending.active = true;

   if(InpDebugLog)
      PrintFormat("[MC-Opt] arm %s @ %s SL=%s TP=%s (%d bars to fill)",
                  side,
                  DoubleToString(g_pending.entry_price, _Digits),
                  DoubleToString(g_pending.sl, _Digits),
                  DoubleToString(g_pending.tp, _Digits),
                  InpPullbackBars);
  }
