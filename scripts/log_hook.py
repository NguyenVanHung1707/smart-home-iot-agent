#!/usr/bin/env python3
"""
Shared AI hook logger — works with Claude Code, Codex, Cursor, and Copilot.
Reads JSON from stdin, normalizes to common format, appends to .ai-log/session.jsonl
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
REPO_ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def detect_tool(data: dict) -> str:
    """Detect which AI tool sent this hook event.

    Priority:
      1. --tool=NAME CLI argument (cross-platform: works in cmd.exe, PowerShell, bash)
      2. AI_TOOL_NAME env var (legacy, bash-only when set inline)
      3. Heuristics from payload shape
    """
    for arg in sys.argv[1:]:
        if arg.startswith("--tool="):
            return arg.split("=", 1)[1].lower()
    tool_env = os.environ.get("AI_TOOL_NAME", "").lower()
    if tool_env:
        return tool_env
    # Heuristics
    if "transcript_path" in data:
        return "codex"
    if data.get("hook_event_name", "")[0:1].islower():
        # camelCase event names → Cursor or Copilot
        if "workspace_roots" in data:
            return "cursor"
        if "toolName" in data:
            return "copilot"
    if "hook_event_name" in data:
        return "claude"
    return "unknown"


def normalize(data: dict, tool: str) -> dict | None:
    """Normalize tool-specific payload to common log entry."""
    event = data.get("hook_event_name") or data.get("event", "")
    if not event and tool == "copilot":
        event = "userPromptSubmitted" if "prompt" in data else "sessionEnd" if "reason" in data else ""
    ts = datetime.now(VN_TZ).isoformat()

    # Resolve repo from git origin. When cwd is not a git working tree (or
    # origin isn't set), skip the event entirely — these entries can't be
    # tied back to a team on the server and would just clutter the pending
    # queue forever.
    origin = git("remote", "get-url", "origin")
    if not origin:
        return None
    repo = origin.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    base = {
        "ts": ts,
        "tool": tool,
        "event": event,
        "session_id": (
            data.get("session_id")
            or data.get("sessionId")
            or data.get("conversation_id")
            or data.get("generation_id")
            or ""
        ),
        "model": data.get("model", ""),
        "repo": repo,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "--short", "HEAD"),
        "student": git("config", "user.email"),
    }

    if tool == "claude":
        prompt = ""
        # UserPromptSubmit: prompt is at top level
        if event == "UserPromptSubmit":
            prompt = data.get("prompt", "")[:1000]
        # PostToolUse: extract from tool_input
        elif isinstance(data.get("tool_input"), dict):
            prompt = data["tool_input"].get("prompt") or data["tool_input"].get("content") or ""
        base.update(
            {
                "prompt": prompt,
                "tool_name": data.get("tool_name", ""),
                "tool_input": data.get("tool_input") if event != "UserPromptSubmit" else None,
                "tool_response": str(data.get("tool_response", ""))[:500],
            }
        )

    elif tool == "codex":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "turn_id": data.get("turn_id", ""),
                "transcript_path": data.get("transcript_path", ""),
            }
        )

    elif tool == "cursor":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "files_context": data.get("attachments", []),
            }
        )

    elif tool == "copilot":
        base.update(
            {
                "prompt": data.get("prompt", "")[:1000],
                "tool_name": data.get("toolName", ""),
                "tool_args": data.get("toolArgs"),
            }
        )

    # Skip only true noise: no prompt AND no tool-specific payload (tool_input,
    # response_summary, tool_response, tool_args, files_context). Previously
    # this only checked `prompt`, which dropped Claude Bash/Edit events (their
    # tool_input has `command` / `file_path`, not `prompt` or `content`) and
    # any Cursor/Copilot turn that carried context but no plain prompt.
    payload_keys = ("prompt", "tool_input", "response_summary", "tool_response", "tool_args", "files_context")
    lifecycle_events = ("Stop", "stop", "SessionEnd", "sessionEnd")
    has_payload = any(base.get(key) for key in payload_keys)
    if not has_payload and event not in lifecycle_events:
        return None

    return base


def main():
    # Read stdin as UTF-8 explicitly. On Windows, sys.stdin defaults to the
    # system code page (e.g. cp1252), which corrupts non-Latin1 prompts
    # (Vietnamese, CJK, emoji) into mojibake. The hook payload is always UTF-8.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    if not raw:
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = detect_tool(data)
    entry = normalize(data, tool)
    if not entry:
        sys.exit(0)

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log")).expanduser()
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "session.jsonl"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Hook runners parse stdout as a decision, so use each runner's schema.
    if tool == "codex":
        print(json.dumps({"continue": True}))
    elif tool == "cursor":
        print(json.dumps({"continue": True}) if entry["event"] == "beforeSubmitPrompt" else "{}")


if __name__ == "__main__":
    main()
