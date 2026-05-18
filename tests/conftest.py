"""Test fixtures and global mocks.

The real ``MetaTrader5`` package is Windows-only and requires a running
terminal. We register a stub module *before* any project import touches it,
so unit tests can run anywhere.
"""

from __future__ import annotations

import sys
import types
from collections import namedtuple
from typing import Any
from unittest.mock import MagicMock

import pytest

# --- Build a fake MetaTrader5 module --------------------------------------

mt5_stub: Any = types.ModuleType("MetaTrader5")

# Constants used by the project ------------------------------------------------

# Timeframes (values arbitrary but stable; real lib uses encoded ints)
_TF_VALUES = {
    "TIMEFRAME_M1": 1,
    "TIMEFRAME_M2": 2,
    "TIMEFRAME_M3": 3,
    "TIMEFRAME_M4": 4,
    "TIMEFRAME_M5": 5,
    "TIMEFRAME_M6": 6,
    "TIMEFRAME_M10": 10,
    "TIMEFRAME_M12": 12,
    "TIMEFRAME_M15": 15,
    "TIMEFRAME_M20": 20,
    "TIMEFRAME_M30": 30,
    "TIMEFRAME_H1": 16385,
    "TIMEFRAME_H2": 16386,
    "TIMEFRAME_H3": 16387,
    "TIMEFRAME_H4": 16388,
    "TIMEFRAME_H6": 16390,
    "TIMEFRAME_H8": 16392,
    "TIMEFRAME_H12": 16396,
    "TIMEFRAME_D1": 16408,
    "TIMEFRAME_W1": 32769,
    "TIMEFRAME_MN1": 49153,
}
for k, v in _TF_VALUES.items():
    setattr(mt5_stub, k, v)

# Order types
_OT_VALUES = {
    "ORDER_TYPE_BUY": 0,
    "ORDER_TYPE_SELL": 1,
    "ORDER_TYPE_BUY_LIMIT": 2,
    "ORDER_TYPE_SELL_LIMIT": 3,
    "ORDER_TYPE_BUY_STOP": 4,
    "ORDER_TYPE_SELL_STOP": 5,
}
for k, v in _OT_VALUES.items():
    setattr(mt5_stub, k, v)

# Filling modes
mt5_stub.ORDER_FILLING_FOK = 0
mt5_stub.ORDER_FILLING_IOC = 1
mt5_stub.ORDER_FILLING_RETURN = 2

# Time-in-force
mt5_stub.ORDER_TIME_GTC = 0
mt5_stub.ORDER_TIME_DAY = 1
mt5_stub.ORDER_TIME_SPECIFIED = 2
mt5_stub.ORDER_TIME_SPECIFIED_DAY = 3

# Trade actions
mt5_stub.TRADE_ACTION_DEAL = 1
mt5_stub.TRADE_ACTION_PENDING = 5
mt5_stub.TRADE_ACTION_SLTP = 6
mt5_stub.TRADE_ACTION_MODIFY = 7
mt5_stub.TRADE_ACTION_REMOVE = 8
mt5_stub.TRADE_ACTION_CLOSE_BY = 10

# Trade retcodes
mt5_stub.TRADE_RETCODE_DONE = 10009

# Functions — replaced per-test as needed via monkeypatch
mt5_stub.initialize = MagicMock(return_value=True)
mt5_stub.shutdown = MagicMock(return_value=None)
mt5_stub.login = MagicMock(return_value=True)
mt5_stub.terminal_info = MagicMock(return_value=MagicMock(community_account=False))
mt5_stub.account_info = MagicMock()
mt5_stub.symbol_select = MagicMock(return_value=True)
mt5_stub.symbol_info = MagicMock()
mt5_stub.symbol_info_tick = MagicMock()
mt5_stub.copy_rates_from_pos = MagicMock(return_value=[])
mt5_stub.positions_get = MagicMock(return_value=[])
mt5_stub.order_send = MagicMock()
mt5_stub.last_error = MagicMock(return_value=(0, "no error"))

sys.modules["MetaTrader5"] = mt5_stub


# --- Helpers --------------------------------------------------------------

AccountTuple = namedtuple(
    "AccountInfo",
    "login name server currency leverage balance equity profit margin "
    "margin_free margin_level trade_allowed trade_mode company",
)
TickTuple = namedtuple("Tick", "time bid ask last volume")
SymbolInfoTuple = namedtuple(
    "SymbolInfo",
    "name spread filling_mode volume_min volume_max volume_step",
)
PositionTuple = namedtuple(
    "Position",
    "ticket time type volume symbol price_open sl tp price_current profit swap magic comment",
)
OrderResultTuple = namedtuple(
    "OrderResult",
    "retcode deal order volume price comment request_id retcode_external",
)


@pytest.fixture
def mt5() -> Any:
    """The mocked MetaTrader5 module (already in sys.modules)."""
    return mt5_stub


@pytest.fixture(autouse=True)
def _reset_mt5_mocks() -> None:
    """Reset all MagicMocks between tests so state does not leak."""
    for name in (
        "initialize",
        "shutdown",
        "login",
        "terminal_info",
        "account_info",
        "symbol_select",
        "symbol_info",
        "symbol_info_tick",
        "copy_rates_from_pos",
        "positions_get",
        "order_send",
        "last_error",
    ):
        m = getattr(mt5_stub, name)
        m.reset_mock()
    # Restore defaults that downstream code expects.
    mt5_stub.symbol_select.return_value = True
    mt5_stub.last_error.return_value = (0, "no error")
