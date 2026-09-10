# Swarm Delegation & Load-Balanced Verification Policy

## 1. Overview: The Swarm Load Balancer
The Lead Orchestrator acts as an intelligent **Task Load Balancer**. It decomposes complex tasks and fans them out across specialized agents rather than writing code and verifying sequentially.

By distributing work across agents with distinct underlying model architectures and providers, the swarm achieves maximum parallel throughput while preventing rate-limit bottlenecks on any single upstream provider.

---

## 2. Specialized Agent Fleet & Provider Distribution

| Agent | Role | Model | Provider Architecture |
| :--- | :--- | :--- | :--- |
| **`@orchestrator`** | Swarm Load Balancer & Dispatcher | `openrouter/openrouter/free` | Meta-Router |
| **`@coder`** | Core Algorithmic Code & Refactoring | `openrouter/cohere/north-mini-code:free` | Cohere |
| **`@explorer`** | Rapid Surgical Edits & CSS Patches | `openrouter/inclusionai/ling-3.0-flash-fin:free` | InclusionAI |
| **`@linter`** | Syntax, Bracket, Import & Lint Checker | `openrouter/poolside/laguna-xs-2.1:free` | Poolside |
| **`@qa`** | Test Runner & Acceptance QA | `openrouter/nvidia/nemotron-3.5-lightning:free` | NVIDIA |
| **`@verifier`** | Logic Trace & Functional Gap Auditor | `openrouter/google/gemma-4-31b-it:free` | Google Gemma |
| **`@reviewer`** | Holistic Code Reviewer & Sign-off | `openrouter/nvidia/nemotron-3-super-120b-a12b:free` | NVIDIA |
| **`@architect`** | System & Multi-File Architecture | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | NVIDIA |
| **`@critic`** | Stress-testing & Flaw Discovery | `openrouter/liquid/lfm-2.5-2.6b:free` | Liquid |
| **`@docs`** | Documentation, Specs & Changelogs | `openrouter/nex-agi/nex-n2.5-pro:free` | Nex-AGI |
| **`@designer`** | UI/UX Layouts & Component Design | `openrouter/thinkingmachines/inkling:free` | ThinkingMachines |

---

## 3. The 3-Phase Swarm Pipeline

Whenever non-trivial code changes are made, the swarm executes through a 3-phase load-balanced pipeline:

```text
               ┌───────────────────────┐
               │    @orchestrator      │
               │ (Task Decomposition)  │
               └──────────┬────────────┘
                          │
            [Phase 1: Implementation]
                          ▼
               ┌───────────────────────┐
               │  @coder / @explorer   │
               │ (Write Code Changes)  │
               └──────────┬────────────┘
                          │
       [Phase 2: Parallel Load-Balanced Verification]
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │   @linter   │ │     @qa     │ │  @verifier  │
   │   (Syntax & │ │ (Test Suite │ │(Logic Gaps &│
   │    Types)   │ │  Execution) │ │ Regressions)│
   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
          └───────────────┼───────────────┘
                          │
               [Phase 3: Final Sign-off]
                          ▼
               ┌───────────────────────┐
               │  @reviewer / Lead PM  │
               │  (Synthesize & Merge) │
               └───────────────────────┘
```

### Phase 1: Implementation
- Delegate to `@coder` for substantive logic, algorithms, and backend functions.
- Delegate to `@explorer` for fast single-file edits, CSS tweaks, and config updates.

### Phase 2: Parallel Load-Balanced Verification (Simultaneous Fan-Out)
Immediately following file modifications, the Orchestrator fans out **three simultaneous subagents**:
1. **`@linter` (Syntax & Static Analysis)**:
   - Scans modified files for syntax errors, missing brackets, broken imports, type violations, and lint rules.
   - Reports exact file and line numbers for any issue found.
2. **`@qa` (Quality Assurance & Test Suite Runner)**:
   - Executes test runners (`npm test`, `pytest`, `cargo test`, `dotnet test`, etc.).
   - Verifies that fresh changes do not break existing test cases.
   - Tests edge cases and validates against user requirements.
3. **`@verifier` (Logic & Functional Gap Auditor)**:
   - Traces diffs for subtle logical flaws, unhandled error paths, off-by-one errors, and race conditions.
   - Identifies functional gaps between the user prompt and the resulting code.

### Phase 3: Final Sign-Off & Synthesis
- `@reviewer` reviews the combined reports from `@linter`, `@qa`, and `@verifier`.
- Any detected syntax or logic gaps are returned to `@coder` for remediation before completion.
- Synthesize all results into a concise, unified response for the user.

---

## 4. Subagent Task Title Tagging Rules (For R.E.Y. Monitor)

Every subagent session appears live in the **R.E.Y. Monitor** SUB-AGENTS table and drives the ASCII Robot Companion's facial animations. All subagent tasks **must be prefixed with a clear role tag**:

* **`[CODE] <task>`** — Activates `@coder` and triggers the robot's `[CODING]` expression.
* **`[LINT] <task>`** — Activates `@linter` and triggers the robot's `[DEBUG]` expression.
* **`[QA] <task>`** or **`[TEST] <task>`** — Activates `@qa` and triggers the robot's `[TESTING]` expression.
* **`[VERIFY] <task>`** — Activates `@verifier` and triggers the robot's `[ANALYZE]` expression.
* **`[REVIEW] <task>`** — Activates `@reviewer` and triggers the robot's `[ANALYZE]` expression.

Example subagent tasks:
- `[CODE] Implement user authentication middleware`
- `[LINT] Check syntax and typescript types in auth.ts`
- `[QA] Run auth test suite and check token expiration`
- `[VERIFY] Audit auth edge cases and missing null checks`

---

## 5. Swarm Portability & Free-Fleet Invariants

1. **Zero-Cost Free Fleet Only**: Only allowlisted free models may be selected. Never switch to paid or non-allowlisted models.
2. **Never Serialize Independent Checks**: `@linter`, `@qa`, and `@verifier` must always be launched concurrently.
3. **Graceful Failover**: If a model hits a temporary rate limit or timeout, the automated tiered fallback chain in `model-fallback.json` will instantly switch to the next fallback model.
4. **Regular Health Check**: Every 8–10 user prompts, run the free-model health check to confirm all providers and allowlisted models resolve with zero cost.
