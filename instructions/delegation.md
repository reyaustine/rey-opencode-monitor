# Auto-delegation policy (free-only fleet)

- Do straightforward work directly with the session's free model.
- When context is large, or when a task splits into independent parts, fan out
  to parallel subagents (one narrow task each) and run them SIMULTANEOUSLY.
  Never serialize independent work.
- Subagents use free allowlisted models only
  (`kilo/kilo-auto/free` or the allowlisted `opencode/*-free` models).
  Then synthesize their results into one answer.
- Keep subagent scopes tight with short, descriptive task titles: each subagent
  session appears as its own titled row in the JARVIS monitor AGENTS pane.
- Never select paid, retired, or non-allowlisted models. If a task genuinely
  needs one, stop and say so instead of switching silently.
- Every 8-10 user prompts, run the lightweight free-model health check
  (providers, allowlisted models, default-model smoke test, zero cost).
