from __future__ import annotations

import pytest

from mt5_mvp import constants


def test_timeframe_map_has_all_expected_keys():
    expected = {
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "M6",
        "M10",
        "M12",
        "M15",
        "M20",
        "M30",
        "H1",
        "H2",
        "H3",
        "H4",
        "H6",
        "H8",
        "H12",
        "D1",
        "W1",
        "MN1",
    }
    assert expected.issubset(set(constants.TIMEFRAME_MAP))


def test_resolve_timeframe_case_insensitive():
    assert constants.resolve_timeframe("h1") == constants.resolve_timeframe("H1")


def test_resolve_timeframe_unknown_raises():
    with pytest.raises(ValueError):
        constants.resolve_timeframe("X9")


def test_resolve_order_type_round_trip():
    for side in ("BUY", "SELL", "BUY_LIMIT", "SELL_STOP"):
        n = constants.resolve_order_type(side)
        assert constants.ORDER_TYPE_REVERSE[n] == side


def test_resolve_filling_unknown_raises():
    with pytest.raises(ValueError):
        constants.resolve_filling("MAYBE")
