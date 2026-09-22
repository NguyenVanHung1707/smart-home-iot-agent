---
description: "Manual AI log fallback for web tools without lifecycle hooks."
---

# Manual AI log (web tools only)

Claude Code, Cursor, Codex, Antigravity IDE/CLI, and GitHub Copilot log
automatically. Use this workflow only for web tools such as ChatGPT, Gemini Web,
Claude.ai, or Perplexity.

Linux, macOS, or Git Bash:

```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "Summarize API design"
```

Windows PowerShell or cmd:

```cmd
scripts\_pyrun.cmd scripts\log_manual.py --tool chatgpt --prompt "Summarize API design"
```

The entry stays in `.ai-log/session.jsonl` until Git pre-push submits it.
