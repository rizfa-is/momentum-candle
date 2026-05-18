---
description: Run a code review against the current branch using the code-reviewer agent.
allowed-tools: Bash(git:*), Read, Grep
---

# /pr-review

Apply the `code-reviewer` agent's checklist to the diff between the
current branch and `main`.

## Steps

1. Determine the parent branch (default `main`):
   `!git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo main`
2. Show the changed files: `!git diff --name-only origin/main...HEAD`
3. For each changed file:
   - Read the new content with the Read tool.
   - Read the old content with `git show origin/main:<file>`.
   - Apply the `code-reviewer` agent (`.claude/agents/code-reviewer.md`)
     checklist.
4. Summarise findings grouped by severity:
   - BLOCKING (trade safety)
   - Correctness
   - Tests
   - Style
   - Architecture
5. Final line: `LGTM` / `Needs changes` / `Block`.

## Constraints

- Do NOT auto-fix anything. Report only.
- Cite `file:line` for every observation.
- Be terse. One sentence per issue.

## Optional argument

If `$ARGUMENTS` is non-empty, use it as the parent branch / ref instead
of `main`. Example: `/pr-review feat/momentum-candle-v0`.
