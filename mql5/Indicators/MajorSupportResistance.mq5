//+------------------------------------------------------------------+
//|                                   MajorSupportResistance.mq5     |
//|                                          momentum-candle project |
//|                            https://github.com/rizfa-is           |
//+------------------------------------------------------------------+
//| Phase 2 of the S/R initiative -- chart-side renderer for the     |
//| algorithm in src/mt5_mvp/strategies/support_resistance.py.       |
//|                                                                  |
//| Detects major support/resistance levels using:                   |
//|   1. Swing-pivot detection (fractal-based)                       |
//|   2. Cluster + touch-count aggregation                           |
//|   3. Multi-timeframe extremes (day/prior-day/week)               |
//|   4. Round-number injection (multiples of InpRoundStep)          |
//|                                                                  |
//| When the active timeframe doesn't surface S/R on both sides of   |
//| the current price, escalates through the ladder M5 -> M15 -> H1  |
//| -> H4 -> D1 until both sides are populated.                      |
//|                                                                  |
//| Each level renders as:                                            |
//|   - a horizontal line (price-anchored to the trigger time range) |
//|   - a shaded zone (rectangle, width = cluster radius)             |
//|   - a text label (tier + type + weight)                           |
//|                                                                  |
//| Hot-cold tier coloring:                                           |
//|   M5      = silver        (cold / recent)                         |
//|   M15     = aqua                                                   |
//|   H1      = yellow                                                 |
//|   H4      = orange                                                 |
//|   D1      = crimson       (hot / macro)                            |
//|   static  = dim gray      (round-number levels)                    |
//+------------------------------------------------------------------+

#property copyright "momentum-candle project"
#property link      "https://github.com/rizfa-is/momentum-candle"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

//--- inputs --------------------------------------------------------
input group "Detection"
input int    InpLookback              = 500;     // bars per tier scan
input double InpClusterAtrMult        = 0.5;     // cluster radius = this x ATR(14)
input int    InpMinTouches            = 3;       // min pivots to qualify as major
input int    InpPivotLeft             = 10;      // bars before pivot for confirmation
input int    InpPivotRight            = 10;      // bars after pivot for confirmation
input bool   InpUseEscalation         = true;    // climb timeframes when one-sided
input int    InpMaxTier               = 5;       // 1=M5, 2=M15, 3=H1, 4=H4, 5=D1
input bool   InpIncludeRoundNumbers   = true;    // inject round-number levels
input double InpRoundStep             = 50.0;    // distance between round numbers
input bool   InpIncludeMultiTfExtremes = true;   // include day/week extremes from D1
input int    InpAtrPeriod             = 14;     // ATR period

input group "Display"
input bool   InpDrawZones             = true;    // render shaded rectangles behind lines
input bool   InpDrawLabels            = true;    // render tier+type+weight labels
input int    InpMaxLevelsShown        = 20;      // hard cap on total levels rendered
input int    InpZoneBackBars          = 200;     // how far back the zone rectangle extends
input int    InpZoneForwardBars       = 50;      // how far forward the zone rectangle extends
input string InpObjectPrefix          = "MSR_";  // chart object name prefix
input bool   InpShowHud               = true;    // top-left summary text
input bool   InpDebugLog              = false;   // verbose log to journal

//--- internal types ------------------------------------------------
struct MSR_Level
  {
   double      price;
   int         weight;
   string      type;
   string      tier;
   datetime    first_touch;
   datetime    last_touch;
  };

//--- runtime state -------------------------------------------------
MSR_Level g_levels[];
datetime  g_last_bar_time = 0;

//--- tier ladder ---------------------------------------------------
ENUM_TIMEFRAMES TierPeriod(const int idx)
  {
   switch(idx)
     {
      case 0: return PERIOD_M5;
      case 1: return PERIOD_M15;
      case 2: return PERIOD_H1;
      case 3: return PERIOD_H4;
      case 4: return PERIOD_D1;
     }
   return PERIOD_M5;
  }

