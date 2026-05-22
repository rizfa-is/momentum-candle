//+------------------------------------------------------------------+
//|                                              LuxAlgo_SMC.mq5     |
//|                                          momentum-candle project |
//|                Port of LuxAlgo "Smart Money Concepts" Pine v5    |
//|       https://www.tradingview.com (CC BY-NC-SA 4.0, LuxAlgo)     |
//+------------------------------------------------------------------+
//| Faithful MQL5 reimplementation of the LuxAlgo SMC Pine v5        |
//| indicator. Renders:                                              |
//|   * Internal & swing market structure (BOS / CHoCH)              |
//|   * Strong / Weak high-low trailing extremes                     |
//|   * Internal & swing order blocks (mitigated on Close or H/L)    |
//|   * Equal highs / lows (EQH / EQL) connector lines               |
//|   * Fair value gaps with auto-threshold and full MTF support     |
//|   * Daily / Weekly / Monthly previous-period high & low          |
//|   * Premium / Discount / Equilibrium zones                       |
//|   * Color-the-candles by internal trend bias                     |
//|                                                                  |
//| EA consumption                                                   |
//|   Buffers 5-7 expose internal bias / swing bias / event code so  |
//|   an EA can iCustom the indicator. Custom chart events fire on   |
//|   each detection (codes 1001-1016) so an EA can listen via       |
//|   OnChartEvent without polling buffers.                          |
//+------------------------------------------------------------------+

#property copyright "Port: momentum-candle project | Original: LuxAlgo (CC BY-NC-SA 4.0)"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_buffers 8
#property indicator_plots   1

#property indicator_label1  "SMC"
#property indicator_type1   DRAW_COLOR_CANDLES
#property indicator_color1  clrSeaGreen, clrFireBrick, clrSilver

//---------------------------------------------------------------------
// Enums
//---------------------------------------------------------------------

enum ENUM_SMC_MODE
  {
   SMC_HISTORICAL = 0, // Historical
   SMC_PRESENT    = 1  // Present
  };

enum ENUM_SMC_STYLE
  {
   SMC_COLORED    = 0, // Colored
   SMC_MONOCHROME = 1  // Monochrome
  };

enum ENUM_SMC_STRUCT
  {
   SMC_STRUCT_ALL   = 0, // All
   SMC_STRUCT_BOS   = 1, // BOS only
   SMC_STRUCT_CHOCH = 2  // CHoCH only
  };

enum ENUM_SMC_LBL
  {
   SMC_LBL_TINY   = 0, // Tiny  (8pt)
   SMC_LBL_SMALL  = 1, // Small (10pt)
   SMC_LBL_NORMAL = 2  // Normal (12pt)
  };

enum ENUM_SMC_OB_FILTER
  {
   SMC_OB_ATR   = 0, // ATR(200)
   SMC_OB_RANGE = 1  // Cumulative Mean Range
  };

enum ENUM_SMC_OB_MITIG
  {
   SMC_OB_CLOSE   = 0, // Close
   SMC_OB_HIGHLOW = 1  // High/Low
  };

enum ENUM_SMC_LINESTYLE
  {
   SMC_LSTYLE_SOLID  = 0, // Solid
   SMC_LSTYLE_DASHED = 1, // Dashed
   SMC_LSTYLE_DOTTED = 2  // Dotted
  };

//---------------------------------------------------------------------
// Inputs
//---------------------------------------------------------------------

input group "=== Smart Money Concepts ==="
input ENUM_SMC_MODE  InpMode      = SMC_HISTORICAL; // Mode
input ENUM_SMC_STYLE InpStyle     = SMC_COLORED;    // Style
input bool           InpShowTrend = false;          // Color Candles

input group "=== Real Time Internal Structure ==="
input bool           InpShowInternals       = true;            // Show Internal Structure
input ENUM_SMC_STRUCT InpInternalBullFilter = SMC_STRUCT_ALL;  // Bullish Structure
input color          InpInternalBullColor   = clrSeaGreen;     // Internal Bullish Color
input ENUM_SMC_STRUCT InpInternalBearFilter = SMC_STRUCT_ALL;  // Bearish Structure
input color          InpInternalBearColor   = clrFireBrick;    // Internal Bearish Color
input bool           InpInternalConfluence  = false;           // Confluence Filter
input ENUM_SMC_LBL   InpInternalLabelSize   = SMC_LBL_TINY;    // Internal Label Size

input group "=== Real Time Swing Structure ==="
input bool           InpShowStructure     = true;            // Show Swing Structure
input ENUM_SMC_STRUCT InpSwingBullFilter  = SMC_STRUCT_ALL;  // Swing Bullish Structure
input color          InpSwingBullColor    = clrSeaGreen;     // Swing Bullish Color
input ENUM_SMC_STRUCT InpSwingBearFilter  = SMC_STRUCT_ALL;  // Swing Bearish Structure
input color          InpSwingBearColor    = clrFireBrick;    // Swing Bearish Color
input ENUM_SMC_LBL   InpSwingLabelSize    = SMC_LBL_SMALL;   // Swing Label Size
input bool           InpShowSwings        = false;           // Show Swing Points (HH/HL/LH/LL)
input int            InpSwingsLength      = 50;              // Swing Length (>=10)
input bool           InpShowHighLowSwings = true;            // Show Strong/Weak High/Low

input group "=== Order Blocks ==="
input bool             InpShowInternalOrderBlocks = true;            // Show Internal OBs
input int              InpInternalOrderBlocksSize = 5;               // Internal OBs to display (1..20)
input bool             InpShowSwingOrderBlocks    = false;           // Show Swing OBs
input int              InpSwingOrderBlocksSize    = 5;               // Swing OBs to display (1..20)
input ENUM_SMC_OB_FILTER InpOrderBlockFilter      = SMC_OB_ATR;      // Volatility Measure
input ENUM_SMC_OB_MITIG  InpOrderBlockMitigation  = SMC_OB_HIGHLOW;  // OB Mitigation
input color            InpInternalBullishOBColor  = C'49,121,245';   // Internal Bullish OB
input color            InpInternalBearishOBColor  = C'247,124,128';  // Internal Bearish OB
input color            InpSwingBullishOBColor     = C'24,72,204';    // Swing Bullish OB
input color            InpSwingBearishOBColor     = C'178,40,51';    // Swing Bearish OB

input group "=== EQH / EQL ==="
input bool         InpShowEqualHighsLows      = true;          // Show Equal H/L
input int          InpEqualHighsLowsLength    = 3;             // Bars Confirmation
input double       InpEqualHighsLowsThreshold = 0.1;           // Threshold (0..0.5)
input ENUM_SMC_LBL InpEqualLabelSize          = SMC_LBL_TINY;  // EQH/EQL Label Size

input group "=== Fair Value Gaps ==="
input bool             InpShowFairValueGaps           = false;           // Show FVGs
input bool             InpFairValueGapsAutoThreshold  = true;            // Auto Threshold
input ENUM_TIMEFRAMES  InpFairValueGapsTimeframe      = PERIOD_CURRENT;  // FVG Timeframe (MTF)
input color            InpFairValueGapsBullColor      = C'0,255,104';    // Bullish FVG
input color            InpFairValueGapsBearColor      = C'255,0,8';      // Bearish FVG
input int              InpFairValueGapsExtend         = 1;               // Extend FVG bars (>=0)

input group "=== Highs & Lows MTF ==="
input bool               InpShowDailyLevels    = false;             // Show Daily levels
input ENUM_SMC_LINESTYLE InpDailyLevelsStyle   = SMC_LSTYLE_SOLID;  // Daily style
input color              InpDailyLevelsColor   = clrRoyalBlue;      // Daily color
input bool               InpShowWeeklyLevels   = false;             // Show Weekly levels
input ENUM_SMC_LINESTYLE InpWeeklyLevelsStyle  = SMC_LSTYLE_SOLID;  // Weekly style
input color              InpWeeklyLevelsColor  = clrRoyalBlue;      // Weekly color
input bool               InpShowMonthlyLevels  = false;             // Show Monthly levels
input ENUM_SMC_LINESTYLE InpMonthlyLevelsStyle = SMC_LSTYLE_SOLID;  // Monthly style
input color              InpMonthlyLevelsColor = clrRoyalBlue;      // Monthly color

input group "=== Premium & Discount Zones ==="
input bool  InpShowPremiumDiscountZones = false;        // Show Zones
input color InpPremiumZoneColor         = clrFireBrick; // Premium
input color InpEquilibriumZoneColor     = clrGray;      // Equilibrium
input color InpDiscountZoneColor        = clrSeaGreen;  // Discount

input group "=== Misc ==="
input string InpObjPrefix = "SMC_";  // Object name prefix (must be unique per chart)
input bool   InpDebugLog  = false;   // Verbose log to Experts journal


//+------------------------------------------------------------------+
//| Constants & event codes                                          |
//+------------------------------------------------------------------+
#define SMC_BIAS_BULLISH      ( 1)
#define SMC_BIAS_BEARISH      (-1)
#define SMC_BIAS_NONE         ( 0)

#define SMC_LEG_BULLISH       (1)
#define SMC_LEG_BEARISH       (0)

