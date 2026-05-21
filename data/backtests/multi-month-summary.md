# Multi-month backtest -- 2025-01 to 2026-05 (17 months)

Months tested: 2025-01, 2025-02, 2025-03, 2025-04, 2025-05, 2025-06, 2025-07, 2025-08, 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-04, 2026-05

Three filters x two entry modes x 17 months = 102 configurations.

## Per-month results

```
config                                           sigs   fill   TP2    SL     WR  meanRR      net      PF
---------------------------------------------------------------------------------------------------------
2025-01 | baseline           | next_open            3      3     2     1  66.7%   0.324    -0.35    0.65
2025-01 | baseline           | pullback_236         3      3     1     1  33.3%   0.584    -0.42    0.58
2025-01 | optimized          | next_open            1      1     1     0  100.0%   0.289    +0.29     inf
2025-01 | optimized          | pullback_236         1      1     0     0   0.0%   0.000    +0.00    0.00
2025-01 | optimized_no_round | next_open            1      1     1     0  100.0%   0.289    +0.29     inf
2025-01 | optimized_no_round | pullback_236         1      1     0     0   0.0%   0.000    +0.00    0.00

2025-02 | baseline           | next_open            8      8     7     1  87.5%   0.291    +1.03    2.03
2025-02 | baseline           | pullback_236         8      7     5     1  71.4%   0.585    +1.93    2.93
2025-02 | optimized          | next_open            0      0     0     0   0.0%   0.000    +0.00    0.00
2025-02 | optimized          | pullback_236         0      0     0     0   0.0%   0.000    +0.00    0.00
2025-02 | optimized_no_round | next_open            2      2     2     0  100.0%   0.285    +0.57     inf
2025-02 | optimized_no_round | pullback_236         2      2     2     0  100.0%   0.586    +1.17     inf

2025-03 | baseline           | next_open            2      2     1     0  50.0%   0.265    +0.27     inf
2025-03 | baseline           | pullback_236         2      2     1     0  50.0%   0.586    +0.59     inf
2025-03 | optimized          | next_open            0      0     0     0   0.0%   0.000    +0.00    0.00
2025-03 | optimized          | pullback_236         0      0     0     0   0.0%   0.000    +0.00    0.00
2025-03 | optimized_no_round | next_open            0      0     0     0   0.0%   0.000    +0.00    0.00
2025-03 | optimized_no_round | pullback_236         0      0     0     0   0.0%   0.000    +0.00    0.00

2025-04 | baseline           | next_open           74     74    58    16  78.4%   0.294    +1.04    1.06
2025-04 | baseline           | pullback_236        74     61    41    20  67.2%   0.586    +4.01    1.20
2025-04 | optimized          | next_open            6      6     3     3  50.0%   0.301    -2.10    0.30
2025-04 | optimized          | pullback_236         6      4     1     3  25.0%   0.585    -2.41    0.20
2025-04 | optimized_no_round | next_open            9      9     5     4  55.6%   0.283    -2.58    0.35
2025-04 | optimized_no_round | pullback_236         9      6     2     4  33.3%   0.585    -2.83    0.29

2025-05 | baseline           | next_open           29     29    23     6  79.3%   0.291    +0.70    1.12
2025-05 | baseline           | pullback_236        29     25    18     7  72.0%   0.586    +3.54    1.51
2025-05 | optimized          | next_open            5      5     4     1  80.0%   0.282    +0.13    1.13
2025-05 | optimized          | pullback_236         5      5     4     1  80.0%   0.586    +1.34    2.34
2025-05 | optimized_no_round | next_open            6      6     5     1  83.3%   0.284    +0.42    1.42
2025-05 | optimized_no_round | pullback_236         6      5     4     1  80.0%   0.586    +1.34    2.34

2025-06 | baseline           | next_open           18     18    13     5  72.2%   0.265    -1.56    0.69
2025-06 | baseline           | pullback_236        18     15    10     5  66.7%   0.586    +0.86    1.17
2025-06 | optimized          | next_open            1      1     1     0  100.0%   0.266    +0.27     inf
2025-06 | optimized          | pullback_236         1      1     1     0  100.0%   0.585    +0.59     inf
2025-06 | optimized_no_round | next_open            1      1     1     0  100.0%   0.266    +0.27     inf
2025-06 | optimized_no_round | pullback_236         1      1     1     0  100.0%   0.585    +0.59     inf

2025-07 | baseline           | next_open            5      5     5     0  100.0%   0.289    +1.45     inf
2025-07 | baseline           | pullback_236         5      3     3     0  100.0%   0.585    +1.76     inf
2025-07 | optimized          | next_open            1      1     1     0  100.0%   0.252    +0.25     inf
2025-07 | optimized          | pullback_236         1      0     0     0   0.0%   0.000    +0.00    0.00
2025-07 | optimized_no_round | next_open            1      1     1     0  100.0%   0.252    +0.25     inf
2025-07 | optimized_no_round | pullback_236         1      0     0     0   0.0%   0.000    +0.00    0.00

2025-08 | baseline           | next_open            5      5     2     3  40.0%   0.320    -2.36    0.21
2025-08 | baseline           | pullback_236         5      4     1     3  25.0%   0.585    -2.41    0.20
2025-08 | optimized          | next_open            2      2     1     1  50.0%   0.368    -0.63    0.37
2025-08 | optimized          | pullback_236         2      1     0     1   0.0%   0.000    -1.00    0.00
2025-08 | optimized_no_round | next_open            2      2     1     1  50.0%   0.368    -0.63    0.37
2025-08 | optimized_no_round | pullback_236         2      1     0     1   0.0%   0.000    -1.00    0.00

2025-09 | baseline           | next_open           10     10     7     3  70.0%   0.285    -1.01    0.66
2025-09 | baseline           | pullback_236        10      7     4     3  57.1%   0.586    -0.66    0.78
2025-09 | optimized          | next_open            0      0     0     0   0.0%   0.000    +0.00    0.00
2025-09 | optimized          | pullback_236         0      0     0     0   0.0%   0.000    +0.00    0.00
2025-09 | optimized_no_round | next_open            1      1     1     0  100.0%   0.354    +0.35     inf
2025-09 | optimized_no_round | pullback_236         1      1     1     0  100.0%   0.586    +0.59     inf

2025-10 | baseline           | next_open          156    156   115    41  73.7%   0.294    -7.16    0.83
2025-10 | baseline           | pullback_236       156    144    97    47  67.4%   0.586    +9.81    1.21
2025-10 | optimized          | next_open           25     25    18     7  72.0%   0.294    -1.72    0.75
2025-10 | optimized          | pullback_236        25     23    16     7  69.6%   0.586    +2.37    1.34
2025-10 | optimized_no_round | next_open           36     36    27     9  75.0%   0.299    -0.92    0.90
2025-10 | optimized_no_round | pullback_236        36     33    24     9  72.7%   0.586    +5.06    1.56

2025-11 | baseline           | next_open           60     60    48    12  80.0%   0.289    +1.87    1.16
2025-11 | baseline           | pullback_236        60     52    39    13  75.0%   0.586    +9.84    1.76
2025-11 | optimized          | next_open            8      8     5     3  62.5%   0.298    -1.51    0.50
2025-11 | optimized          | pullback_236         8      6     3     3  50.0%   0.586    -1.24    0.59
2025-11 | optimized_no_round | next_open           12     12     9     3  75.0%   0.293    -0.36    0.88
2025-11 | optimized_no_round | pullback_236        12     10     7     3  70.0%   0.586    +1.10    1.37

2025-12 | baseline           | next_open           52     52    38    11  73.1%   0.281    -0.30    0.97
2025-12 | baseline           | pullback_236        52     44    30    11  68.2%   0.586    +6.57    1.60
2025-12 | optimized          | next_open            5      5     2     2  40.0%   0.298    -1.40    0.30
2025-12 | optimized          | pullback_236         5      5     2     2  40.0%   0.585    -0.83    0.59
2025-12 | optimized_no_round | next_open            7      7     3     3  42.9%   0.306    -2.08    0.31
2025-12 | optimized_no_round | pullback_236         7      7     3     3  42.9%   0.586    -1.24    0.59

2026-01 | baseline           | next_open          161    161   117    43  72.7%   0.287    -9.47    0.78
2026-01 | baseline           | pullback_236       161    141    94    46  66.7%   0.586    +9.05    1.20
2026-01 | optimized          | next_open           37     37    27    10  73.0%   0.295    -2.04    0.80
2026-01 | optimized          | pullback_236        37     32    19    13  59.4%   0.586    -1.87    0.86
2026-01 | optimized_no_round | next_open           52     52    37    15  71.2%   0.290    -4.25    0.72
2026-01 | optimized_no_round | pullback_236        52     44    26    18  59.1%   0.586    -2.77    0.85

2026-02 | baseline           | next_open          223    223   171    52  76.7%   0.292    -2.06    0.96
2026-02 | baseline           | pullback_236       223    200   143    57  71.5%   0.586   +26.75    1.47
2026-02 | optimized          | next_open           26     26    22     4  84.6%   0.289    +2.35    1.59
2026-02 | optimized          | pullback_236        26     21    15     6  71.4%   0.586    +2.79    1.46
2026-02 | optimized_no_round | next_open           49     49    40     9  81.6%   0.292    +2.68    1.30
2026-02 | optimized_no_round | pullback_236        49     42    31    11  73.8%   0.586    +7.16    1.65

2026-03 | baseline           | next_open          287    287   227    60  79.1%   0.290    +5.73    1.10
2026-03 | baseline           | pullback_236       287    254   185    69  72.8%   0.586   +39.34    1.57
2026-03 | optimized          | next_open           46     46    40     6  87.0%   0.298    +5.94    1.99
2026-03 | optimized          | pullback_236        46     42    34     8  81.0%   0.586   +11.91    2.49
2026-03 | optimized_no_round | next_open           69     69    58    11  84.1%   0.300    +6.40    1.58
2026-03 | optimized_no_round | pullback_236        69     63    50    13  79.4%   0.586   +16.28    2.25

2026-04 | baseline           | next_open          147    147   105    42  71.4%   0.291   -11.43    0.73
2026-04 | baseline           | pullback_236       147    133    84    49  63.2%   0.586    +0.20    1.00
2026-04 | optimized          | next_open           20     20    15     5  75.0%   0.309    -0.36    0.93
2026-04 | optimized          | pullback_236        20     17    12     5  70.6%   0.586    +2.03    1.41
2026-04 | optimized_no_round | next_open           34     34    26     8  76.5%   0.307    -0.01    1.00
2026-04 | optimized_no_round | pullback_236        34     30    21     9  70.0%   0.586    +3.30    1.37

2026-05 | baseline           | next_open           72     72    53    19  73.6%   0.287    -3.79    0.80
2026-05 | baseline           | pullback_236        72     65    43    22  66.2%   0.586    +3.18    1.14
2026-05 | optimized          | next_open           10     10    10     0  100.0%   0.295    +2.95     inf
2026-05 | optimized          | pullback_236        10      9     8     1  88.9%   0.586    +3.68    4.68
2026-05 | optimized_no_round | next_open           11     11    11     0  100.0%   0.300    +3.30     inf
2026-05 | optimized_no_round | pullback_236        11     10     9     1  90.0%   0.585    +4.27    5.27

```