string TierName(const int idx)
  {
   switch(idx)
     {
      case 0: return "M5";
      case 1: return "M15";
      case 2: return "H1";
      case 3: return "H4";
      case 4: return "D1";
     }
   return "?";
  }

int TierIndexFromName(const string name)
  {
   if(name == "M5")  return 0;
   if(name == "M15") return 1;
   if(name == "H1")  return 2;
   if(name == "H4")  return 3;
   if(name == "D1")  return 4;
   if(name == "static") return 5;
   return 99;
  }

//--- color + style mapping per tier --------------------------------
color TierColor(const string tier)
  {
   if(tier == "M5")     return clrSilver;
   if(tier == "M15")    return clrAqua;
   if(tier == "H1")     return clrYellow;
   if(tier == "H4")     return clrOrange;
   if(tier == "D1")     return clrCrimson;
   return clrDimGray;
  }

int TierLineWidth(const int weight)
  {
   if(weight >= 5) return 3;
   if(weight >= 3) return 2;
   return 1;
  }

ENUM_LINE_STYLE TierLineStyle(const string tier)
  {
   if(tier == "static") return STYLE_DOT;
   if(tier == "D1")     return STYLE_SOLID;
   return STYLE_SOLID;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("Major S/R (cluster=%.2fxATR, touches>=%d, escal=%s)",
                                   InpClusterAtrMult, InpMinTouches,
                                   InpUseEscalation ? "yes" : "no"));
   ObjectsDeleteAll(0, InpObjectPrefix);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, InpObjectPrefix);
   Comment("");
  }

//+------------------------------------------------------------------+
//| ATR helper -- Wilder smoothing on the active timeframe.          |
//| Returns the most recent ATR value. Returns 0 on insufficient     |
//| history.                                                         |
//+------------------------------------------------------------------+
double LastWilderATR(const ENUM_TIMEFRAMES tf, const int period, const int lookback)
  {
   if(lookback < period + 2) return 0.0;
   double atr = 0.0;
   for(int k = period; k > 0; k--)
     {
      const double h = iHigh(_Symbol, tf, k);
      const double l = iLow(_Symbol, tf, k);
      const double pc = iClose(_Symbol, tf, k + 1);
      const double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      atr += tr;
     }
   atr /= period;
   // Wilder smooth back to bar 1
   for(int k = period - 1; k >= 1; k--)
     {
      const double h = iHigh(_Symbol, tf, k);
      const double l = iLow(_Symbol, tf, k);
      const double pc = iClose(_Symbol, tf, k + 1);
      const double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      atr = (atr * (period - 1) + tr) / period;
     }
   return atr;
  }