#define SMC_EVT_INT_BULL_BOS    1001
#define SMC_EVT_INT_BEAR_BOS    1002
#define SMC_EVT_INT_BULL_CHOCH  1003
#define SMC_EVT_INT_BEAR_CHOCH  1004
#define SMC_EVT_SWG_BULL_BOS    1005
#define SMC_EVT_SWG_BEAR_BOS    1006
#define SMC_EVT_SWG_BULL_CHOCH  1007
#define SMC_EVT_SWG_BEAR_CHOCH  1008
#define SMC_EVT_INT_OB_BULL_MIT 1009
#define SMC_EVT_INT_OB_BEAR_MIT 1010
#define SMC_EVT_SWG_OB_BULL_MIT 1011
#define SMC_EVT_SWG_OB_BEAR_MIT 1012
#define SMC_EVT_EQH             1013
#define SMC_EVT_EQL             1014
#define SMC_EVT_FVG_BULL        1015
#define SMC_EVT_FVG_BEAR        1016

#define SMC_MAX_OB_HISTORY      100
#define SMC_MAX_FVG_HISTORY     200

//+------------------------------------------------------------------+
//| Data structures                                                  |
//+------------------------------------------------------------------+
struct SMCPivot
  {
   double currentLevel;
   double lastLevel;
   bool   crossed;
   datetime barTime;
   int    barIndex;        // bar index relative to indicator's processed bars
  };

struct SMCTrailing
  {
   double  top;
   double  bottom;
   datetime barTime;
   int     barIndex;
   datetime lastTopTime;
   datetime lastBottomTime;
  };

struct SMCOrderBlock
  {
   double   barHigh;
   double   barLow;
   datetime barTime;
   int      bias;          // SMC_BIAS_BULLISH or SMC_BIAS_BEARISH
   string   objName;       // chart object name (rectangle), empty until drawn
   bool     active;        // false once mitigated
  };

struct SMCFairValueGap
  {
   double   top;
   double   bottom;
   int      bias;
   datetime leftTime;
   datetime rightTime;
   string   topBoxName;
   string   bottomBoxName;
   bool     active;
  };

struct SMCEqualDisplay
  {
   string lineName;
   string labelName;
  };

//+------------------------------------------------------------------+
//| Indicator buffers                                                |
//+------------------------------------------------------------------+
double bufOpen[];
double bufHigh[];
double bufLow[];
double bufClose[];
double bufColor[];
double bufInternalBias[];
double bufSwingBias[];
double bufEventCode[];

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
SMCPivot    g_swingHigh;
SMCPivot    g_swingLow;
SMCPivot    g_internalHigh;
SMCPivot    g_internalLow;
SMCPivot    g_equalHigh;
SMCPivot    g_equalLow;

int         g_swingTrend     = SMC_BIAS_NONE;
int         g_internalTrend  = SMC_BIAS_NONE;

SMCTrailing g_trailing;

SMCOrderBlock    g_internalOBs[];
SMCOrderBlock    g_swingOBs[];

SMCFairValueGap  g_fvgs[];

SMCEqualDisplay  g_equalHighDisplay;
SMCEqualDisplay  g_equalLowDisplay;

// Parsed arrays (Pine: parsedHighs / parsedLows / highs / lows / times)
// Indexed in ascending chronological order (rates_total order, not series).
double      g_parsedHighs[];
double      g_parsedLows[];
double      g_highs[];
double      g_lows[];
datetime    g_times[];

// Bar handles for ATR(200)
int         g_atrHandle = INVALID_HANDLE;

// Cached state for re-entrancy and partial computation
int         g_lastProcessedBars = 0;
datetime    g_initialTime       = 0;

// MTF FVG -- track the last completed bar time on the user-selected TF
datetime    g_fvgLastTfBarTime = 0;

//+------------------------------------------------------------------+
//| Helpers: object name composition                                 |
//+------------------------------------------------------------------+
string SMCObj(const string suffix)
  {
   return InpObjPrefix + suffix;
  }

string SMCObjUnique(const string family, const long counter)
  {
   return StringFormat("%s%s_%I64d", InpObjPrefix, family, counter);
  }

//+------------------------------------------------------------------+
//| Helpers: enums to MQL primitives                                 |
//+------------------------------------------------------------------+
ENUM_LINE_STYLE SMCLineStyle(ENUM_SMC_LINESTYLE s)
  {
   switch(s)
     {
      case SMC_LSTYLE_DASHED: return STYLE_DASH;
      case SMC_LSTYLE_DOTTED: return STYLE_DOT;
      default:                return STYLE_SOLID;
     }
  }

int SMCLabelFontSize(ENUM_SMC_LBL s)
  {
   switch(s)
     {
      case SMC_LBL_NORMAL: return 12;
      case SMC_LBL_SMALL:  return 10;
      default:             return 8;
     }
  }

color SMCMonoBullish() { return C'178,181,190'; }
color SMCMonoBearish() { return C'93,96,107'; }

color SMCSwingBullColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBullish() : InpSwingBullColor;
  }

color SMCSwingBearColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBearish() : InpSwingBearColor;
  }

color SMCInternalBullColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBullish() : InpInternalBullColor;
  }

color SMCInternalBearColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBearish() : InpInternalBearColor;
  }

color SMCFVGBullColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBullish() : InpFairValueGapsBullColor;
  }

color SMCFVGBearColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBearish() : InpFairValueGapsBearColor;
  }

color SMCPremiumColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBearish() : InpPremiumZoneColor;
  }

color SMCDiscountColor()
  {
   return (InpStyle == SMC_MONOCHROME) ? SMCMonoBullish() : InpDiscountZoneColor;
  }


//+------------------------------------------------------------------+
//| OnInit / OnDeinit                                                |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, bufOpen,         INDICATOR_DATA);
   SetIndexBuffer(1, bufHigh,         INDICATOR_DATA);
   SetIndexBuffer(2, bufLow,          INDICATOR_DATA);
   SetIndexBuffer(3, bufClose,        INDICATOR_DATA);
   SetIndexBuffer(4, bufColor,        INDICATOR_COLOR_INDEX);
   SetIndexBuffer(5, bufInternalBias, INDICATOR_DATA);
   SetIndexBuffer(6, bufSwingBias,    INDICATOR_DATA);
   SetIndexBuffer(7, bufEventCode,    INDICATOR_DATA);

   PlotIndexSetString(0, PLOT_LABEL, "SMC Open;SMC High;SMC Low;SMC Close");
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, 250);

   IndicatorSetString(INDICATOR_SHORTNAME, "LuxAlgo SMC");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   ArraySetAsSeries(bufOpen,         false);
   ArraySetAsSeries(bufHigh,         false);
   ArraySetAsSeries(bufLow,          false);
   ArraySetAsSeries(bufClose,        false);
   ArraySetAsSeries(bufColor,        false);
   ArraySetAsSeries(bufInternalBias, false);
   ArraySetAsSeries(bufSwingBias,    false);
   ArraySetAsSeries(bufEventCode,    false);

   ArrayResize(g_internalOBs, 0);
   ArrayResize(g_swingOBs,    0);
   ArrayResize(g_fvgs,        0);
   ArrayResize(g_parsedHighs, 0);
   ArrayResize(g_parsedLows,  0);
   ArrayResize(g_highs,       0);
   ArrayResize(g_lows,        0);
   ArrayResize(g_times,       0);

   ResetPivot(g_swingHigh);
   ResetPivot(g_swingLow);
   ResetPivot(g_internalHigh);
   ResetPivot(g_internalLow);
   ResetPivot(g_equalHigh);
   ResetPivot(g_equalLow);
   ResetTrailing(g_trailing);
   g_swingTrend    = SMC_BIAS_NONE;
   g_internalTrend = SMC_BIAS_NONE;
   g_lastProcessedBars = 0;
   g_initialTime       = 0;
   g_fvgLastTfBarTime  = 0;

   g_equalHighDisplay.lineName  = "";
   g_equalHighDisplay.labelName = "";
   g_equalLowDisplay.lineName   = "";
   g_equalLowDisplay.labelName  = "";

   g_atrHandle = iATR(_Symbol, _Period, 200);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("[SMC] iATR handle failed: ", GetLastError());
      return(INIT_FAILED);
     }

   if(InpEqualHighsLowsThreshold < 0.0 || InpEqualHighsLowsThreshold > 0.5)
     {
      Print("[SMC] InpEqualHighsLowsThreshold must be in [0, 0.5]");
      return(INIT_FAILED);
     }
   if(InpSwingsLength < 10)
     {
      Print("[SMC] InpSwingsLength must be >= 10");
      return(INIT_FAILED);
     }
   if(InpInternalOrderBlocksSize < 1 || InpInternalOrderBlocksSize > 20)
     {
      Print("[SMC] InpInternalOrderBlocksSize must be in [1, 20]");
      return(INIT_FAILED);
     }
   if(InpSwingOrderBlocksSize < 1 || InpSwingOrderBlocksSize > 20)
     {
      Print("[SMC] InpSwingOrderBlocksSize must be in [1, 20]");
      return(INIT_FAILED);
     }

   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
     {
      IndicatorRelease(g_atrHandle);
      g_atrHandle = INVALID_HANDLE;
     }
   SMCDeleteAllObjects();
  }

void ResetPivot(SMCPivot &p)
  {
   p.currentLevel = 0.0;
   p.lastLevel    = 0.0;
   p.crossed      = false;
   p.barTime      = 0;
   p.barIndex     = 0;
  }

