#!/usr/bin/env bash
# live-trade-guard.sh — block destructive MT5 tool calls unless:
#   1. MT5_DRY_RUN=0 (live trading explicitly enabled in env), AND
#   2. the user prompt contains the literal token "CONFIRM_LIVE".
#
# Hook payload arrives on stdin as JSON: { tool, input, prompt, ... }.

set -euo pipefail

payload="$(cat || true)"

# Read MT5_DRY_RUN from .env if not already set in environment.
proj_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
env_file="$proj_dir/.env"
if [[ -z "${MT5_DRY_RUN:-}" && -f "$env_file" ]]; then
  # Extract MT5_DRY_RUN value from .env, ignoring quotes/spaces.
  raw="$(grep -E '^[[:space:]]*MT5_DRY_RUN[[:space:]]*=' "$env_file" | tail -n1 || true)"
  if [[ -n "$raw" ]]; then
    val="${raw#*=}"
    val="${val%%#*}"             # strip trailing comment
    val="$(echo "$val" | tr -d '"\047' | xargs)"
    export MT5_DRY_RUN="$val"
  fi
fi

dry="${MT5_DRY_RUN:-1}"

# Detect CONFIRM_LIVE in the user's prompt. The hook payload field name
# differs slightly across Claude Code versions; grep the whole JSON.
if echo "$payload" | grep -q "CONFIRM_LIVE"; then
  has_confirm=1
else
  has_confirm=0
fi

if [[ "$dry" == "0" && "$has_confirm" == "1" ]]; then
  exit 0
fi

reason="MT5_DRY_RUN=$dry"
if [[ "$has_confirm" == "0" ]]; then
  reason="$reason, prompt missing CONFIRM_LIVE token"
fi

cat >&2 <<EOF
{"block": true, "message": "Refusing destructive MT5 tool: $reason. To execute live trades, set MT5_DRY_RUN=0 in .env AND include CONFIRM_LIVE in the prompt."}
EOF
exit 2
