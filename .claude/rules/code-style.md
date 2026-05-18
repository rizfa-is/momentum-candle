---
name: code-style
description: Code style rules for momentum-candle. Type hints, logging, error handling, no print() in stdio mode.
---

# Code style

## Type hints — mandatory

Every public function gets type hints. `Any` is allowed for MT5
namedtuples and dynamic dicts. The `ANN` ruff rule enforces this.

```python
def get_account() -> dict[str, Any]:        # good
def get_account():                          # bad — missing return type
```

## Logging, never print()

`print()` corrupts the stdio JSON-RPC stream. Always:

```python
import logging
log = logging.getLogger("mt5mcp")
log.info("connected")
```

`logging.basicConfig(stream=sys.stderr, ...)` is set in `cli.py` so all
log records go to stderr. The ruff rule `T20` blocks `print` in source
code; tests are exempt.

## Error handling — return dicts, don't raise

MCP tools must return structured data, not raise. Every error becomes:

```python
return {"error": "human readable reason"}
```

Reserve exceptions for genuinely exceptional internal bugs.

## Imports

Three groups, sorted alphabetically within each (ruff handles this):

```python
# stdlib
import os
from typing import Any

# third-party
import MetaTrader5 as mt5

# local
from ._utils import to_dict
```

## Naming

- Modules: snake_case, short (`trade.py`, not `trade_handlers.py`).
- Public functions: snake_case verbs (`place_market_order`).
- Classes: PascalCase. Avoid them when a function suffices.
- Magic constants: SCREAMING_SNAKE in module scope.

## Docstrings

Every public function gets a one-line summary plus param list when args
are non-obvious. The MCP server uses these as tool descriptions seen by
the AI client — write for that audience.

## Limit retries and side effects

Retries on broker errors belong in a single, well-tested place
(eventually `mt5_signals/executor.py`). Handlers return one attempt's
result. Do not silently re-send orders.