void ResetTrailing(SMCTrailing &t)
  {
   t.top            = 0.0;
   t.bottom         = 0.0;
   t.barTime        = 0;
   t.barIndex       = 0;
   t.lastTopTime    = 0;
   t.lastBottomTime = 0;
  }

//+------------------------------------------------------------------+
//| Object cleanup                                                   |
//+------------------------------------------------------------------+
void SMCDeleteAllObjects()
  {
   const int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, InpObjPrefix) == 0)
         ObjectDelete(0, name);
     }
   ChartRedraw();
  }

void SMCDeleteObjectIfAny(const string name)
  {
   if(name == "" || StringLen(name) == 0)
      return;
   if(ObjectFind(0, name) >= 0)
      ObjectDelete(0, name);
  }


//+------------------------------------------------------------------+
//| Object factories: line / label / box                             |
//+------------------------------------------------------------------+
bool SMCMakeOrUpdateTrend(const string name,
                          const datetime t1, const double p1,
                          const datetime t2, const double p2,
                          const color clr,
                          const ENUM_LINE_STYLE style,
                          const int width)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2))
         return(false);
     }
   else
     {
      ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
      ObjectSetDouble(0,  name, OBJPROP_PRICE, 0, p1);
      ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
      ObjectSetDouble(0,  name, OBJPROP_PRICE, 1, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR,    clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE,    style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,    width);
   ObjectSetInteger(0, name, OBJPROP_RAY,      false);
   ObjectSetInteger(0, name, OBJPROP_BACK,     false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,   false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
   return(true);
  }

bool SMCMakeOrUpdateLabel(const string name,
                          const datetime t, const double price,
                          const string text,
                          const color clr,
                          const int fontsize,
                          const ENUM_ANCHOR_POINT anchor)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TEXT, 0, t, price))
         return(false);
     }
   else
     {
      ObjectSetInteger(0, name, OBJPROP_TIME,  t);
      ObjectSetDouble(0,  name, OBJPROP_PRICE, price);
     }
   ObjectSetString(0,  name, OBJPROP_TEXT,    text);
   ObjectSetString(0,  name, OBJPROP_FONT,    "Arial");
   ObjectSetInteger(0, name, OBJPROP_COLOR,   clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontsize);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,  anchor);
   ObjectSetInteger(0, name, OBJPROP_BACK,    false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,  true);
   return(true);
  }

bool SMCMakeOrUpdateRect(const string name,
                         const datetime t1, const double p1,
                         const datetime t2, const double p2,
                         const color border,
                         const color fill,
                         const bool back = true)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
         return(false);
     }
   else
     {
      ObjectSetInteger(0, name, OBJPROP_TIME,  0, t1);
      ObjectSetDouble(0,  name, OBJPROP_PRICE, 0, p1);
      ObjectSetInteger(0, name, OBJPROP_TIME,  1, t2);
      ObjectSetDouble(0,  name, OBJPROP_PRICE, 1, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR,        border);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,      fill);
   ObjectSetInteger(0, name, OBJPROP_FILL,         true);
   ObjectSetInteger(0, name, OBJPROP_BACK,         back);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED,     false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,       true);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,        1);
   return(true);
  }

//+------------------------------------------------------------------+
//| Color blending helpers (Pine color.new(c, transparency_pct))     |
//|   transparency 0   = opaque                                       |
//|   transparency 100 = fully transparent                            |
//| MQL5 doesn't have alpha for OBJ_RECTANGLE bgcolor, so we emulate  |
//| by mixing with the chart background color from CHART_COLOR_BG.   |
//+------------------------------------------------------------------+
color SMCBlendWithChartBg(const color base, const int transparencyPct)
  {
   const long bgRaw = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   const color bg = (color)bgRaw;
   double t = (double)transparencyPct / 100.0;
   if(t < 0.0) t = 0.0;
   if(t > 1.0) t = 1.0;
   const int br = (base       & 0xFF);
   const int bgr= (base >>  8) & 0xFF;
   const int bb = (base >> 16) & 0xFF;
   const int xr = (bg         & 0xFF);
   const int xgr= (bg   >>  8) & 0xFF;
   const int xb = (bg   >> 16) & 0xFF;
   const int rr = (int)MathRound(br * (1.0 - t) + xr * t);
   const int rg = (int)MathRound(bgr * (1.0 - t) + xgr * t);
   const int rb = (int)MathRound(bb * (1.0 - t) + xb * t);
   return((color)((rb << 16) | (rg << 8) | rr));
  }

//+------------------------------------------------------------------+
//| Volatility helpers (Pine: atr / cum mean range)                  |
//+------------------------------------------------------------------+
double SMCGetATR(const int absShift)
  {
   if(g_atrHandle == INVALID_HANDLE) return(0.0);
   double v[];
   if(CopyBuffer(g_atrHandle, 0, absShift, 1, v) != 1)
      return(0.0);
   return(v[0]);
  }

double SMCCumulativeMeanRange(const int barIndex)
  {
   // Pine: ta.cum(ta.tr) / bar_index
   // We don't have a precomputed cumulative TR; on the worker side we
   // accumulate when traversing bars in CalculateUpTo. The function
   // below is purely a proxy derived from ATR for first-bar safety.
   const double atr = SMCGetATR(0);
   return(atr > 0.0 ? atr : (g_highs[ArraySize(g_highs) - 1] - g_lows[ArraySize(g_lows) - 1]));
  }

//+------------------------------------------------------------------+
//| Highest/lowest in [absShift, absShift + length - 1] (chrono)     |
//+------------------------------------------------------------------+
double SMCHighestHigh(const int absShift, const int length)
  {
   const int total = ArraySize(g_highs);
   const int from  = absShift;
   const int to    = absShift + length;
   if(from < 0 || to > total)
      return(0.0);
   double m = g_highs[from];
   for(int i = from + 1; i < to; i++)
      if(g_highs[i] > m) m = g_highs[i];
   return(m);
  }

double SMCLowestLow(const int absShift, const int length)
  {
   const int total = ArraySize(g_lows);
   const int from  = absShift;
   const int to    = absShift + length;
   if(from < 0 || to > total)
      return(0.0);
   double m = g_lows[from];
   for(int i = from + 1; i < to; i++)
      if(g_lows[i] < m) m = g_lows[i];
   return(m);
  }


//+------------------------------------------------------------------+
//| Leg detector (Pine: leg(size))                                   |
//|                                                                  |
//| Pine logic:                                                      |
//|   newLegHigh = high[size] > ta.highest(size)                     |
//|   newLegLow  = low[size]  < ta.lowest(size)                      |
//|   if newLegHigh: leg := BEARISH_LEG   (0)                         |
//|   else if newLegLow: leg := BULLISH_LEG (1)                       |
//|                                                                  |
//| In our chronological arrays (index 0 = oldest):                  |
//|   - 'currentBar' = absolute index of the bar being evaluated     |
//|   - 'size' bars back = currentBar - size                          |
//|   - The lookback window for highest/lowest is                     |
//|     [currentBar - size + 1, currentBar] (exclusive of the pivot) |
//|     i.e. size bars (Pine includes the current bar).               |
//+------------------------------------------------------------------+

#define SMC_NEW_LEG_NONE  -1

// Per-detector persistent leg state (one per (size, channel) combo).
// We mirror Pine's three calls: swing(50), internal(5), equal(N).
struct SMCLegState
  {
   int    leg;        // current leg: SMC_LEG_BULLISH / SMC_LEG_BEARISH / unset (-1)
   int    lastBarIndex;
  };

SMCLegState g_legSwing;
SMCLegState g_legInternal;
SMCLegState g_legEqual;

void SMCResetLegState(SMCLegState &s)
  {
   s.leg          = SMC_NEW_LEG_NONE;
   s.lastBarIndex = -1;
  }

// Returns the new leg value at currentBar, or unchanged previous leg.
// Sets `changed` true if leg flipped on this evaluation.
int SMCLegEvaluate(SMCLegState &s,
                   const int currentBar,
                   const int size,
                   bool &changed,
                   bool &pivotLow,
                   bool &pivotHigh)
  {
   changed   = false;
   pivotLow  = false;
   pivotHigh = false;

   // Pine's leg() runs on every bar; pivot at currentBar - size is
   // tested against the size most recent bars (including currentBar).
   // We need at least `size + 1` bars to evaluate.
   if(currentBar < size)
      return(s.leg);

   const int pivotIdx = currentBar - size;
   const double pivotHighVal = g_highs[pivotIdx];
   const double pivotLowVal  = g_lows[pivotIdx];

   // Highest / lowest over the last `size` bars (Pine's ta.highest(size))
   // includes the current bar; the window is [currentBar - size + 1,
   // currentBar] — i.e. size bars not including pivotIdx itself.
   const double maxHigh = SMCHighestHigh(currentBar - size + 1, size);
   const double minLow  = SMCLowestLow(currentBar - size + 1, size);

   const bool newLegHigh = pivotHighVal > maxHigh;
   const bool newLegLow  = pivotLowVal  < minLow;

   int newLeg = s.leg;
   if(newLegHigh)
      newLeg = SMC_LEG_BEARISH;
   else if(newLegLow)
      newLeg = SMC_LEG_BULLISH;

   if(newLeg != s.leg && s.leg != SMC_NEW_LEG_NONE)
     {
      changed = true;
      pivotLow  = (newLeg == SMC_LEG_BULLISH);
      pivotHigh = (newLeg == SMC_LEG_BEARISH);
     }

   s.leg          = newLeg;
   s.lastBarIndex = currentBar;
   return(s.leg);
  }

