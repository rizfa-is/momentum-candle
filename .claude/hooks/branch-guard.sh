#!/usr/bin/env bash
# branch-guard.sh — block edits when on main/master.
# Hook payload comes in on stdin as JSON; we don't need to parse it.

set -euo pipefail

# Resolve the project's git directory (best-effort — we may be in a worktree).
proj_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# git may not be on PATH in some Claude environments; fall back gracefully.
if ! command -v git >/dev/null 2>&1; then
  exit 0
fi

branch="$(git -C "$proj_dir" branch --show-current 2>/dev/null || true)"

if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  cat >&2 <<EOF
{"block": true, "message": "Refuse to edit on protected branch '$branch'. Create a feature branch first: git checkout -b feat/<scope>"}
EOF
  exit 2
fi

exit 0
