---
name: mcp-fastmcp
description: FastMCP server patterns. Use when registering MCP tools, choosing transports, setting hints, or editing src/mt5_mvp/server.py and cli.py.
---

# FastMCP — patterns we use

## Tool registration

```python
from fastmcp import FastMCP

mcp = FastMCP("mt5-mvp", instructions="...")

@mcp.tool(annotations={"readOnlyHint": True})
def get_account() -> dict:
    """Docstring becomes the tool description shown to the AI client."""
    ...
```

## Annotations matter

| Hint | Meaning | Use for |
|---|---|---|
| `readOnlyHint: True` | Safe, no side effects | account/market reads |
| `destructiveHint: True` | Has irreversible effects | every order/trade tool |
| `idempotentHint: True` | Same call same result | rare in trading |
| `openWorldHint: True` | Touches external systems | not used here |

Set them honestly. Well-behaved clients (Claude, opencode) prompt the user
before running destructive tools.

## Global instructions

`FastMCP("name", instructions="...")` accepts a system-style preamble that
the AI client receives at discovery time. Use it for rules the AI must
follow on every call (e.g. "always check account before placing trades").

## Transports

| Transport | Use case |
|---|---|
| `stdio` | Local Claude Desktop / opencode (default) |
| `sse` | Remote MCP for VPS scenarios; needs network access |
| `streamable-http` | Newer streaming HTTP variant |

Switch via `mcp.run(transport="sse", host="...", port=...)`.

## Logging on stdio — never print()

stdio transport multiplexes JSON-RPC over stdout. A stray `print()`
corrupts the stream and the client disconnects.

```python
import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("mt5mcp")
log.info("safe — goes to stderr")
```

## Type hints drive schemas

FastMCP generates JSON Schema from your function signature. Use precise
types:

```python
def place_market_order(
    symbol: str,
    side: str,                     # consider Literal["BUY", "SELL"] later
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
) -> dict[str, Any]:
    ...
```

`Literal[...]` produces enum schemas (better autocompletion in clients).
Avoid bare `dict` returns where possible — `dict[str, Any]` is fine.

## `_ensure()` pattern

Every tool calls a shared connection check:

```python
def _ensure() -> dict[str, Any] | None:
    if not ensure_initialized():
        return {"error": "MT5 terminal not connected"}
    return None

@mcp.tool(annotations={"readOnlyHint": True})
def get_account() -> dict:
    if (err := _ensure()) is not None:
        return err
    return account.get_account()
```

Keeps each tool small and consistent.