//+------------------------------------------------------------------+
//| Equal H/L drawing                                                |
//+------------------------------------------------------------------+
void SMCDrawEqualHighLow(SMCPivot &p, const double level,
                         const int sizeBack, const bool equalHigh,
                         const int currentBar)
  {
   if(InpMode == SMC_PRESENT)
     {
      if(equalHigh)
        {
         SMCDeleteObjectIfAny(g_equalHighDisplay.lineName);
         SMCDeleteObjectIfAny(g_equalHighDisplay.labelName);
        }
      else
        {
         SMCDeleteObjectIfAny(g_equalLowDisplay.lineName);
         SMCDeleteObjectIfAny(g_equalLowDisplay.labelName);
        }
     }

   const string tag      = equalHigh ? "EQH" : "EQL";
   const color  clr      = equalHigh ? SMCSwingBearColor() : SMCSwingBullColor();
   const datetime tEnd   = g_times[currentBar - sizeBack];
   const datetime tMid   = (datetime)((p.barTime + tEnd) / 2);
   const ENUM_ANCHOR_POINT anchor = equalHigh ? ANCHOR_LOWER : ANCHOR_UPPER;

   const long counter = (long)(equalHigh ? 1 : 2) * 1000000 + currentBar;
   const string lineName  = SMCObjUnique(equalHigh ? "EQH_LINE_"  : "EQL_LINE_",  counter);
   const string labelName = SMCObjUnique(equalHigh ? "EQH_LABEL_" : "EQL_LABEL_", counter);

   SMCMakeOrUpdateTrend(lineName, p.barTime, p.currentLevel, tEnd, level,
                        clr, STYLE_DOT, 1);
   SMCMakeOrUpdateLabel(labelName, tMid, level, tag, clr,
                        SMCLabelFontSize(InpEqualLabelSize), anchor);

   if(equalHigh)
     {
      g_equalHighDisplay.lineName  = lineName;
      g_equalHighDisplay.labelName = labelName;
     }
   else
     {
      g_equalLowDisplay.lineName  = lineName;
      g_equalLowDisplay.labelName = labelName;
     }
  }

//+------------------------------------------------------------------+
//| Swing point label (HH / HL / LH / LL)                            |
//+------------------------------------------------------------------+
void SMCDrawSwingLabel(const datetime t, const double price,
                       const string text, const color clr,
                       const ENUM_ANCHOR_POINT anchor)
  {
   const string name = SMCObjUnique("SWING_PT_", (long)t);
   SMCMakeOrUpdateLabel(name, t, price, text, clr,
                        SMCLabelFontSize(InpSwingLabelSize), anchor);
  }

//+------------------------------------------------------------------+
//| getCurrentStructure (Pine getCurrentStructure)                   |
//|                                                                  |
//|   size            int    structure size (Pine left/right confirm)|
//|   equalHighLow    bool   tracks pivot for EQH/EQL                |
//|   internal        bool   tracks pivot for internal structure     |
//+------------------------------------------------------------------+
void SMCGetCurrentStructure(const int currentBar,
                            const int size,
                            const bool equalHighLow,
                            const bool internal)
  {
   bool changed = false;
   bool pivotLow = false;
   bool pivotHigh = false;

   if(equalHighLow)
      SMCLegEvaluate(g_legEqual, currentBar, size, changed, pivotLow, pivotHigh);
   else if(internal)
      SMCLegEvaluate(g_legInternal, currentBar, size, changed, pivotLow, pivotHigh);
   else
      SMCLegEvaluate(g_legSwing, currentBar, size, changed, pivotLow, pivotHigh);

   if(!changed) return;

   const int    pivotIdx = currentBar - size;
   const double atr      = SMCGetATR(0);

   if(pivotLow)
     {
      const double level = g_lows[pivotIdx];

      // capture currentLevel before mutation for label/equality logic
      double prevLevel;
      if(equalHighLow)      prevLevel = g_equalLow.currentLevel;
      else if(internal)     prevLevel = g_internalLow.currentLevel;
      else                  prevLevel = g_swingLow.currentLevel;

      if(equalHighLow && atr > 0.0 && prevLevel != 0.0)
        {
         if(MathAbs(prevLevel - level) < InpEqualHighsLowsThreshold * atr)
           {
            SMCDrawEqualHighLow(g_equalLow, level, size, false, currentBar);
            SMCEmitEvent(SMC_EVT_EQL, currentBar);
           }
        }

      // Apply pivot update by channel
      if(equalHighLow)
        {
         g_equalLow.lastLevel    = g_equalLow.currentLevel;
         g_equalLow.currentLevel = level;
         g_equalLow.crossed      = false;
         g_equalLow.barTime      = g_times[pivotIdx];
         g_equalLow.barIndex     = pivotIdx;
        }
      else if(internal)
        {
         g_internalLow.lastLevel    = g_internalLow.currentLevel;
         g_internalLow.currentLevel = level;
         g_internalLow.crossed      = false;
         g_internalLow.barTime      = g_times[pivotIdx];
         g_internalLow.barIndex     = pivotIdx;
        }
      else
        {
         g_swingLow.lastLevel    = g_swingLow.currentLevel;
         g_swingLow.currentLevel = level;
         g_swingLow.crossed      = false;
         g_swingLow.barTime      = g_times[pivotIdx];
         g_swingLow.barIndex     = pivotIdx;

         g_trailing.bottom         = level;
         g_trailing.barTime        = g_times[pivotIdx];
         g_trailing.barIndex       = pivotIdx;
         g_trailing.lastBottomTime = g_times[pivotIdx];

         if(InpShowSwings)
           {
            const string text = (level < prevLevel || prevLevel == 0.0) ? "LL" : "HL";
            SMCDrawSwingLabel(g_times[pivotIdx], level, text,
                              SMCSwingBullColor(), ANCHOR_UPPER);
           }
        }
     }
   else if(pivotHigh)
     {
      const double level = g_highs[pivotIdx];

      double prevLevel;
      if(equalHighLow)      prevLevel = g_equalHigh.currentLevel;
      else if(internal)     prevLevel = g_internalHigh.currentLevel;
      else                  prevLevel = g_swingHigh.currentLevel;

      if(equalHighLow && atr > 0.0 && prevLevel != 0.0)
        {
         if(MathAbs(prevLevel - level) < InpEqualHighsLowsThreshold * atr)
           {
            SMCDrawEqualHighLow(g_equalHigh, level, size, true, currentBar);
            SMCEmitEvent(SMC_EVT_EQH, currentBar);
           }
        }

      if(equalHighLow)
        {
         g_equalHigh.lastLevel    = g_equalHigh.currentLevel;
         g_equalHigh.currentLevel = level;
         g_equalHigh.crossed      = false;
         g_equalHigh.barTime      = g_times[pivotIdx];
         g_equalHigh.barIndex     = pivotIdx;
        }
      else if(internal)
        {
         g_internalHigh.lastLevel    = g_internalHigh.currentLevel;
         g_internalHigh.currentLevel = level;
         g_internalHigh.crossed      = false;
         g_internalHigh.barTime      = g_times[pivotIdx];
         g_internalHigh.barIndex     = pivotIdx;
        }
      else
        {
         g_swingHigh.lastLevel    = g_swingHigh.currentLevel;
         g_swingHigh.currentLevel = level;
         g_swingHigh.crossed      = false;
         g_swingHigh.barTime      = g_times[pivotIdx];
         g_swingHigh.barIndex     = pivotIdx;

         g_trailing.top         = level;
         g_trailing.barTime     = g_times[pivotIdx];
         g_trailing.barIndex    = pivotIdx;
         g_trailing.lastTopTime = g_times[pivotIdx];

         if(InpShowSwings)
           {
            const string text = (level > prevLevel) ? "HH" : "LH";
            SMCDrawSwingLabel(g_times[pivotIdx], level, text,
                              SMCSwingBearColor(), ANCHOR_LOWER);
           }
        }
     }
  }


//+------------------------------------------------------------------+
//| Custom event emission to chart for EA consumption                |
//+------------------------------------------------------------------+
void SMCEmitEvent(const int code, const int absShift)
  {
   if(absShift >= 0 && absShift < ArraySize(bufEventCode))
      bufEventCode[absShift] = (double)code;

   EventChartCustom(0, (ushort)(code & 0xFFFF), (long)g_times[absShift], 0.0, "");

   if(InpDebugLog)
      PrintFormat("[SMC] event=%d at bar=%d time=%s",
                  code, absShift, TimeToString(g_times[absShift]));
  }

//+------------------------------------------------------------------+
//| BOS / CHoCH structure detection (Pine displayStructure)          |
//+------------------------------------------------------------------+
void SMCDrawStructureLine(SMCPivot &p,
                          const string tag,
                          const color clr,
                          const ENUM_LINE_STYLE lineStyle,
                          const ENUM_ANCHOR_POINT labelAnchor,
                          const ENUM_SMC_LBL labelSize,
                          const datetime endTime,
                          const long uniqueKey)
  {
   const string lineName  = SMCObjUnique("STRUCT_LINE_",  uniqueKey);
   const string labelName = SMCObjUnique("STRUCT_LABEL_", uniqueKey);

   SMCMakeOrUpdateTrend(lineName, p.barTime, p.currentLevel, endTime,
                        p.currentLevel, clr, lineStyle, 1);

   const datetime midT = (datetime)((p.barTime + endTime) / 2);
   SMCMakeOrUpdateLabel(labelName, midT, p.currentLevel, tag, clr,
                        SMCLabelFontSize(labelSize), labelAnchor);
  }

