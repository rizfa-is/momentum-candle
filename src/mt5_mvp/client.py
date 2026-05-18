"""MetaTrader 5 connection management.

Wraps every blocking MT5 call in a thread with timeout protection, so a hung
terminal cannot freeze the MCP server. Pattern adapted from the mql5.com
article (Muhammad Minhas Qamar, 2026).
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import Any

import MetaTrader5 as mt5

log = logging.getLogger("mt5mcp")

DEFAULT_INIT_TIMEOUT = 60
QUICK_TIMEOUT = 15


def _run_with_timeout[T](fn: Callable[[], T], timeout: float) -> T | None:
    """Run ``fn()`` in a daemon thread; return None if it does not complete in time."""
    result: list[T | None] = [None]
    exc: list[BaseException | None] = [None]

    def worker() -> None:
        try:
            result[0] = fn()
        except BaseException as e:  # propagate via list
            exc[0] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        log.warning("MT5 call timed out after %.1fs", timeout)
        return None
    if exc[0] is not None:
        log.exception("MT5 call raised", exc_info=exc[0])
        return None
    return result[0]


def _config() -> dict[str, Any]:
    """Read MT5 connection config from environment."""
    return {
        "login": os.getenv("MT5_LOGIN", "").strip() or None,
        "password": os.getenv("MT5_PASSWORD", "") or None,
        "server": os.getenv("MT5_SERVER", "").strip() or None,
        "path": os.getenv("MT5_PATH", "").strip() or None,
        "timeout": int(os.getenv("MT5_TIMEOUT", str(DEFAULT_INIT_TIMEOUT))),
    }


def init_mt5() -> bool:
    """Initialise the MT5 terminal and (optionally) log in.

    Returns True on success, False otherwise.
    """
    cfg = _config()
    init_kwargs: dict[str, Any] = {"timeout": cfg["timeout"] * 1000}
    if cfg["path"]:
        init_kwargs["path"] = cfg["path"]
    if cfg["login"]:
        try:
            init_kwargs["login"] = int(cfg["login"])
        except ValueError:
            log.error("MT5_LOGIN must be an integer, got %r", cfg["login"])
            return False
    if cfg["password"]:
        init_kwargs["password"] = cfg["password"]
    if cfg["server"]:
        init_kwargs["server"] = cfg["server"]

    ok = _run_with_timeout(lambda: mt5.initialize(**init_kwargs), timeout=cfg["timeout"])
    if not ok:
        log.error("MT5 initialize() failed: %s", mt5.last_error())
        return False
    log.info("MT5 initialised")
    return True


def ensure_initialized() -> bool:
    """Ensure terminal is responding and account is logged in.

    Three-step check (mql5 article pattern):
    1. ``terminal_info()`` reachable within QUICK_TIMEOUT.
    2. ``account_info()`` returns non-zero login.
    3. If not logged in and credentials are configured, attempt ``login()``.
    """
    info = _run_with_timeout(mt5.terminal_info, timeout=QUICK_TIMEOUT)
    if info is None:
        log.warning("Terminal not responding; running full init")
        return init_mt5()

    acc = _run_with_timeout(mt5.account_info, timeout=QUICK_TIMEOUT)
    if acc is not None and getattr(acc, "login", 0) != 0:
        return True

    cfg = _config()
    if not cfg["login"]:
        # Assume the user is already logged in via the GUI.
        return True

    log.info("Not logged in; attempting login()")
    return bool(
        _run_with_timeout(
            lambda: mt5.login(
                login=int(cfg["login"]),
                password=cfg["password"],
                server=cfg["server"],
            ),
            timeout=cfg["timeout"],
        )
    )


def shutdown() -> None:
    """Close the MT5 connection."""
    try:
        mt5.shutdown()
    except Exception:
        log.exception("MT5 shutdown raised")
