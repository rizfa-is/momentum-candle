"""Account-info handlers."""

from __future__ import annotations

from typing import Any

import MetaTrader5 as mt5

from ._utils import last_error_msg, to_dict


def get_account() -> dict[str, Any]:
    """Return current trading account info as a plain dict."""
    info = mt5.account_info()
    if info is None:
        return {"error": f"account_info() failed: {last_error_msg()}"}
    data = to_dict(info) or {}
    # Trim to the fields signal-bots actually need.
    keep = (
        "login",
        "name",
        "server",
        "currency",
        "leverage",
        "balance",
        "equity",
        "profit",
        "margin",
        "margin_free",
        "margin_level",
        "trade_allowed",
        "trade_mode",
        "company",
    )
    return {k: data[k] for k in keep if k in data}