void SMCDisplayStructure(const int currentBar, const bool internal)
  {
   bool bullishBar = true;
   bool bearishBar = true;

   if(InpInternalConfluence && internal)
     {
      const double o = g_parsedHighs[currentBar]; // placeholder, see below
      // Pine: bullishBar = high - max(close,open) > min(close, open - low)
      const double h = g_highs[currentBar];
      const double l = g_lows[currentBar];
      // We need close & open at currentBar; reload from rates_total later.
      // For confluence filter we use real OHLC, not parsed. Rates supplied
      // through SMCSetCurrentBarOHLC; here we read from a global cache.
      const double cls = g_currentClose[currentBar];
      const double opn = g_currentOpen[currentBar];
      bullishBar = (h - MathMax(cls, opn)) > (MathMin(cls, opn) - l);
      bearishBar = (h - MathMax(cls, opn)) < (MathMin(cls, opn) - l);
     }

   const ENUM_LINE_STYLE lineStyle = internal ? STYLE_DASH : STYLE_SOLID;
   const ENUM_SMC_LBL    labelSize = internal ? InpInternalLabelSize : InpSwingLabelSize;
   const color bullColor = internal ? SMCInternalBullColor() : SMCSwingBullColor();
   const color bearColor = internal ? SMCInternalBearColor() : SMCSwingBearColor();
   const ENUM_SMC_STRUCT bullFilter = internal ? InpInternalBullFilter : InpSwingBullFilter;
   const ENUM_SMC_STRUCT bearFilter = internal ? InpInternalBearFilter : InpSwingBearFilter;
   const bool showStructToggle = internal ? InpShowInternals : InpShowStructure;

   const double cls = g_currentClose[currentBar];

   //--- Bullish leg: close crosses over the recent pivotHigh ---
     {
      const double pivotLevel = internal ? g_internalHigh.currentLevel : g_swingHigh.currentLevel;
      const bool   pivotCrossed = internal ? g_internalHigh.crossed     : g_swingHigh.crossed;
      const int    curTrend     = internal ? g_internalTrend            : g_swingTrend;

      bool extra = true;
      if(internal)
         extra = (g_internalHigh.currentLevel != g_swingHigh.currentLevel) && bullishBar;

      const double prevClose = (currentBar > 0 ? g_currentClose[currentBar - 1] : cls);
      const bool crossOver = (prevClose <= pivotLevel) && (cls > pivotLevel);

      if(crossOver && !pivotCrossed && extra && pivotLevel > 0.0)
        {
         const string tag = (curTrend == SMC_BIAS_BEARISH) ? "CHoCH" : "BOS";

         if(internal)
           {
            if(tag == "CHoCH") SMCEmitEvent(SMC_EVT_INT_BULL_CHOCH, currentBar);
            else               SMCEmitEvent(SMC_EVT_INT_BULL_BOS,   currentBar);
            g_internalHigh.crossed = true;
            g_internalTrend        = SMC_BIAS_BULLISH;
           }
         else
           {
            if(tag == "CHoCH") SMCEmitEvent(SMC_EVT_SWG_BULL_CHOCH, currentBar);
            else               SMCEmitEvent(SMC_EVT_SWG_BULL_BOS,   currentBar);
            g_swingHigh.crossed = true;
            g_swingTrend        = SMC_BIAS_BULLISH;
           }

         const bool show = showStructToggle &&
                           (bullFilter == SMC_STRUCT_ALL
                            || (bullFilter == SMC_STRUCT_BOS   && tag != "CHoCH")
                            || (bullFilter == SMC_STRUCT_CHOCH && tag == "CHoCH"));

         if(show)
           {
            if(internal)
               SMCDrawStructureLine(g_internalHigh, tag, bullColor, lineStyle,
                                    ANCHOR_UPPER, labelSize,
                                    g_times[currentBar],
                                    (long)g_times[currentBar] * 10 + 1);
            else
               SMCDrawStructureLine(g_swingHigh, tag, bullColor, lineStyle,
                                    ANCHOR_UPPER, labelSize,
                                    g_times[currentBar],
                                    (long)g_times[currentBar] * 10 + 0);
           }

         const bool storeOB = (internal ? InpShowInternalOrderBlocks : InpShowSwingOrderBlocks);
         if(storeOB)
           {
            if(internal)
               SMCStoreOrderBlock(g_internalHigh, true,  SMC_BIAS_BULLISH, currentBar);
            else
               SMCStoreOrderBlock(g_swingHigh,    false, SMC_BIAS_BULLISH, currentBar);
           }
        }
     }

   //--- Bearish leg: close crosses under the recent pivotLow ---
     {
      const double pivotLevel = internal ? g_internalLow.currentLevel : g_swingLow.currentLevel;
      const bool   pivotCrossed = internal ? g_internalLow.crossed     : g_swingLow.crossed;
      const int    curTrend     = internal ? g_internalTrend           : g_swingTrend;

      bool extra = true;
      if(internal)
         extra = (g_internalLow.currentLevel != g_swingLow.currentLevel) && bearishBar;

      const double prevClose = (currentBar > 0 ? g_currentClose[currentBar - 1] : cls);
      const bool crossUnder = (prevClose >= pivotLevel) && (cls < pivotLevel);

      if(crossUnder && !pivotCrossed && extra && pivotLevel > 0.0)
        {
         const string tag = (curTrend == SMC_BIAS_BULLISH) ? "CHoCH" : "BOS";

         if(internal)
           {
            if(tag == "CHoCH") SMCEmitEvent(SMC_EVT_INT_BEAR_CHOCH, currentBar);
            else               SMCEmitEvent(SMC_EVT_INT_BEAR_BOS,   currentBar);
            g_internalLow.crossed = true;
            g_internalTrend       = SMC_BIAS_BEARISH;
           }
         else
           {
            if(tag == "CHoCH") SMCEmitEvent(SMC_EVT_SWG_BEAR_CHOCH, currentBar);
            else               SMCEmitEvent(SMC_EVT_SWG_BEAR_BOS,   currentBar);
            g_swingLow.crossed = true;
            g_swingTrend       = SMC_BIAS_BEARISH;
           }

         const bool show = showStructToggle &&
                           (bearFilter == SMC_STRUCT_ALL
                            || (bearFilter == SMC_STRUCT_BOS   && tag != "CHoCH")
                            || (bearFilter == SMC_STRUCT_CHOCH && tag == "CHoCH"));

         if(show)
           {
            if(internal)
               SMCDrawStructureLine(g_internalLow, tag, bearColor, lineStyle,
                                    ANCHOR_LOWER, labelSize,
                                    g_times[currentBar],
                                    (long)g_times[currentBar] * 10 + 2);
            else
               SMCDrawStructureLine(g_swingLow, tag, bearColor, lineStyle,
                                    ANCHOR_LOWER, labelSize,
                                    g_times[currentBar],
                                    (long)g_times[currentBar] * 10 + 3);
           }

         const bool storeOB = (internal ? InpShowInternalOrderBlocks : InpShowSwingOrderBlocks);
         if(storeOB)
           {
            if(internal)
               SMCStoreOrderBlock(g_internalLow, true,  SMC_BIAS_BEARISH, currentBar);
            else
               SMCStoreOrderBlock(g_swingLow,    false, SMC_BIAS_BEARISH, currentBar);
           }
        }
     }
  }


//+------------------------------------------------------------------+
//| Order block storage and drawing                                  |
//|                                                                  |
//| Pine: storeOrderBlock(p, internal, bias)                         |
//|   For BEARISH: scan parsedHighs[p.barIndex .. bar_index] and pick|
//|                the bar with the maximum parsedHigh.              |
//|   For BULLISH: scan parsedLows  and pick min parsedLow.          |
//|   Store {barHigh, barLow, barTime, bias} of that bar.            |
//+------------------------------------------------------------------+
void SMCStoreOrderBlock(SMCPivot &p, const bool internal,
                        const int bias, const int currentBar)
  {
   const int from = p.barIndex;
   const int to   = currentBar;
   if(from < 0 || to <= from || to >= ArraySize(g_parsedHighs))
      return;

   int pickIdx = from;
   if(bias == SMC_BIAS_BEARISH)
     {
      double m = g_parsedHighs[from];
      for(int i = from + 1; i <= to; i++)
         if(g_parsedHighs[i] > m)
           {
            m = g_parsedHighs[i];
            pickIdx = i;
           }
     }
   else
     {
      double m = g_parsedLows[from];
      for(int i = from + 1; i <= to; i++)
         if(g_parsedLows[i] < m)
           {
            m = g_parsedLows[i];
            pickIdx = i;
           }
     }

   SMCOrderBlock ob;
   ob.barHigh = g_parsedHighs[pickIdx];
   ob.barLow  = g_parsedLows[pickIdx];
   ob.barTime = g_times[pickIdx];
   ob.bias    = bias;
   ob.objName = "";
   ob.active  = true;

   if(internal)
     {
      // Pine: unshift, capped at 100
      const int n = ArraySize(g_internalOBs);
      if(n >= SMC_MAX_OB_HISTORY)
        {
         // pop the oldest = last (since we unshift to front)
         SMCDeleteObjectIfAny(g_internalOBs[n - 1].objName);
         ArrayResize(g_internalOBs, n - 1);
        }
      ArrayResize(g_internalOBs, ArraySize(g_internalOBs) + 1);
      // shift right
      for(int i = ArraySize(g_internalOBs) - 1; i > 0; i--)
         g_internalOBs[i] = g_internalOBs[i - 1];
      g_internalOBs[0] = ob;
     }
   else
     {
      const int n = ArraySize(g_swingOBs);
      if(n >= SMC_MAX_OB_HISTORY)
        {
         SMCDeleteObjectIfAny(g_swingOBs[n - 1].objName);
         ArrayResize(g_swingOBs, n - 1);
        }
      ArrayResize(g_swingOBs, ArraySize(g_swingOBs) + 1);
      for(int i = ArraySize(g_swingOBs) - 1; i > 0; i--)
         g_swingOBs[i] = g_swingOBs[i - 1];
      g_swingOBs[0] = ob;
     }
  }

