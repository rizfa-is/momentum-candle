//+------------------------------------------------------------------+
//|                                     MomentumCandleBacktest.mq5   |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Backtest harness EA for the two momentum-candle variants.        |
//|                                                                  |
//| Strategy Tester usage:                                           |
//|   * Symbol = XAUUSD (or your default), period = M5/M15/H1.       |
//|   * Model  = "Every tick based on real ticks" (most accurate)    |
//|              or "1-minute OHLC" for a faster pass.               |
//|   * Set InpVariant input to choose which indicator to load:      |
//|       VIDEO -> MomentumCandle_Video                              |
//|       PROXY -> MomentumCandle_Proxy                              |
//|   * Set TP target via InpUseTp1 (true=candle high, false=1.27).  |
//|                                                                  |
//| The EA reads the Direction and Confidence buffers via iCustom    |
//| from the chosen indicator. On a NEW non-zero direction, it opens |
//| a market trade with the indicator's recommended SL and TP. One   |
//| position at a time; multiple entries are dropped.                |
//|                                                                  |
//| All trades are tagged with Magic so results are isolated per     |
//| Strategy Tester run.                                              |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <MomentumCandleCommon.mqh>

enum MC_Variant
  {
   VARIANT_VIDEO = 0,
   VARIANT_PROXY = 1,
  };

input MC_Variant InpVariant       = VARIANT_VIDEO;     // Indicator variant to backtest
input double     InpLotSize       = 0.01;              // Fixed lot size
input bool       InpUseTp1        = true;              // true=use candle high (TP1), false=1.27 ext (TP2)
input double     InpMinConfidence = 0.50;              // Skip setups below this confidence
input int        InpMagic         = 901001;            // Magic number for this EA
input string     InpComment       = "MC-backtest";    // Trade comment
input bool       InpOnlyOnePos    = true;              // Only one position at a time

//--- inputs forwarded to the indicator -----------------------------
input group "Indicator parameters (must match indicator inputs)"
input double InpMinBodyPct      = 0.70;
input double InpMaxCloseWickPct = 0.10;
input int    InpLocalLookback   = 5;     // VIDEO variant only
input double InpRangeMult       = 1.5;   // VIDEO: range/local mean ; PROXY: range/ATR
input int    InpAtrPeriod       = 14;    // PROXY variant only
input int    InpVolSmaPeriod    = 20;    // PROXY variant only
input double InpVolMult         = 1.5;
input bool   InpEntryOnNextOpen = true;

//--- runtime -------------------------------------------------------
CTrade   g_trade;
int      g_ind_handle = INVALID_HANDLE;
datetime g_last_seen_bar = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFilling(ORDER_FILLING_FOK);
   g_trade.SetDeviationInPoints(50);

   const string ind_name = (InpVariant == VARIANT_VIDEO)
                           ? "MomentumCandle_Video"
                           : "MomentumCandle_Proxy";

   if(InpVariant == VARIANT_VIDEO)
     {
      g_ind_handle = iCustom(_Symbol, _Period, ind_name,
                             InpMinBodyPct,
                             InpMaxCloseWickPct,
                             InpLocalLookback,
                             InpRangeMult,
                             InpVolMult,
                             InpMinConfidence,
                             InpEntryOnNextOpen,
                             /*InpDrawLevels*/ false,
                             /*InpAlertOnNew*/ false,
                             /*InpMaxLabels*/ 5,
                             /*InpObjectPrefix*/ "MCV_");
     }
   else
     {
      g_ind_handle = iCustom(_Symbol, _Period, ind_name,
                             InpMinBodyPct,
                             InpMaxCloseWickPct,
                             InpAtrPeriod,
                             InpRangeMult,
                             InpVolSmaPeriod,
                             InpVolMult,
                             InpMinConfidence,
                             InpEntryOnNextOpen,
                             /*InpDrawLevels*/ false,
                             /*InpAlertOnNew*/ false,
                             /*InpMaxLabels*/ 5,
                             /*InpObjectPrefix*/ "MCP_");
     }

   if(g_ind_handle == INVALID_HANDLE)
     {
      Print("Failed to create iCustom handle for ", ind_name, " err=", GetLastError());
      return INIT_FAILED;
     }
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_ind_handle != INVALID_HANDLE)
     {
      IndicatorRelease(g_ind_handle);
      g_ind_handle = INVALID_HANDLE;
     }
  }

//+------------------------------------------------------------------+
//| OnTick — act once per new bar.                                   |
//+------------------------------------------------------------------+
void OnTick()
  {
   const datetime t1 = iTime(_Symbol, _Period, 1);
   if(t1 == 0 || t1 == g_last_seen_bar) return;
   g_last_seen_bar = t1;

   if(InpOnlyOnePos && CountOpenPositions() > 0) return;

   //--- read the indicator's buffers at shift=1 (last closed bar) -
   double dir_buf[1];
   double conf_buf[1];
   // Buffer 2 = direction, buffer 3 = confidence (calculation buffers).
   if(CopyBuffer(g_ind_handle, 2, 1, 1, dir_buf)  != 1) return;
   if(CopyBuffer(g_ind_handle, 3, 1, 1, conf_buf) != 1) return;

   const double dir  = dir_buf[0];
   const double conf = conf_buf[0];
   if(dir == 0.0) return;
   if(conf < InpMinConfidence) return;

   //--- recompute SL/TP from the trigger candle's OHLC -----------
   const double t_open  = iOpen (_Symbol, _Period, 1);
   const double t_high  = iHigh (_Symbol, _Period, 1);
   const double t_low   = iLow  (_Symbol, _Period, 1);
   const double t_close = iClose(_Symbol, _Period, 1);
   const double rng = t_high - t_low;
   if(rng <= 0.0) return;

   double sl, tp;
   ENUM_ORDER_TYPE side;
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(dir > 0.0)
     {
      side = ORDER_TYPE_BUY;
      sl   = t_low  - 0.10 * rng;
      tp   = InpUseTp1 ? t_high : (t_high + 0.27 * rng);
     }
   else
     {
      side = ORDER_TYPE_SELL;
      sl   = t_high + 0.10 * rng;
      tp   = InpUseTp1 ? t_low  : (t_low  - 0.27 * rng);
     }

   //--- guard against invalid stop levels (broker minimum) -------
   const long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double min_dist  = stops_level * point;

   const double price = (side == ORDER_TYPE_BUY) ? ask : bid;
   if(MathAbs(price - sl) < min_dist) return;
   if(MathAbs(tp    - price) < min_dist) return;

   //--- normalise lot size against broker constraints ------------
   const double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double vstp = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lot = InpLotSize;
   if(lot < vmin) lot = vmin;
   if(lot > vmax) lot = vmax;
   if(vstp > 0.0)
      lot = MathFloor(lot / vstp) * vstp;
   if(lot <= 0.0) return;

   //--- send -----------------------------------------------------
   const string c = StringFormat("%s/%s", InpComment,
                                 (InpVariant == VARIANT_VIDEO) ? "video" : "proxy");
   if(side == ORDER_TYPE_BUY)
      g_trade.Buy(lot, _Symbol, ask, sl, tp, c);
   else
      g_trade.Sell(lot, _Symbol, bid, sl, tp, c);
  }

//+------------------------------------------------------------------+
int CountOpenPositions()
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