//+------------------------------------------------------------------+
//| Pivot detection on the chosen timeframe.                          |
//+------------------------------------------------------------------+
void ScanTierPivots(const ENUM_TIMEFRAMES tf, const string tier_name,
                    const int lookback, const int pivot_left, const int pivot_right,
                    const double cluster_radius, const int min_touches)
  {
   datetime times[];
   double prices[];
   ArrayResize(times, 0);
   ArrayResize(prices, 0);

   const int total = MathMin(lookback, iBars(_Symbol, tf));
   if(total < pivot_left + pivot_right + 2) return;

   //--- gather pivots
   //  shift convention: 1 = most recently CLOSED bar; pivot_right
   //  bars right (newer) are needed for confirmation; pivot_left bars
   //  left (older) are needed too.
   for(int i = pivot_right + 1; i + pivot_left < total; i++)
     {
      const double h = iHigh(_Symbol, tf, i);
      const double l = iLow(_Symbol, tf, i);

      bool is_pivot_high = true;
      bool is_pivot_low  = true;
      for(int k = 1; k <= pivot_left && (is_pivot_high || is_pivot_low); k++)
        {
         if(iHigh(_Symbol, tf, i + k) >= h) is_pivot_high = false;
         if(iLow(_Symbol, tf, i + k)  <= l) is_pivot_low  = false;
        }
      for(int k = 1; k <= pivot_right && (is_pivot_high || is_pivot_low); k++)
        {
         if(iHigh(_Symbol, tf, i - k) >= h) is_pivot_high = false;
         if(iLow(_Symbol, tf, i - k)  <= l) is_pivot_low  = false;
        }
      if(!is_pivot_high && !is_pivot_low) continue;

      const datetime t = iTime(_Symbol, tf, i);
      const int n = ArraySize(prices);
      ArrayResize(times, n + 1);
      ArrayResize(prices, n + 1);
      times[n] = t;
      prices[n] = is_pivot_high ? h : l;
     }

   if(ArraySize(prices) == 0) return;

   //--- sort pivots by price (simple insertion sort, list is small)
   const int n_pivots = ArraySize(prices);
   for(int i = 1; i < n_pivots; i++)
     {
      const double p = prices[i];
      const datetime t = times[i];
      int j = i - 1;
      while(j >= 0 && prices[j] > p)
        {
         prices[j + 1] = prices[j];
         times[j + 1]  = times[j];
         j--;
        }
      prices[j + 1] = p;
      times[j + 1]  = t;
     }

   //--- greedy-cluster within radius
   int  cluster_count = 0;
   int  cluster_indices[];
   ArrayResize(cluster_indices, n_pivots);

   //  cluster_indices[i] = id of cluster pivot i belongs to
   double mean = prices[0];
   int    members = 1;
   cluster_indices[0] = 0;
   int    cluster_id  = 0;
   for(int i = 1; i < n_pivots; i++)
     {
      if(MathAbs(prices[i] - mean) <= cluster_radius)
        {
         mean = (mean * members + prices[i]) / (members + 1);
         members++;
         cluster_indices[i] = cluster_id;
        }
      else
        {
         cluster_id++;
         mean = prices[i];
         members = 1;
         cluster_indices[i] = cluster_id;
        }
     }
   cluster_count = cluster_id + 1;

   //--- accumulate cluster stats and emit MSR_Levels with weight >= min_touches
   for(int cid = 0; cid < cluster_count; cid++)
     {
      double sum = 0.0;
      int    cnt = 0;
      datetime first_t = 0;
      datetime last_t = 0;
      for(int i = 0; i < n_pivots; i++)
        {
         if(cluster_indices[i] != cid) continue;
         sum += prices[i];
         cnt++;
         if(first_t == 0 || times[i] < first_t) first_t = times[i];
         if(times[i] > last_t) last_t = times[i];
        }
      if(cnt < min_touches) continue;

      const int slot = ArraySize(g_levels);
      ArrayResize(g_levels, slot + 1);
      g_levels[slot].price = sum / cnt;
      g_levels[slot].weight = cnt;
      g_levels[slot].type = "swing";
      g_levels[slot].tier = tier_name;
      g_levels[slot].first_touch = first_t;
      g_levels[slot].last_touch = last_t;
     }

   if(InpDebugLog)
      PrintFormat("[MSR] %s scan: %d pivots -> %d clusters, %d levels emitted",
                  tier_name, n_pivots, cluster_count, ArraySize(g_levels));
  }

