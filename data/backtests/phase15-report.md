# Phase 15 backtest -- M15 v0.5.0 optimization with train/test split

4 entry profiles x 4 SL placements = 16 cells.
Train: 2024-01..2025-05 (17 months). Test: 2025-06..2026-05 (12 months).

Pre-committed thresholds per half: n>=30, PF>1.40, meanRR>=0.5, sigs/mo>=6, losing_months<=30 percent.

## Result table

Each cell shows TRAIN | TEST | FULL aggregate.

```
cell   profile   SL           TR-n  TR-WR  TR-PF  TR-net TR-sm   TE-n  TE-WR  TE-PF  TE-net TE-sm  verdict       
----------------------------------------------------------------------------------------------------------------------------------
A-S1   strict    78.6 fib       11  63.6%   1.61  +2.44   0.6     68  52.9%   1.07  +2.12   5.7  REJECT        
A-S2   strict    90 pct         11  72.7%   3.05  +4.10   0.6     68  58.8%   1.17  +4.48   5.7  REJECT        
A-S3   strict    100 (=L)       11  72.7%   5.30  +4.30   0.6     68  63.2%   1.29  +6.48   5.7  REJECT        
A-S4   strict    110 cur        11  81.8%    inf  +5.27   0.6     68  69.1%   1.53  +9.53   5.7  REJECT        
B-S1   firm      78.6 fib       21  61.9%   1.50  +3.96   1.2    103  60.2%   1.43 +17.04   8.6  REJECT        
B-S2   firm      90 pct         21  66.7%   1.78  +4.67   1.2    103  64.1%   1.44 +15.30   8.6  REJECT        
B-S3   firm      100 (=L)       21  66.7%   1.85  +4.27   1.2    103  67.0%   1.47 +14.70   8.6  REJECT        
B-S4   firm      110 cur        21  71.4%   2.20  +4.78   1.2    103  72.8%   1.76 +18.92   8.6  REJECT        
C-S1   medium    78.6 fib       35  60.0%   1.38  +5.32   2.1    145  57.2%   1.25 +15.36  12.1  REJECT        
C-S2   medium    90 pct         35  65.7%   1.59  +6.53   2.1    145  63.4%   1.37 +19.11  12.1  REJECT        
C-S3   medium    100 (=L)       35  65.7%   1.52  +5.23   2.1    145  66.2%   1.38 +17.58  12.1  REJECT        
C-S4   medium    110 cur        35  74.3%   2.18  +8.23   2.1    145  73.1%   1.72 +26.08  12.1  REJECT        
D-S1   relax     78.6 fib       55  69.1%   2.06 +17.96   3.2    175  55.4%   1.16 +12.24  14.6  REJECT        
D-S2   relax     90 pct         55  72.7%   2.18 +16.48   3.2    175  61.1%   1.24 +15.54  14.6  REJECT        
D-S3   relax     100 (=L)       55  72.7%   2.04 +13.49   3.2    175  65.1%   1.30 +17.50  14.6  REJECT        
D-S4   relax     110 cur        55  80.0%   2.86 +16.77   3.2    175  70.9%   1.51 +24.62  14.6  REJECT        
```

## Cells passing BOTH train and test

None. No cell cleared the thresholds on both halves.

