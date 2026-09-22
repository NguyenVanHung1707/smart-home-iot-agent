import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.log_antigravity import _conv_matches_repo, _normalize
from scripts.setup_hooks import HOOK_BODY

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_path_matching_is_separator_safe(tmp_path):
    repo = _normalize(str(tmp_path / "HomeMind"))

    assert _conv_matches_repo({_normalize(str(tmp_path))}, repo)
    assert _conv_matches_repo({_normalize(str(tmp_path / "HomeMind" / "src"))}, repo)
    assert not _conv_matches_repo({_normalize(str(tmp_path / "HomeMind-old"))}, repo)


def test_pre_push_hook_resolves_repo_root():
    assert "git rev-parse --show-toplevel" in HOOK_BODY
    assert '"$repo_root/scripts/_pyrun.sh"' in HOOK_BODY


@pytest.mark.parametrize(
    ("tool", "payload", "expected"),
    [
        ("claude", {"hook_event_name": "UserPromptSubmit", "prompt": "test"}, ""),
        ("codex", {"hook_event_name": "UserPromptSubmit", "prompt": "test"}, '{"continue": true}'),
        ("codex", {"hook_event_name": "Stop"}, '{"continue": true}'),
        ("cursor", {"hook_event_name": "beforeSubmitPrompt", "prompt": "test"}, '{"continue": true}'),
        ("cursor", {"hook_event_name": "stop"}, "{}"),
        ("copilot", {"sessionId": "test", "prompt": "test"}, ""),
        ("copilot", {"sessionId": "test", "reason": "complete"}, ""),
    ],
)
def test_hook_output_contract(tmp_path, tool, payload, expected):
    env = os.environ | {"AI_LOG_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "scripts/log_hook.py", f"--tool={tool}"],
        cwd=REPO_ROOT,
        env=env,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == expected


def test_antigravity_stop_hook_returns_json(tmp_path):
    env = os.environ | {
        "AI_LOG_DIR": str(tmp_path / "logs"),
        "ANTIGRAVITY_BRAIN_DIR": str(tmp_path / "missing"),
    }
    result = subprocess.run(
        [sys.executable, "scripts/log_antigravity.py", "--auto", "--hook"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(result.stdout) == {"decision": "allow"}
