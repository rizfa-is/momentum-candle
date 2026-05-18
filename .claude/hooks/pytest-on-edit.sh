#!/usr/bin/env bash
# pytest-on-edit.sh — fast feedback test runner triggered by file edits.
# Runs `pytest -x` only when a .py file under src/ or tests/ was changed.

set -euo pipefail

proj_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
payload="$(cat || true)"

files="$(
  echo "$payload" \
    | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]+"' \
    | sed -E 's/.*"file_path"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' \
    | sort -u
)"

run_tests=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    *src/*\.py|*tests/*\.py)
      run_tests=1
      ;;
  esac
done <<< "$files"

if [[ "$run_tests" == "0" ]]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "pytest-on-edit hook: uv not found in PATH; skipping" >&2
  exit 0
fi

# Non-blocking — surface failures via stderr but never exit 2.
if ! ( cd "$proj_dir" && uv run pytest -x --no-header -q 2>&1 ); then
  echo "pytest-on-edit hook: tests failed (non-blocking)" >&2
fi

exit 0
