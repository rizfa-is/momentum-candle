"""Strategy detectors.

Each strategy module exports a ``scan(...)`` function that takes a candle
list (as produced by ``mt5_mvp.market.get_candles_latest``) and returns
zero or more ``Setup`` objects.
"""

from .base import Setup

__all__ = ["Setup"]
