# Skills

Each subdirectory contains a `SKILL.md` with YAML frontmatter (`name`,
`description`) and project-specific guidance. Claude auto-suggests skills
based on `hooks/skill-rules.json`.

| Skill | When it fires |
|---|---|
| `mt5-python-api` | Working with MetaTrader5 lib internals — filling modes, retcodes, init flow. |
| `mcp-fastmcp` | Editing the FastMCP server, registering tools, choosing transports. |
| `trading-safety` | Anything touching destructive trade tools, dry-run, or magic numbers. |
| `pytest-mt5` | Writing tests; needs the mocked MetaTrader5 fixture. |
| `uv-python-tooling` | Adding/removing deps, syncing the lockfile, Python version pins. |
| `candlestick-strategy` | Momentum-candle strategy work on XAUUSD. |

## Adding a new skill

1. Create `<skill-name>/SKILL.md` with frontmatter:
   ```
   ---
   name: <skill-name>
   description: ...keywords trigger this; what to do when it fires...
   ---
   ```
2. Add a matching entry in `hooks/skill-rules.json` with keywords and
   intent patterns.
3. Keep the body under ~300 lines. Link out to longer docs.
