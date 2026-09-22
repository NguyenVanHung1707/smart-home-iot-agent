#!/usr/bin/env bash
# POSIX / Git Bash entry point; installation logic is shared with Windows.
repo_root="$(git rev-parse --show-toplevel)" || exit 1
bash "$repo_root/scripts/_pyrun.sh" "$repo_root/scripts/setup_hooks.py"
