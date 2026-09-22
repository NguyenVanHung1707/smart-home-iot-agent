#!/usr/bin/env python3
"""Log AI use from web tools that cannot run repository hooks."""

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
REPO_ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def interactive_mode() -> tuple[str, str, str, str]:
    tool = input("Tool (chatgpt, gemini-web, claude-web, ...): ").strip() or "unknown"
    model = input("Model (optional): ").strip() or tool
    prompt = input("Prompt or task summary: ").strip()
    if not prompt:
        raise SystemExit("[ai-log] Prompt cannot be empty.")
    return tool, model, prompt, input("Result summary (optional): ").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool")
    parser.add_argument("--prompt")
    parser.add_argument("--model")
    parser.add_argument("--result", default="")
    args = parser.parse_args()
    if args.tool and args.prompt:
        tool, model, prompt, result = (args.tool, args.model or args.tool, args.prompt, args.result)
    else:
        tool, model, prompt, result = interactive_mode()

    origin = git("remote", "get-url", "origin")
    repo = origin.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log")).expanduser()
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(VN_TZ)
    entry = {
        "ts": now.isoformat(),
        "tool": tool,
        "event": "ManualLog",
        "entry_id": f"manual-{now.strftime('%Y%m%d-%H%M%S-%f')}",
        "model": model,
        "repo": repo.removesuffix(".git") or REPO_ROOT.name,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "--short", "HEAD"),
        "student": git("config", "user.email") or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        "prompt": prompt[:1000],
        "response_summary": result[:500],
    }
    log_file = log_dir / "session.jsonl"
    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[ai-log] Logged [{tool}] to {log_file}")


if __name__ == "__main__":
    main()
