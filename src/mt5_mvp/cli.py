"""Command-line entrypoint for the MT5 MCP server.

Usage:
    uv run mt5-mvp                       # stdio (default — for Claude Desktop/opencode)
    uv run mt5-mvp --transport sse       # remote MCP over SSE
    uv run mt5-mvp --transport http      # streamable HTTP
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# stderr-only logging so stdio JSON-RPC stream is never corrupted.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("mt5mcp")


def _load_dotenv(start: Path | None = None) -> None:
    """Tiny .env loader — avoids adding python-dotenv as a dep for MVP."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        env = candidate / ".env"
        if env.is_file():
            try:
                for line in env.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
            except OSError:
                log.warning("Could not read %s", env)
            return


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mt5-mvp", description="MT5 MCP server (MVP)")
    p.add_argument(
        "--transport",
        choices=("stdio", "sse", "http"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio)",
    )
    p.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Bind host for sse/http (default: 127.0.0.1)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8765")),
        help="Bind port for sse/http (default: 8765)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = _build_parser().parse_args(argv)

    # Import here so a bad MT5 install fails with a useful message.
    from .server import mcp

    log.info(
        "Starting mt5-mvp transport=%s dry_run=%s server=%s",
        args.transport,
        os.getenv("MT5_DRY_RUN", "1"),
        os.getenv("MT5_SERVER", "(unset)"),
    )

    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
