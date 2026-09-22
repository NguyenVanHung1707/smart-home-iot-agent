# Windows entry point; installation logic is shared with POSIX.
$RepoRoot = git rev-parse --show-toplevel
& "$RepoRoot\scripts\_pyrun.cmd" "$RepoRoot\scripts\setup_hooks.py"
