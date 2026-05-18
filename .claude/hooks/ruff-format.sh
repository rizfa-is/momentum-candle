#!/usr/bin/env bash
# ruff-format.sh — format and auto-fix Python files after Edit/Write.
# Reads the hook payload from stdin, extracts the file path(s), and runs
# ruff only on Python files inside this project.

set -euo pipefail

proj_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
payload="$(cat || true)"

# Extract a file_path from typical hook payloads.
# Supports both single Edit/Write and MultiEdit shapes.
files="$(
  echo "$payload" \
    | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]+"' \
    | sed -E 's/.*"file_path"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' \
    | sort -u
)"

if [[ -z "$files" ]]; then
  exit 0
fi

py_files=()
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    *.py) py_files+=("$f") ;;
  esac
done <<< "$files"

if [[ ${#py_files[@]} -eq 0 ]]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ruff-format hook: uv not found in PATH; skipping" >&2
  exit 0
fi

# Format then lint-fix. Both calls are best-effort; we never block.
( cd "$proj_dir" && uv run ruff format "${py_files[@]}" >/dev/null 2>&1 ) || true
( cd "$proj_dir" && uv run ruff check --fix --unsafe-fixes "${py_files[@]}" >/dev/null 2>&1 ) || true

exit 0