void SMCDeleteOrderBlocks(const bool internal, const int currentBar)
  {
   const double mitClose = g_currentClose[currentBar];
   const double bearishMitSrc = (InpOrderBlockMitigation == SMC_OB_CLOSE) ? mitClose : g_highs[currentBar];
   const double bullishMitSrc = (InpOrderBlockMitigation == SMC_OB_CLOSE) ? mitClose : g_lows[currentBar];

   if(internal)
     {
      for(int i = ArraySize(g_internalOBs) - 1; i >= 0; i--)
        {
         bool crossed = false;
         if(g_internalOBs[i].bias == SMC_BIAS_BEARISH && bearishMitSrc > g_internalOBs[i].barHigh)
           {
            crossed = true;
            SMCEmitEvent(SMC_EVT_INT_OB_BEAR_MIT, currentBar);
           }
         else if(g_internalOBs[i].bias == SMC_BIAS_BULLISH && bullishMitSrc < g_internalOBs[i].barLow)
           {
            crossed = true;
            SMCEmitEvent(SMC_EVT_INT_OB_BULL_MIT, currentBar);
           }
         if(crossed)
           {
            SMCDeleteObjectIfAny(g_internalOBs[i].objName);
            // remove element i (shift left)
            const int n = ArraySize(g_internalOBs);
            for(int j = i; j < n - 1; j++)
               g_internalOBs[j] = g_internalOBs[j + 1];
            ArrayResize(g_internalOBs, n - 1);
           }
        }
     }
   else
     {
      for(int i = ArraySize(g_swingOBs) - 1; i >= 0; i--)
        {
         bool crossed = false;
         if(g_swingOBs[i].bias == SMC_BIAS_BEARISH && bearishMitSrc > g_swingOBs[i].barHigh)
           {
            crossed = true;
            SMCEmitEvent(SMC_EVT_SWG_OB_BEAR_MIT, currentBar);
           }
         else if(g_swingOBs[i].bias == SMC_BIAS_BULLISH && bullishMitSrc < g_swingOBs[i].barLow)
           {
            crossed = true;
            SMCEmitEvent(SMC_EVT_SWG_OB_BULL_MIT, currentBar);
           }
         if(crossed)
           {
            SMCDeleteObjectIfAny(g_swingOBs[i].objName);
            const int n = ArraySize(g_swingOBs);
            for(int j = i; j < n - 1; j++)
               g_swingOBs[j] = g_swingOBs[j + 1];
            ArrayResize(g_swingOBs, n - 1);
           }
        }
     }
  }

void SMCDrawOrderBlocks(const bool internal, const datetime rightEdge)
  {
   const int maxShow = internal ? InpInternalOrderBlocksSize : InpSwingOrderBlocksSize;
   if(maxShow <= 0) return;

   const int n = internal ? ArraySize(g_internalOBs) : ArraySize(g_swingOBs);
   const int show = MathMin(n, maxShow);
   if(show <= 0) return;

   for(int i = 0; i < show; i++)
     {
      double obHigh, obLow;
      datetime obTime;
      int obBias;
      if(internal)
        {
         obHigh = g_internalOBs[i].barHigh;
         obLow  = g_internalOBs[i].barLow;
         obTime = g_internalOBs[i].barTime;
         obBias = g_internalOBs[i].bias;
        }
      else
        {
         obHigh = g_swingOBs[i].barHigh;
         obLow  = g_swingOBs[i].barLow;
         obTime = g_swingOBs[i].barTime;
         obBias = g_swingOBs[i].bias;
        }

      const string family = StringFormat("%sOB_%I64d_%d",
                                         internal ? "I" : "S",
                                         (long)obTime, obBias);
      const string name = SMCObj(family);
      if(internal) g_internalOBs[i].objName = name;
      else         g_swingOBs[i].objName    = name;

      color baseColor;
      if(InpStyle == SMC_MONOCHROME)
         baseColor = (obBias == SMC_BIAS_BEARISH) ? SMCMonoBearish() : SMCMonoBullish();
      else if(internal)
         baseColor = (obBias == SMC_BIAS_BEARISH) ? InpInternalBearishOBColor : InpInternalBullishOBColor;
      else
         baseColor = (obBias == SMC_BIAS_BEARISH) ? InpSwingBearishOBColor    : InpSwingBullishOBColor;

      const color fill = SMCBlendWithChartBg(baseColor, 40);
      color border;
      if(InpStyle == SMC_MONOCHROME)
         border = baseColor;
      else if(internal)
         border = SMCBlendWithChartBg(baseColor, 20);
      else
         border = baseColor;

      SMCMakeOrUpdateRect(name,
                          obTime, obHigh,
                          rightEdge,  obLow,
                          border, fill, false);
     }
  }


//+------------------------------------------------------------------+
//| Fair Value Gaps (full MTF)                                       |
//|                                                                  |
//| Pine logic uses request.security on the user-selected timeframe. |
//| For each *closed* TF bar, it inspects:                           |
//|   lastClose  = TF close[1]                                       |
//|   lastOpen   = TF open[1]                                        |
//|   lastTime   = TF time[1]                                        |
//|   currentHigh = TF high[0]                                       |
//|   currentLow  = TF low[0]                                        |
//|   currentTime = TF time[0]                                       |
//|   last2High = TF high[2]                                         |
//|   last2Low  = TF low[2]                                          |
//|                                                                  |
//| Bullish FVG when:                                                |
//|   currentLow > last2High                                         |
//|   AND lastClose > last2High                                      |
//|   AND barDeltaPct > threshold                                    |
//|   AND timeframe.change                                            |
//|                                                                  |
//| In MT5, "currentTime[0]" refers to the just-formed TF bar; we    |
//| evaluate when the chart timeframe has produced the close of that |
//| bar. We approximate this by tracking g_fvgLastTfBarTime and      |
//| evaluating once per new TF bar that has closed.                  |
//+------------------------------------------------------------------+

double g_fvgCumulativeDeltaPct = 0.0;  // running sum of |TF barDeltaPct|
int    g_fvgTfBarCount         = 0;    // bars on TF since indicator started

double SMCFVGComputeThreshold(const double currentDeltaPct)
  {
   if(!InpFairValueGapsAutoThreshold) return(0.0);
   g_fvgCumulativeDeltaPct += MathAbs(currentDeltaPct);
   g_fvgTfBarCount++;
   if(g_fvgTfBarCount <= 0) return(0.0);
   return((g_fvgCumulativeDeltaPct / g_fvgTfBarCount) * 2.0);
  }

void SMCDeleteFairValueGaps(const int currentBar)
  {
   const double curHigh = g_highs[currentBar];
   const double curLow  = g_lows[currentBar];

   for(int i = ArraySize(g_fvgs) - 1; i >= 0; i--)
     {
      bool mitigated = false;
      if(g_fvgs[i].bias == SMC_BIAS_BULLISH && curLow < g_fvgs[i].bottom)
         mitigated = true;
      else if(g_fvgs[i].bias == SMC_BIAS_BEARISH && curHigh > g_fvgs[i].top)
         mitigated = true;
      if(mitigated)
        {
         SMCDeleteObjectIfAny(g_fvgs[i].topBoxName);
         SMCDeleteObjectIfAny(g_fvgs[i].bottomBoxName);
         const int n = ArraySize(g_fvgs);
         for(int j = i; j < n - 1; j++)
            g_fvgs[j] = g_fvgs[j + 1];
         ArrayResize(g_fvgs, n - 1);
        }
     }
  }

void SMCMakeFVGBoxes(SMCFairValueGap &fvg,
                     const datetime extendRightTime,
                     const color baseColor)
  {
   const color fill = SMCBlendWithChartBg(baseColor, 40);
   const double mid = (fvg.top + fvg.bottom) / 2.0;

   const string topName = SMCObj(StringFormat("FVG_T_%I64d_%d", (long)fvg.leftTime, fvg.bias));
   const string botName = SMCObj(StringFormat("FVG_B_%I64d_%d", (long)fvg.leftTime, fvg.bias));
   fvg.topBoxName    = topName;
   fvg.bottomBoxName = botName;

   if(fvg.bias == SMC_BIAS_BULLISH)
     {
      // Top half: from bottom (=last2High) up to mid
      // Bottom half: from mid up to top (=currentLow)
      // Pine box.new(top..bottom): we map (top=currentLow, bottom=last2High)
      // First box: (top=currentLow, bottom=mid)
      // Second box: (top=mid, bottom=last2High)
      SMCMakeOrUpdateRect(topName,
                          fvg.leftTime, fvg.top,
                          extendRightTime, mid,
                          fill, fill);
      SMCMakeOrUpdateRect(botName,
                          fvg.leftTime, mid,
                          extendRightTime, fvg.bottom,
                          fill, fill);
     }
   else
     {
      // Bearish: top=currentHigh, bottom=last2Low
      SMCMakeOrUpdateRect(topName,
                          fvg.leftTime, fvg.top,
                          extendRightTime, mid,
                          fill, fill);
      SMCMakeOrUpdateRect(botName,
                          fvg.leftTime, mid,
                          extendRightTime, fvg.bottom,
                          fill, fill);
     }
  }

