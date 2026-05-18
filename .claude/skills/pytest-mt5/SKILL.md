---
name: pytest-mt5
description: Mocking MetaTrader5 module for unit tests. Use when writing pytest tests, fixtures, integration test gating, or anything in tests/.
---

# pytest with mocked MetaTrader5

## The conftest pattern

`tests/conftest.py` registers a stub `MetaTrader5` module in `sys.modules`
**before** any test imports the project. This is the only reliable way to
test on machines without MT5 installed.

```python
import sys, types
from unittest.mock import MagicMock

mt5_stub = types.ModuleType("MetaTrader5")
# ... set constants and MagicMock methods ...
sys.modules["MetaTrader5"] = mt5_stub
```

Tests that need to assert on calls receive the stub via the `mt5` fixture:

```python
def test_dry_run_buy(mt5, monkeypatch):
    monkeypatch.setenv("MT5_DRY_RUN", "1")
    mt5.symbol_info_tick.return_value = SomeTick(...)
    out = trade.place_market_order("XAUUSD", "BUY", 0.01)
    assert out["dry_run"] is True
```

## Reset between tests

The autouse `_reset_mt5_mocks` fixture resets all `MagicMock`s and
restores defaults (`symbol_select.return_value = True`,
`last_error.return_value = (0, "no error")`).

If a test sets attributes you forget about, prefer `monkeypatch.setattr`
so they're undone automatically.

## Integration tests against a live demo

Mark tests that need a real terminal:

```python
@pytest.mark.integration
def test_real_account_info():
    ...
```

Run only when explicitly requested:

```powershell
$env:MT5_INTEGRATION="1"
uv run pytest -m integration
```

CI never runs integration tests.

## Patterns to avoid

- Do **not** import `MetaTrader5` at the top of test files; it pulls
  the stub which shadows project constants if conftest hasn't run yet.
  Import the stub via the `mt5` fixture instead.
- Do **not** use `time.sleep` in unit tests; use `monkeypatch` to fake
  timers.
- Do **not** assert on full request dicts — they include nondeterministic
  fields like `magic`. Pick out the keys you care about.

## Speedy feedback loop

`uv run pytest -x --no-header -q` is what the `pytest-on-edit` hook runs.
Tests should be quick (<3s total for the unit suite) and import-light.
