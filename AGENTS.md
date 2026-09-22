# AI usage logging

AI-usage logs are collected automatically by the configured hooks and submitted
by the Git pre-push hook. Do not run `scripts/submit_log.py` manually.

Codex prompt logging is handled by surface hooks when available. Do not run
`scripts/log_manual.py` from Codex; it is only a fallback for web tools without
lifecycle hooks.

Do not include secrets in prompts. The pre-push hook submits `.ai-log/session.jsonl`
on the next `git push`.

# Vietnamese-first orchestration

- Treat Vietnamese as the source language for intent. Resolve omitted subjects,
  regional wording, politeness particles, negation, questions, hypotheticals,
  quotations, and time expressions before deciding that text is an instruction.
- For change or build requests, the main agent owns intent analysis, constraints,
  planning, safety decisions, and final review. Delegate the bounded implementation
  brief to the `worker` subagent, then inspect its diff and run relevant checks.
- The `worker` executes only the approved brief. It must not broaden scope, guess
  through material ambiguity, weaken safety rules, or report success without tests.
- Answer simple questions and perform small read-only checks in the main thread;
  do not spawn a worker when delegation would add no useful separation.
- If Vietnamese wording has multiple materially different interpretations, ask
  one concise clarification question instead of silently choosing an action.