//+------------------------------------------------------------------+
//| Both-sides coverage check                                         |
//+------------------------------------------------------------------+
bool HasBothSides(const double current_price)
  {
   bool above = false;
   bool below = false;
   for(int i = 0; i < ArraySize(g_levels); i++)
     {
      if(g_levels[i].weight < InpMinTouches) continue;
      if(g_levels[i].price > current_price) above = true;
      if(g_levels[i].price < current_price) below = true;
      if(above && below) return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Static levels: round numbers + multi-TF extremes                  |
//+------------------------------------------------------------------+
void AddRoundLevels(const double current_price, const double radius)
  {
   if(InpRoundStep <= 0) return;
   const double nearest = MathRound(current_price / InpRoundStep) * InpRoundStep;
   for(int k = 0; k <= 50; k++)
     {
      bool any_in_band = false;
      for(int sign = -1; sign <= 1; sign += 2)
        {
         if(k == 0 && sign == 1) continue; // avoid double-emitting nearest
         const double p = nearest + sign * k * InpRoundStep;
         if(MathAbs(p - current_price) > radius) continue;
         const int slot = ArraySize(g_levels);
         ArrayResize(g_levels, slot + 1);
         g_levels[slot].price = p;
         g_levels[slot].weight = 1;
         g_levels[slot].type = "round_50";
         g_levels[slot].tier = "static";
         g_levels[slot].first_touch = 0;
         g_levels[slot].last_touch = 0;
         any_in_band = true;
        }
      if(!any_in_band && k > 0) break;
     }
  }

void AddMultiTfExtremes()
  {
   if(iBars(_Symbol, PERIOD_D1) < 1) return;
   //  today
   const double dh = iHigh(_Symbol, PERIOD_D1, 0);
   const double dl = iLow(_Symbol, PERIOD_D1, 0);
   AppendStaticLevel(dh, "day_high", "D1");
   AppendStaticLevel(dl, "day_low",  "D1");

   //  prior day
   if(iBars(_Symbol, PERIOD_D1) >= 2)
     {
      AppendStaticLevel(iHigh(_Symbol, PERIOD_D1, 1), "prior_day_high", "D1");
      AppendStaticLevel(iLow (_Symbol, PERIOD_D1, 1), "prior_day_low",  "D1");
     }

   //  week (last 5 D1 bars)
   if(iBars(_Symbol, PERIOD_D1) >= 5)
     {
      double wh = iHigh(_Symbol, PERIOD_D1, 0);
      double wl = iLow (_Symbol, PERIOD_D1, 0);
      for(int k = 1; k < 5; k++)
        {
         wh = MathMax(wh, iHigh(_Symbol, PERIOD_D1, k));
         wl = MathMin(wl, iLow (_Symbol, PERIOD_D1, k));
        }
      AppendStaticLevel(wh, "week_high", "D1");
      AppendStaticLevel(wl, "week_low",  "D1");
     }
  }

void AppendStaticLevel(const double price, const string type_, const string tier)
  {
   const int slot = ArraySize(g_levels);
   ArrayResize(g_levels, slot + 1);
   g_levels[slot].price = price;
   g_levels[slot].weight = 1;
   g_levels[slot].type = type_;
   g_levels[slot].tier = tier;
   g_levels[slot].first_touch = 0;
   g_levels[slot].last_touch = 0;
  }

//+------------------------------------------------------------------+
//| Cross-tier dedupe -- keep lower tier when prices are within      |
//| dedupe_radius. Lower tier ranking: M5(0) < M15 < H1 < H4 < D1 <  |
//| static(5).                                                        |
//+------------------------------------------------------------------+
void DedupeLevels(const double dedupe_radius)
  {
   if(dedupe_radius <= 0) return;

   const int n = ArraySize(g_levels);
   bool keep[];
   ArrayResize(keep, n);
   for(int i = 0; i < n; i++) keep[i] = true;

   for(int i = 0; i < n; i++)
     {
      if(!keep[i]) continue;
      const int rank_i = TierIndexFromName(g_levels[i].tier);
      for(int j = i + 1; j < n; j++)
        {
         if(!keep[j]) continue;
         if(MathAbs(g_levels[i].price - g_levels[j].price) > dedupe_radius) continue;
         const int rank_j = TierIndexFromName(g_levels[j].tier);
         //  drop higher-ranked tier (older / less specific)
         if(rank_i <= rank_j)
           {
            //  bump i's weight by max
            if(g_levels[j].weight > g_levels[i].weight)
               g_levels[i].weight = g_levels[j].weight;
            keep[j] = false;
           }
         else
           {
            //  prefer j; copy its data into i and drop j
            if(g_levels[i].weight > g_levels[j].weight)
               g_levels[j].weight = g_levels[i].weight;
            //  swap: j now becomes the canonical
            g_levels[i].price = g_levels[j].price;
            g_levels[i].weight = g_levels[j].weight;
            g_levels[i].type = g_levels[j].type;
            g_levels[i].tier = g_levels[j].tier;
            g_levels[i].first_touch = g_levels[j].first_touch;
            g_levels[i].last_touch = g_levels[j].last_touch;
            keep[j] = false;
           }
        }
     }

   //  compact
   int write = 0;
   for(int i = 0; i < n; i++)
     {
      if(!keep[i]) continue;
      if(write != i)
        {
         g_levels[write] = g_levels[i];
        }
      write++;
     }
   ArrayResize(g_levels, write);
  }

//+------------------------------------------------------------------+
//| Sort by absolute distance from current price (insertion sort).    |
//+------------------------------------------------------------------+
void SortByDistance(const double current_price)
  {
   const int n = ArraySize(g_levels);
   for(int i = 1; i < n; i++)
     {
      const MSR_Level key = g_levels[i];
      const double key_dist = MathAbs(key.price - current_price);
      int j = i - 1;
      while(j >= 0 && MathAbs(g_levels[j].price - current_price) > key_dist)
        {
         g_levels[j + 1] = g_levels[j];
         j--;
        }
      g_levels[j + 1] = key;
     }
  }

//+------------------------------------------------------------------+
//| Render one level on the chart                                     |
//+------------------------------------------------------------------+
void DrawLevel(const MSR_Level &L, const int slot)
  {
   const string id_line  = StringFormat("%sL%d_line", InpObjectPrefix, slot);
   const string id_zone  = StringFormat("%sL%d_zone", InpObjectPrefix, slot);
   const string id_label = StringFormat("%sL%d_lbl",  InpObjectPrefix, slot);

   const color clr      = TierColor(L.tier);
   const int   width    = TierLineWidth(L.weight);
   const ENUM_LINE_STYLE style = TierLineStyle(L.tier);

   //  time anchors -- use chart's most-recent bar to span the view
   const datetime t_now = iTime(_Symbol, _Period, 0);
   const datetime t_back = iTime(_Symbol, _Period, MathMin(InpZoneBackBars, iBars(_Symbol, _Period) - 1));
   const datetime t_forward = t_now + InpZoneForwardBars * PeriodSeconds(_Period);

   //  Horizontal line via OBJ_TREND
   if(ObjectFind(0, id_line) >= 0) ObjectDelete(0, id_line);
   ObjectCreate(0, id_line, OBJ_TREND, 0, t_back, L.price, t_forward, L.price);
   ObjectSetInteger(0, id_line, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id_line, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, id_line, OBJPROP_STYLE, style);
   ObjectSetInteger(0, id_line, OBJPROP_BACK, true);
   ObjectSetInteger(0, id_line, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, id_line, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, id_line, OBJPROP_SELECTABLE, false);

   //  Shaded zone (rectangle)
   if(InpDrawZones)
     {
      const double atr = LastWilderATR(_Period, InpAtrPeriod, InpLookback);
      const double half = atr * InpClusterAtrMult * 0.5;
      const double top = L.price + half;
      const double bot = L.price - half;
      if(ObjectFind(0, id_zone) >= 0) ObjectDelete(0, id_zone);
      ObjectCreate(0, id_zone, OBJ_RECTANGLE, 0, t_back, top, t_forward, bot);
      ObjectSetInteger(0, id_zone, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, id_zone, OBJPROP_FILL, true);
      ObjectSetInteger(0, id_zone, OBJPROP_BACK, true);
      ObjectSetInteger(0, id_zone, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, id_zone, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, id_zone, OBJPROP_SELECTABLE, false);
     }

   //  Label
   if(InpDrawLabels)
     {
      const string txt = StringFormat("%s %s w%d",
                                       L.tier, L.type, L.weight);
      if(ObjectFind(0, id_label) >= 0) ObjectDelete(0, id_label);
      ObjectCreate(0, id_label, OBJ_TEXT, 0, t_forward, L.price);
      ObjectSetString(0,  id_label, OBJPROP_TEXT, txt);
      ObjectSetInteger(0, id_label, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, id_label, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, id_label, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, id_label, OBJPROP_SELECTABLE, false);
     }
  }

//+------------------------------------------------------------------+
//| HUD (top-left summary)                                            |
//+------------------------------------------------------------------+
void UpdateHud(const double current_price, const int drawn,
               const string &tiers_scanned, const bool escalation_triggered)
  {
   if(!InpShowHud)
     {
      Comment("");
      return;
     }
   int support_count = 0, resistance_count = 0;
   for(int i = 0; i < ArraySize(g_levels); i++)
     {
      if(g_levels[i].price < current_price) support_count++;
      else                                   resistance_count++;
     }
   Comment(StringFormat(
      "==== Major S/R ====\n"
      "Price:         %s\n"
      "Levels found:  %d (%d res / %d sup, drawn=%d)\n"
      "Tiers scanned: %s\n"
      "Escalation:    %s",
      DoubleToString(current_price, _Digits),
      ArraySize(g_levels), resistance_count, support_count, drawn,
      tiers_scanned,
      escalation_triggered ? "YES" : "no"));
  }

//+------------------------------------------------------------------+
//| OnCalculate -- recompute on each new bar of the active timeframe |
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
   if(rates_total < 2) return 0;

   const datetime t1 = iTime(_Symbol, _Period, 1);
   if(t1 == g_last_bar_time && prev_calculated > 0) return rates_total;
   g_last_bar_time = t1;

   //--- wipe previous render
   ObjectsDeleteAll(0, InpObjectPrefix);
   ArrayResize(g_levels, 0);

   const double current_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double price = (current_price > 0.0) ? current_price : iClose(_Symbol, _Period, 0);

   //--- detect starting tier index (must match active chart period;
   //  if active period not on the ladder, default to M5)
   int start_idx = 0;
   for(int k = 0; k < 5; k++)
     {
      if(TierPeriod(k) == _Period) { start_idx = k; break; }
     }
   const int cap_idx = MathMin(InpMaxTier - 1, 4);

   //--- scan tiers with one-sided escalation
   string tiers_scanned = "";
   double last_atr = 0.0;
   bool escalation = false;
   for(int idx = start_idx; idx <= cap_idx; idx++)
     {
      const ENUM_TIMEFRAMES tf = TierPeriod(idx);
      const double atr = LastWilderATR(tf, InpAtrPeriod, InpLookback);
      if(atr <= 0.0) continue;
      last_atr = atr;
      const double cluster_radius = atr * InpClusterAtrMult;

      ScanTierPivots(tf, TierName(idx), InpLookback,
                     InpPivotLeft, InpPivotRight, cluster_radius, InpMinTouches);
      if(StringLen(tiers_scanned) > 0) tiers_scanned += ",";
      tiers_scanned += TierName(idx);
      if(idx > start_idx) escalation = true;

      if(!InpUseEscalation) break;
      if(HasBothSides(price)) break;
     }

   //--- static levels
   if(InpIncludeMultiTfExtremes) AddMultiTfExtremes();
   if(InpIncludeRoundNumbers && last_atr > 0.0) AddRoundLevels(price, last_atr * 20.0);

   //--- dedupe + sort
   if(last_atr > 0.0)
      DedupeLevels(last_atr * InpClusterAtrMult);
   SortByDistance(price);

   //--- render
   const int draw_count = MathMin(InpMaxLevelsShown, ArraySize(g_levels));
   for(int i = 0; i < draw_count; i++)
      DrawLevel(g_levels[i], i);

   UpdateHud(price, draw_count, tiers_scanned, escalation);

   if(InpDebugLog)
      PrintFormat("[MSR] recompute: tiers=%s escalation=%d levels=%d drawn=%d atr=%.5f",
                  tiers_scanned, (int)escalation, ArraySize(g_levels), draw_count, last_atr);

   return rates_total;
  }