void SMCDrawFairValueGaps(const int currentBar)
  {
   if(!InpShowFairValueGaps) return;

   const ENUM_TIMEFRAMES tf = (InpFairValueGapsTimeframe == PERIOD_CURRENT) ? _Period : InpFairValueGapsTimeframe;

   // Need at least 3 closed bars on tf
   const datetime tfBarTime = iTime(_Symbol, tf, 0);
   if(tfBarTime == 0) return;
   if(tfBarTime == g_fvgLastTfBarTime) return;
   g_fvgLastTfBarTime = tfBarTime;

   // tf shifts: 1 = last closed, 2 = before that, 3 = three back
   const double lastClose = iClose(_Symbol, tf, 1);
   const double lastOpen  = iOpen (_Symbol, tf, 1);
   const datetime lastTime= iTime (_Symbol, tf, 1);
   const double currentHi = iHigh (_Symbol, tf, 0);
   const double currentLo = iLow  (_Symbol, tf, 0);
   const datetime curTime = iTime (_Symbol, tf, 0);
   const double last2Hi   = iHigh (_Symbol, tf, 2);
   const double last2Lo   = iLow  (_Symbol, tf, 2);

   if(lastOpen <= 0.0) return;

   const double barDeltaPct = (lastClose - lastOpen) / (lastOpen * 100.0);
   const double threshold   = SMCFVGComputeThreshold(barDeltaPct);

   const bool bullishFVG = (currentLo > last2Hi) && (lastClose > last2Hi) && (barDeltaPct  > threshold);
   const bool bearishFVG = (currentHi < last2Lo) && (lastClose < last2Lo) && (-barDeltaPct > threshold);

   if(!bullishFVG && !bearishFVG) return;

   // Cap history
   if(ArraySize(g_fvgs) >= SMC_MAX_FVG_HISTORY)
     {
      SMCDeleteObjectIfAny(g_fvgs[0].topBoxName);
      SMCDeleteObjectIfAny(g_fvgs[0].bottomBoxName);
      const int n = ArraySize(g_fvgs);
      for(int j = 0; j < n - 1; j++)
         g_fvgs[j] = g_fvgs[j + 1];
      ArrayResize(g_fvgs, n - 1);
     }

   const datetime extendRight = (datetime)(curTime + (long)InpFairValueGapsExtend
                                            * (long)PeriodSeconds(tf));

   if(bullishFVG)
     {
      SMCFairValueGap fvg;
      fvg.top       = currentLo;
      fvg.bottom    = last2Hi;
      fvg.bias      = SMC_BIAS_BULLISH;
      fvg.leftTime  = lastTime;
      fvg.rightTime = curTime;
      fvg.active    = true;
      ArrayResize(g_fvgs, ArraySize(g_fvgs) + 1);
      g_fvgs[ArraySize(g_fvgs) - 1] = fvg;
      SMCMakeFVGBoxes(g_fvgs[ArraySize(g_fvgs) - 1], extendRight, SMCFVGBullColor());
      SMCEmitEvent(SMC_EVT_FVG_BULL, currentBar);
     }
   else
     {
      SMCFairValueGap fvg;
      fvg.top       = currentHi;
      fvg.bottom    = last2Lo;
      fvg.bias      = SMC_BIAS_BEARISH;
      fvg.leftTime  = lastTime;
      fvg.rightTime = curTime;
      fvg.active    = true;
      ArrayResize(g_fvgs, ArraySize(g_fvgs) + 1);
      g_fvgs[ArraySize(g_fvgs) - 1] = fvg;
      SMCMakeFVGBoxes(g_fvgs[ArraySize(g_fvgs) - 1], extendRight, SMCFVGBearColor());
      SMCEmitEvent(SMC_EVT_FVG_BEAR, currentBar);
     }
  }


//+------------------------------------------------------------------+
//| MTF previous-period levels (Daily / Weekly / Monthly)            |
//+------------------------------------------------------------------+
bool SMCHigherTimeframe(const ENUM_TIMEFRAMES higher)
  {
   return PeriodSeconds(_Period) > PeriodSeconds(higher);
  }

void SMCDrawLevels(const ENUM_TIMEFRAMES tf,
                   const string slug,
                   const ENUM_LINE_STYLE style,
                   const color clr)
  {
   if(SMCHigherTimeframe(tf)) return;

   const double topLevel    = iHigh(_Symbol, tf, 1);
   const double bottomLevel = iLow (_Symbol, tf, 1);
   const datetime leftTime  = iTime(_Symbol, tf, 1);
   const datetime rightTime = iTime(_Symbol, tf, 0);

   if(topLevel <= 0.0 || bottomLevel <= 0.0 || leftTime == 0) return;

   const datetime endTime = (datetime)(rightTime + 20 * (long)PeriodSeconds(_Period));

   const string topLine = SMCObj("LVL_" + slug + "_TOP_LINE");
   const string botLine = SMCObj("LVL_" + slug + "_BOT_LINE");
   const string topLbl  = SMCObj("LVL_" + slug + "_TOP_LABEL");
   const string botLbl  = SMCObj("LVL_" + slug + "_BOT_LABEL");

   SMCMakeOrUpdateTrend(topLine, leftTime, topLevel, endTime, topLevel, clr, style, 1);
   SMCMakeOrUpdateTrend(botLine, leftTime, bottomLevel, endTime, bottomLevel, clr, style, 1);
   SMCMakeOrUpdateLabel(topLbl, endTime, topLevel,    "P" + slug + "H", clr, 8, ANCHOR_LEFT);
   SMCMakeOrUpdateLabel(botLbl, endTime, bottomLevel, "P" + slug + "L", clr, 8, ANCHOR_LEFT);
  }

//+------------------------------------------------------------------+
//| Strong/Weak high-low and Premium/Discount zones                  |
//+------------------------------------------------------------------+
void SMCUpdateTrailingExtremes(const int currentBar)
  {
   const double h = g_highs[currentBar];
   const double l = g_lows[currentBar];
   const datetime t = g_times[currentBar];

   if(h > g_trailing.top)
     {
      g_trailing.top         = h;
      g_trailing.lastTopTime = t;
     }
   if(l < g_trailing.bottom || g_trailing.bottom == 0.0)
     {
      g_trailing.bottom         = l;
      g_trailing.lastBottomTime = t;
     }
  }

void SMCDrawHighLowSwings()
  {
   const datetime endTime = (datetime)(g_times[ArraySize(g_times) - 1]
                                       + 20 * (long)PeriodSeconds(_Period));

   const string topLine = SMCObj("TRAIL_TOP_LINE");
   const string botLine = SMCObj("TRAIL_BOT_LINE");
   const string topLbl  = SMCObj("TRAIL_TOP_LABEL");
   const string botLbl  = SMCObj("TRAIL_BOT_LABEL");

   SMCMakeOrUpdateTrend(topLine, g_trailing.lastTopTime, g_trailing.top,
                        endTime, g_trailing.top,
                        SMCSwingBearColor(), STYLE_SOLID, 1);
   SMCMakeOrUpdateTrend(botLine, g_trailing.lastBottomTime, g_trailing.bottom,
                        endTime, g_trailing.bottom,
                        SMCSwingBullColor(), STYLE_SOLID, 1);

   const string topText = (g_swingTrend == SMC_BIAS_BEARISH) ? "Strong High" : "Weak High";
   const string botText = (g_swingTrend == SMC_BIAS_BULLISH) ? "Strong Low"  : "Weak Low";
   SMCMakeOrUpdateLabel(topLbl, endTime, g_trailing.top, topText,
                        SMCSwingBearColor(), 8, ANCHOR_LOWER);
   SMCMakeOrUpdateLabel(botLbl, endTime, g_trailing.bottom, botText,
                        SMCSwingBullColor(), 8, ANCHOR_UPPER);
  }

void SMCDrawZone(const string slug,
                 const datetime t1, const double p1,
                 const datetime t2, const double p2,
                 const string label, const datetime labelT, const double labelP,
                 const color baseColor,
                 const ENUM_ANCHOR_POINT anchor)
  {
   const string boxName = SMCObj("ZONE_" + slug + "_BOX");
   const string lblName = SMCObj("ZONE_" + slug + "_LABEL");
   const color fill = SMCBlendWithChartBg(baseColor, 70);
   SMCMakeOrUpdateRect(boxName, t1, p1, t2, p2, CLR_NONE, fill, true);
   SMCMakeOrUpdateLabel(lblName, labelT, labelP, label, baseColor, 9, anchor);
  }

