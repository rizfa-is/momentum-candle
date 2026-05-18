from __future__ import annotations

from mt5_mvp import client


def test_run_with_timeout_returns_result():
    assert client._run_with_timeout(lambda: 42, timeout=1.0) == 42


def test_run_with_timeout_handles_hang(monkeypatch):
    import time

    def slow():
        time.sleep(2.0)
        return "late"

    assert client._run_with_timeout(slow, timeout=0.1) is None


def test_run_with_timeout_swallows_exceptions():
    def boom():
        raise RuntimeError("nope")

    assert client._run_with_timeout(boom, timeout=1.0) is None


def test_ensure_initialized_when_terminal_alive_and_logged_in(mt5):
    mt5.terminal_info.return_value = object()
    mt5.account_info.return_value = type("A", (), {"login": 94682256})()
    assert client.ensure_initialized() is True


def test_ensure_initialized_calls_init_when_terminal_dead(mt5, monkeypatch):
    mt5.terminal_info.return_value = None
    called = {"n": 0}

    def fake_init():
        called["n"] += 1
        return True

    monkeypatch.setattr(client, "init_mt5", fake_init)
    assert client.ensure_initialized() is True
    assert called["n"] == 1


def test_ensure_initialized_attempts_login_when_not_logged_in(mt5, monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "94682256")
    monkeypatch.setenv("MT5_PASSWORD", "x")
    monkeypatch.setenv("MT5_SERVER", "InstaForex-Server")
    mt5.terminal_info.return_value = object()
    mt5.account_info.return_value = type("A", (), {"login": 0})()
    mt5.login.return_value = True
    assert client.ensure_initialized() is True
    assert mt5.login.called