## Pooled aggregate (17 months)

```
config                                           fill   TP2    SL     WR      net      PF   per-trade
----------------------------------------------------------------------------------------------------
ALL | baseline           | next_open            1312   992   315  75.6%   -27.41    0.91    -0.021 R
ALL | baseline           | pullback_236         1160   799   354  68.9%  +113.93    1.32    +0.098 R

ALL | optimized          | next_open             193   150    42  77.7%    +2.41    1.06    +0.012 R
ALL | optimized          | pullback_236          167   115    50  68.9%   +17.35    1.35    +0.104 R

ALL | optimized_no_round | next_open             293   228    64  77.8%    +3.69    1.06    +0.013 R
ALL | optimized_no_round | pullback_236          256   181    73  70.7%   +33.00    1.45    +0.129 R

```

## Month-over-month WR for the 3 most-relevant configs

Looking for stability of the WR across months. A real edge
shows roughly the same WR every month; a curve-fit shows a
blowout in one month and average elsewhere.

```
month       baseline+pull       optimized+pull      opt_no_round+pull 
---------------------------------------------------------------------------
2025-01       3t 33.3% PF0.58     1t  0.0% PF0.00     1t  0.0% PF0.00 
2025-02       7t 71.4% PF2.93     0t  0.0% PF0.00     2t 100.0% PFinf 
2025-03       2t 50.0% PFinf      0t  0.0% PF0.00     0t  0.0% PF0.00 
2025-04      61t 67.2% PF1.20     4t 25.0% PF0.20     6t 33.3% PF0.29 
2025-05      25t 72.0% PF1.51     5t 80.0% PF2.34     5t 80.0% PF2.34 
2025-06      15t 66.7% PF1.17     1t 100.0% PFinf     1t 100.0% PFinf 
2025-07       3t 100.0% PFinf     0t  0.0% PF0.00     0t  0.0% PF0.00 
2025-08       4t 25.0% PF0.20     1t  0.0% PF0.00     1t  0.0% PF0.00 
2025-09       7t 57.1% PF0.78     0t  0.0% PF0.00     1t 100.0% PFinf 
2025-10     144t 67.4% PF1.21    23t 69.6% PF1.34    33t 72.7% PF1.56 
2025-11      52t 75.0% PF1.76     6t 50.0% PF0.59    10t 70.0% PF1.37 
2025-12      44t 68.2% PF1.60     5t 40.0% PF0.59     7t 42.9% PF0.59 
2026-01     141t 66.7% PF1.20    32t 59.4% PF0.86    44t 59.1% PF0.85 
2026-02     200t 71.5% PF1.47    21t 71.4% PF1.46    42t 73.8% PF1.65 
2026-03     254t 72.8% PF1.57    42t 81.0% PF2.49    63t 79.4% PF2.25 
2026-04     133t 63.2% PF1.00    17t 70.6% PF1.41    30t 70.0% PF1.37 
2026-05      65t 66.2% PF1.14     9t 88.9% PF4.68    10t 90.0% PF5.27 
```