void SMCDrawPremiumDiscountZones()
  {
   const double top = g_trailing.top;
   const double bot = g_trailing.bottom;
   if(top <= 0.0 || bot <= 0.0 || top <= bot) return;

   const datetime endTime = (datetime)(g_times[ArraySize(g_times) - 1]
                                       + 20 * (long)PeriodSeconds(_Period));
   const datetime midTime = (datetime)((g_trailing.barTime + endTime) / 2);

   const double premiumBot     = 0.95 * top + 0.05 * bot;
   const double equilibriumTop = 0.525 * top + 0.475 * bot;
   const double equilibriumBot = 0.525 * bot + 0.475 * top;
   const double discountTop    = 0.95 * bot + 0.05 * top;
   const double mid            = (top + bot) / 2.0;

   SMCDrawZone("PREMIUM",
               g_trailing.barTime, top,
               endTime, premiumBot,
               "Premium", midTime, top,
               SMCPremiumColor(), ANCHOR_LOWER);

   SMCDrawZone("EQUI",
               g_trailing.barTime, equilibriumTop,
               endTime, equilibriumBot,
               "Equilibrium", endTime, mid,
               InpEquilibriumZoneColor, ANCHOR_LEFT);

   SMCDrawZone("DISCOUNT",
               g_trailing.barTime, discountTop,
               endTime, bot,
               "Discount", midTime, bot,
               SMCDiscountColor(), ANCHOR_UPPER);
  }

//+------------------------------------------------------------------+
//| Real-time current OHLC global (used by displayStructure)         |
//+------------------------------------------------------------------+
double g_currentOpen[];
double g_currentClose[];

void SMCStoreCurrentOHLC(const int rates_total,
                         const double &open[],  const double &close[])
  {
   if(ArraySize(g_currentOpen)  != rates_total) ArrayResize(g_currentOpen,  rates_total);
   if(ArraySize(g_currentClose) != rates_total) ArrayResize(g_currentClose, rates_total);
   for(int i = 0; i < rates_total; i++)
     {
      g_currentOpen[i]  = open[i];
      g_currentClose[i] = close[i];
     }
  }


//+------------------------------------------------------------------+
//| OnCalculate                                                      |
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
   if(rates_total < 250)
      return(0);

   // Indicator data sources are non-series; we operate in chronological order.
   ArraySetAsSeries(time,  false);
   ArraySetAsSeries(open,  false);
   ArraySetAsSeries(high,  false);
   ArraySetAsSeries(low,   false);
   ArraySetAsSeries(close, false);

   // (Re)initialize on first run or full recalc
   const bool fullRecalc = (prev_calculated == 0);
   const int  startBar   = fullRecalc ? 0 : (prev_calculated - 1);

   if(fullRecalc)
     {
      ArrayResize(g_parsedHighs, rates_total);
      ArrayResize(g_parsedLows,  rates_total);
      ArrayResize(g_highs,       rates_total);
      ArrayResize(g_lows,        rates_total);
      ArrayResize(g_times,       rates_total);
      ArrayInitialize(g_parsedHighs, 0.0);
      ArrayInitialize(g_parsedLows,  0.0);
      ArrayInitialize(g_highs,       0.0);
      ArrayInitialize(g_lows,        0.0);

      ArrayInitialize(bufOpen,         EMPTY_VALUE);
      ArrayInitialize(bufHigh,         EMPTY_VALUE);
      ArrayInitialize(bufLow,          EMPTY_VALUE);
      ArrayInitialize(bufClose,        EMPTY_VALUE);
      ArrayInitialize(bufColor,        0);
      ArrayInitialize(bufInternalBias, 0.0);
      ArrayInitialize(bufSwingBias,    0.0);
      ArrayInitialize(bufEventCode,    0.0);

      g_initialTime = time[0];

      ResetPivot(g_swingHigh);
      ResetPivot(g_swingLow);
      ResetPivot(g_internalHigh);
      ResetPivot(g_internalLow);
      ResetPivot(g_equalHigh);
      ResetPivot(g_equalLow);
      ResetTrailing(g_trailing);
      g_swingTrend    = SMC_BIAS_NONE;
      g_internalTrend = SMC_BIAS_NONE;

      SMCResetLegState(g_legSwing);
      SMCResetLegState(g_legInternal);
      SMCResetLegState(g_legEqual);

      ArrayResize(g_internalOBs, 0);
      ArrayResize(g_swingOBs,    0);
      ArrayResize(g_fvgs,        0);
      g_fvgCumulativeDeltaPct = 0.0;
      g_fvgTfBarCount         = 0;
      g_fvgLastTfBarTime      = 0;

      // Hard-clear chart objects on full recalc to keep visuals coherent
      SMCDeleteAllObjects();
     }
   else
     {
      // Resize arrays to track new bars
      if(ArraySize(g_parsedHighs) != rates_total)
        {
         ArrayResize(g_parsedHighs, rates_total);
         ArrayResize(g_parsedLows,  rates_total);
         ArrayResize(g_highs,       rates_total);
         ArrayResize(g_lows,        rates_total);
         ArrayResize(g_times,       rates_total);
        }
     }

   // Cache OHLC
   SMCStoreCurrentOHLC(rates_total, open, close);

   // Fill chronological arrays (incremental from startBar)
   for(int i = startBar; i < rates_total; i++)
     {
      g_highs[i] = high[i];
      g_lows[i]  = low[i];
      g_times[i] = time[i];

      // Pine: parsedHigh / parsedLow trick for high-volatility bars
      const double atr = SMCGetATR(rates_total - 1 - i);
      double volatilityMeasure = atr;
      if(InpOrderBlockFilter == SMC_OB_RANGE)
        {
         // approximate cumulative-mean-range with ATR; close enough for the OB filter
         volatilityMeasure = atr;
        }
      const bool highVol = (high[i] - low[i]) >= 2.0 * volatilityMeasure;
      g_parsedHighs[i] = highVol ? low[i]  : high[i];
      g_parsedLows[i]  = highVol ? high[i] : low[i];
     }

   // Process structure / OBs / FVGs / etc per bar
   for(int i = startBar; i < rates_total; i++)
     {
      // Structures need at least 2*size bars of history; the leg detector
      // returns early if currentBar < size.
      SMCGetCurrentStructure(i, InpSwingsLength, /*equalHL*/false, /*internal*/false);
      SMCGetCurrentStructure(i, 5,               /*equalHL*/false, /*internal*/true);

      if(InpShowEqualHighsLows)
         SMCGetCurrentStructure(i, InpEqualHighsLowsLength, /*equalHL*/true, /*internal*/false);

      if(InpShowInternals || InpShowInternalOrderBlocks || InpShowTrend)
         SMCDisplayStructure(i, /*internal*/true);

      if(InpShowStructure || InpShowSwingOrderBlocks || InpShowHighLowSwings)
         SMCDisplayStructure(i, /*internal*/false);

      if(InpShowInternalOrderBlocks)
         SMCDeleteOrderBlocks(/*internal*/true, i);
      if(InpShowSwingOrderBlocks)
         SMCDeleteOrderBlocks(/*internal*/false, i);

      if(InpShowHighLowSwings || InpShowPremiumDiscountZones)
         SMCUpdateTrailingExtremes(i);

      if(InpShowFairValueGaps)
        {
         SMCDeleteFairValueGaps(i);
         SMCDrawFairValueGaps(i);
        }

      // Fill output buffers
      bufOpen[i]   = open[i];
      bufHigh[i]   = high[i];
      bufLow[i]    = low[i];
      bufClose[i]  = close[i];
      bufColor[i]  = (g_internalTrend == SMC_BIAS_BULLISH ? 0
                     : g_internalTrend == SMC_BIAS_BEARISH ? 1 : 2);
      bufInternalBias[i] = (double)g_internalTrend;
      bufSwingBias[i]    = (double)g_swingTrend;
     }

   // Suppress candle output when "Color Candles" is off so the user's own
   // chart candles remain visible.
   if(!InpShowTrend)
     {
      for(int i = 0; i < rates_total; i++)
        {
         bufOpen[i]  = EMPTY_VALUE;
         bufHigh[i]  = EMPTY_VALUE;
         bufLow[i]   = EMPTY_VALUE;
         bufClose[i] = EMPTY_VALUE;
        }
     }

   // Final-pass drawings (run only at "last bar" equivalent each tick)
   const datetime rightEdge = (datetime)(time[rates_total - 1]
                                         + 20 * (long)PeriodSeconds(_Period));
   if(InpShowInternalOrderBlocks)
      SMCDrawOrderBlocks(/*internal*/true, rightEdge);
   if(InpShowSwingOrderBlocks)
      SMCDrawOrderBlocks(/*internal*/false, rightEdge);

   if(InpShowHighLowSwings)
      SMCDrawHighLowSwings();
   if(InpShowPremiumDiscountZones)
      SMCDrawPremiumDiscountZones();

   if(InpShowDailyLevels)
      SMCDrawLevels(PERIOD_D1, "D",
                    SMCLineStyle(InpDailyLevelsStyle), InpDailyLevelsColor);
   if(InpShowWeeklyLevels)
      SMCDrawLevels(PERIOD_W1, "W",
                    SMCLineStyle(InpWeeklyLevelsStyle), InpWeeklyLevelsColor);
   if(InpShowMonthlyLevels)
      SMCDrawLevels(PERIOD_MN1, "M",
                    SMCLineStyle(InpMonthlyLevelsStyle), InpMonthlyLevelsColor);

   g_lastProcessedBars = rates_total;
   return(rates_total);
  }
//+------------------------------------------------------------------+
