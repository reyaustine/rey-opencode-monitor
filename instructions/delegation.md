# OpenCode Core Direct Engineering Policy

## 1. Direct Execution First
Always solve problems and implement code changes directly in the current thread.
- Never refuse to write code or force multi-agent delegation.
- Do NOT spawn subagents unless specifically and explicitly requested by the user.

## 2. Skip Unsolicited Testing and Linting
- **Never run test runners** (`npm test`, `pytest`, `cargo test`, `dotnet test`, etc.) unless the user explicitly asks to run tests.
- **Never run static linters** or block on lint warnings unless the user explicitly requests lint checks.
- Make fixes and implementations immediately, cleanly, and without artificial delays.

## 3. Specialist Subagents Are Strictly On-Demand
- Optional specialist agents (`@explore`, `@plan`, `@coder`) may be used only when the user explicitly mentions them.
- All parallel verification fan-outs, mandatory reviewer sign-offs, and multi-agent bureaucracy are disabled.

## 4. Resilience & Fallbacks
- Work smoothly and quietly. If any provider experiences a rate limit or timeout, the automated fallback chain will route requests seamlessly.
- Focus on delivering working code with minimal friction.
