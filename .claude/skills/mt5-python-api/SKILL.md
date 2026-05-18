---
name: mt5-python-api
description: MetaTrader5 Python lib quirks. Use when working with mt5.* calls, filling modes, retcodes, symbol_info, copy_rates, order_send, account/terminal init. Covers InstaForex demo specifics.
---

# MT5 Python API — what to remember

## Initialise once, gracefully

`mt5.initialize()` and `mt5.login()` are global on the process. Wrap every
blocking MT5 call in a thread with timeout (see `src/mt5_mvp/client.py`).
A hung terminal will lock the process otherwise.

```python
from mt5_mvp.client import ensure_initialized
if not ensure_initialized():
    return {"error": "MT5 not connected"}
```

## Symbol selection is mandatory before quotes

`symbol_select(symbol, True)` must succeed before `symbol_info_tick` or
`copy_rates_*` will return data. Skip it and you get `None`.

## Filling modes — broker-dependent

`symbol_info(symbol).filling_mode` is a bitmask, **not** a single value.

| Bit | Meaning |
|---|---|
| 1 | FOK supported |
| 2 | IOC supported |
| neither | broker uses RETURN |

InstaForex demo for XAUUSD typically allows IOC. Always pass the detected
filling mode in `request["type_filling"]`.

## Volume normalisation

Read `volume_min`, `volume_max`, `volume_step` from `symbol_info`. Round
**down** to the nearest step:

```python
steps = int(volume / step)
volume = round(steps * step, 8)
```

Sending an off-step volume returns retcode `10014` (invalid volume).

## copy_rates_from_pos returns numpy arrays, not namedtuples

Cannot use `_asdict()`. Index by position:

```
rates[i][0] -> time (epoch)
rates[i][1] -> open
rates[i][2] -> high
rates[i][3] -> low
rates[i][4] -> close
rates[i][5] -> tick_volume
rates[i][6] -> spread
rates[i][7] -> real_volume
```

## Common retcodes

| Code | Meaning |
|---|---|
| 10009 | Request completed (success) |
| 10013 | Invalid request |
| 10014 | Invalid volume |
| 10015 | Invalid price |
| 10016 | Invalid stops |
| 10018 | Market closed |
| 10019 | Insufficient funds |
| 10027 | Autotrading disabled in client terminal |

`_utils.describe_retcode()` maps these. Always include `retcode_text` in
trade tool responses so the AI explains errors clearly.

## Time handling

MT5 returns Unix epoch seconds. Never trust local clock for trade
decisions — use `mt5.symbol_info_tick().time` as the authoritative time.

## Shutdown is best-effort

`mt5.shutdown()` may raise on already-disconnected terminals. Wrap in a
try/except and log; do not propagate.
