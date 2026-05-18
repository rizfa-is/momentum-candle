from __future__ import annotations

from mt5_mvp import trade


def _setup_symbol(mt5, *, bid=2350.10, ask=2350.50):
    mt5.symbol_select.return_value = True

    class Tick:
        def __init__(self):
            self.time = 1700000000
            self.bid = bid
            self.ask = ask
            self.last = ask
            self.volume = 1234

    class Info:
        spread = 40
        filling_mode = 2  # IOC
        volume_min = 0.01
        volume_max = 100.0
        volume_step = 0.01

    mt5.symbol_info_tick.return_value = Tick()
    mt5.symbol_info.return_value = Info()


def test_dry_run_market_order_returns_synthetic(mt5, monkeypatch):
    monkeypatch.setenv("MT5_DRY_RUN", "1")
    _setup_symbol(mt5)

    out = trade.place_market_order("XAUUSD", "BUY", 0.01, sl=2340.0, tp=2360.0)
    assert out["dry_run"] is True
    req = out["request"]
    assert req["symbol"] == "XAUUSD"
    assert req["volume"] == 0.01
    assert req["price"] == 2350.50  # ask for BUY
    assert req["sl"] == 2340.0
    assert req["tp"] == 2360.0
    assert mt5.order_send.called is False


def test_dry_run_sell_uses_bid(mt5, monkeypatch):
    monkeypatch.setenv("MT5_DRY_RUN", "1")
    _setup_symbol(mt5)

    out = trade.place_market_order("XAUUSD", "SELL", 0.05)
    assert out["dry_run"] is True
    assert out["request"]["price"] == 2350.10  # bid for SELL


def test_volume_normalised_to_step(mt5, monkeypatch):
    monkeypatch.setenv("MT5_DRY_RUN", "1")
    _setup_symbol(mt5)

    out = trade.place_market_order("XAUUSD", "BUY", 0.027)
    # 0.027 → floor to step 0.01 → 0.02
    assert out["request"]["volume"] == 0.02


def test_invalid_side_returns_error(mt5):
    out = trade.place_market_order("XAUUSD", "HOLD", 0.01)
    assert "error" in out


def test_close_all_when_no_positions(mt5):
    mt5.positions_get.return_value = []
    out = trade.close_all_positions()
    assert out == {"closed": 0, "results": []}
