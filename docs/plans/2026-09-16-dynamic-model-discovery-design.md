# Dynamic Model Discovery & Tier Selection — Design Spec

> **Goal:** Replace hardcoded roster models with live-discovered models from each provider, with a free/mixed tier filter.

## Current State

- `rey-roster.py` has hardcoded `ROSTER_RULES` with static model names
- `rey-health.py` already fetches live models from OpenRouter, Kilo, Groq (patterns to reuse)
- `rey-setup.ps1` flows: Provider Selection → API Key Entry → Roster

## Proposed Flow (7 Steps)

```
1. Select Providers     (existing — rey-setup.ps1)
2. Model Tier Select    (NEW — rey-setup.ps1: Free Only / Mixed)
3. Fetch Live Models    (NEW — rey-models.py: calls provider APIs)
4. Show Model Counts    (NEW — rey-setup.ps1: display summary table)
5. Enter API Keys       (existing — rey-setup.ps1)
6. Generate Roster      (modified — rey-roster.py: uses live models)
7. Display Roster       (existing — rey-roster.ps1)
```

## New File: `scripts/rey-models.py`

Standalone Python script that:
1. Reads `byok-config.json` for enabled providers
2. Reads `model-tier.json` for free/mixed preference
3. Fetches live models from each enabled provider's API
4. Filters by tier (free-only strips paid, mixed keeps all)
5. Writes `live-models.json` with results
6. Prints summary JSON to stdout for PowerShell consumption

### Provider APIs

| Provider | Endpoint | Auth | Free Detection |
|----------|----------|------|----------------|
| OpenRouter | `GET https://openrouter.ai/api/v1/models` | None (public) | `:free` suffix or pricing==0 |
| Groq | `GET https://api.groq.com/openai/v1/models` | `Authorization: Bearer $GROQ_API_KEY` | All models free-tier |
| Gemini | Hardcoded list (no public API) | N/A | All models free-tier |
| Claude | Hardcoded list (no public API) | N/A | All models paid |
| ChatGPT | Hardcoded list (no public API) | N/A | All models paid |
| OpenCode | `GET http://localhost:1234/v1/models` (LAN) | None | All models free |
| Kilo | `GET https://api.kilo.ai/api/gateway/v1/models` | None | All models free |

### Output: `live-models.json`

```json
{
  "tier": "free",
  "generated_at": "2026-09-16T10:00:00",
  "providers": {
    "openrouter": {
      "ok": true,
      "models": [
        {"id": "deepseek/deepseek-chat:free", "name": "DeepSeek Chat", "context_length": 128000, "pricing": "free"}
      ],
      "total": 23,
      "free_count": 23,
      "paid_count": 0
    },
    "groq": { ... },
    ...
  },
  "summary": {
    "total_models": 45,
    "by_provider": {"openrouter": 23, "groq": 8, ...}
  }
}
```

## Modified File: `scripts/rey-roster.py`

- Remove hardcoded `ROSTER_RULES`
- Read `live-models.json` instead
- For each role, pick the best model from available live models using priority rules:
  - **coder**: prefer code-specialized models (deepseek-chat, codestral, gpt-4.1, gemini-flash)
  - **reviewer**: prefer reasoning models (claude-sonnet, o3, gemini-pro)
  - **planner**: prefer large-context models (gemini-pro, claude-opus, o3)
  - **researcher**: prefer fast/cheap models (gemini-flash, gpt-4.1-mini, llama-instant)
  - **debugger**: prefer reasoning models (deepseek-r1, o3, claude-sonnet)

## Modified File: `scripts/rey-setup.ps1`

### New Step 2: `Show-TierSelection`
- Two options: `[1] Free Only` / `[2] Mixed (Free + Paid)`
- Default: Free Only
- Saves to `model-tier.json`

### New Step 3: `Show-ModelDiscovery`
- Calls `python scripts/rey-models.py`
- Displays summary table:
  ```
  ┌──────────────┬───────┬──────┬──────┐
  │ PROVIDER     │ TOTAL │ FREE │ PAID │
  ├──────────────┼───────┼──────┼──────┤
  │ OpenRouter   │    23 │   23 │    0 │
  │ Groq         │     8 │    8 │    0 │
  │ Google Gemini│     3 │    3 │    0 │
  │ ...          │       │      │      │
  └──────────────┴───────┴──────┴──────┘
  Total: 45 models available
  ```
- Press Enter to continue

### Modified `Start-Setup` orchestration:
```
Show-ProviderSelection → Show-TierSelection → Show-ModelDiscovery → Show-KeyInput → roster → done
```

## New File: `model-tier.json`

```json
{
  "tier": "free",
  "updated_at": "2026-09-16T10:00:00"
}
```

## Error Handling

- If a provider API fails: skip it, show "FAILED" in table, continue with others
- If no providers return models: show warning, suggest switching to Mixed tier
- If `rey-models.py` not found: fall back to hardcoded roster (graceful degradation)

## Testing

1. Delete `byok-config.json` and `.setup-complete`
2. Run `pwsh scripts/rey-monitor.ps1` → setup wizard launches
3. Select providers → choose Free Only → see model counts → enter keys → roster displays
4. Re-run with Mixed tier → see paid models included
5. Test with no API keys → public endpoints still work (OpenRouter, Kilo)
