#!/usr/bin/env python3
"""Install the repository's portable Git pre-push hook."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_BODY = """#!/usr/bin/env bash
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$repo_root" || exit 0
bash "$repo_root/scripts/_pyrun.sh" "$repo_root/scripts/log_antigravity.py" --auto || true
venv_python="$repo_root/.venv/bin/python"
if [ ! -x "$venv_python" ]; then
  venv_python="$repo_root/.venv/Scripts/python.exe"
fi
if [ -x "$venv_python" ]; then
  "$venv_python" "$repo_root/scripts/submit_log.py" || true
else
  bash "$repo_root/scripts/_pyrun.sh" "$repo_root/scripts/submit_log.py" || true
fi
exit 0
"""


def main() -> None:
    hook_path = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-path", "hooks/pre-push"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    )
    if not hook_path.is_absolute():
        hook_path = REPO_ROOT / hook_path
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(HOOK_BODY, encoding="utf-8", newline="\n")
    hook_path.chmod(hook_path.stat().st_mode | 0o111)
    (REPO_ROOT / ".ai-log").mkdir(exist_ok=True)
    (REPO_ROOT / ".ai-log" / ".gitkeep").touch()
    print(f"[ai-log] Git pre-push hook installed: {os.path.relpath(hook_path, REPO_ROOT)}")


if __name__ == "__main__":
    main()
