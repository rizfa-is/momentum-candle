"""skill-eval.py — UserPromptSubmit hook.

Reads the hook payload from stdin, scores it against rules in
``skill-rules.json`` (keywords, regex patterns, intent patterns, file paths),
and emits a "SKILL ACTIVATION REQUIRED" block on stderr that the Claude
session can read.

Pure stdlib. Exit 0 always; non-blocking advisory output.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

WEIGHTS = {
    "keyword": 2,
    "keywordPattern": 3,
    "pathPattern": 4,
    "intentPattern": 4,
}

THRESHOLD = 4  # minimum score to surface a skill

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
RULES_PATH = PROJECT_DIR / ".claude" / "hooks" / "skill-rules.json"


def _read_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _extract_prompt(payload: dict[str, Any]) -> str:
    # Claude Code historically uses {"prompt": "..."} for UserPromptSubmit.
    for key in ("prompt", "user_prompt", "input"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            return v
    # Some payloads nest under tool_input/messages — fall back to JSON dump.
    return json.dumps(payload, ensure_ascii=False)


def _load_rules() -> dict[str, Any]:
    if not RULES_PATH.is_file():
        return {}
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"skill-eval: rules JSON invalid: {e}", file=sys.stderr)
        return {}


def _score(prompt: str, rules: dict[str, Any]) -> list[tuple[str, int, list[str]]]:
    p_lower = prompt.lower()
    results: list[tuple[str, int, list[str]]] = []

    for skill_name, cfg in rules.items():
        if not isinstance(cfg, dict):
            continue
        triggers = cfg.get("triggers") or {}
        score = 0
        reasons: list[str] = []

        for kw in triggers.get("keywords") or []:
            if kw.lower() in p_lower:
                score += WEIGHTS["keyword"]
                reasons.append(f'keyword "{kw}"')

        for pat in triggers.get("keywordPatterns") or []:
            try:
                if re.search(pat, prompt, re.IGNORECASE):
                    score += WEIGHTS["keywordPattern"]
                    reasons.append(f"pattern /{pat}/")
            except re.error:
                continue

        for pat in triggers.get("pathPatterns") or []:
            try:
                if re.search(pat, prompt):
                    score += WEIGHTS["pathPattern"]
                    reasons.append(f"path /{pat}/")
            except re.error:
                continue

        for pat in triggers.get("intentPatterns") or []:
            try:
                if re.search(pat, prompt, re.IGNORECASE):
                    score += WEIGHTS["intentPattern"]
                    reasons.append(f"intent /{pat}/")
            except re.error:
                continue

        excludes = cfg.get("excludePatterns") or []
        if any(re.search(x, prompt, re.IGNORECASE) for x in excludes):
            continue

        if score >= THRESHOLD:
            results.append((skill_name, score, reasons))

    results.sort(key=lambda r: r[1], reverse=True)
    return results


def _confidence(score: int) -> str:
    if score >= 10:
        return "HIGH"
    if score >= 6:
        return "MEDIUM"
    return "LOW"


def main() -> int:
    payload = _read_payload()
    prompt = _extract_prompt(payload)
    if not prompt.strip():
        return 0

    rules = _load_rules()
    if not rules:
        return 0

    matches = _score(prompt, rules)
    if not matches:
        return 0

    lines = ["SKILL ACTIVATION REQUIRED", ""]
    for i, (name, score, reasons) in enumerate(matches[:5], start=1):
        lines.append(f"{i}. {name} ({_confidence(score)} confidence, score={score})")
        if reasons:
            lines.append(f"   matched: {', '.join(reasons[:4])}")
    print("\n".join(lines), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
