const fs = require('fs');

const opencodeConfig = {
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "@smart-coders-hq/opencode-model-fallback"
  ],
  "default_agent": "orchestrator",
  "provider": {
    "google": {
      "options": {
        "apiKey": "AQ.Ab8RN6K3sT729ZBROZ_prMPnCacOJg1u-7ZGHRGAlbPeDtLjAg"
      }
    },
    "openrouter": {
      "models": {
        "minimax/minimax-m3:free": {
          "settings": {
            "reasoningEffort": "medium"
          }
        },
        "deepseek/deepseek-chat": {
          "settings": {
            "reasoningEffort": "medium"
          }
        }
      }
    }
  },
  "agent": {
    "orchestrator": {
      "mode": "all",
      "model": "google/gemini-2.5-pro",
      "system": "You are the Lead Project Manager. You have a massive 1M context window. Delegate specific coding or file-editing tasks sequentially (one at a time) to your subagents (@glm-coder, @inkling-explorer, @m3-architect). When the user asks for direct actions, you may also execute them directly."
    },
    "glm-coder": {
      "mode": "all",
      "model": "google/gemini-2.5-pro",
      "description": "Specialist for complex algorithmic code generation and deep refactoring. Call this for heavy coding.",
      "system": "You are a senior developer. Write clean, exact code."
    },
    "m3-architect": {
      "mode": "all",
      "model": "google/gemini-2.5-pro",
      "description": "Heavyweight agent for parsing massive logs, architectural design, and deep repository understanding."
    },
    "inkling-explorer": {
      "mode": "all",
      "model": "google/gemini-2.5-flash",
      "description": "Fast explorer for quick patches, CSS tweaks, UI updates, and surgical file edits."
    },
    "reviewer": {
      "mode": "all",
      "model": "google/gemini-2.5-pro",
      "description": "Thorough code reviewer and QA verifier. Validates logic, catches regressions, and checks edge cases."
    },
    "critic": {
      "mode": "all",
      "model": "google/gemini-2.5-pro",
      "description": "Critical analysis agent for evaluating architecture decisions, finding edge-case flaws, and reviewing plans."
    }
  }
};

const modelFallbackConfig = {
  "enabled": true,
  "defaults": {
    "fallbackOn": [
      "rate_limit",
      "quota_exceeded",
      "5xx",
      "timeout",
      "overloaded"
    ],
    "cooldownMs": 60000,
    "retryOriginalAfterMs": 180000,
    "maxFallbackDepth": 6
  },
  "agents": {
    "*": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "openrouter/minimax/minimax-m3:free",
        "opencode/big-pickle",
        "openrouter/deepseek/deepseek-chat"
      ]
    },
    "orchestrator": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "openrouter/minimax/minimax-m3:free",
        "openrouter/openai/gpt-oss-120b:free",
        "opencode/big-pickle"
      ]
    },
    "glm-coder": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "openrouter/deepseek/deepseek-chat",
        "opencode/big-pickle"
      ]
    },
    "m3-architect": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "openrouter/minimax/minimax-m3:free",
        "google/gemini-2.5-flash",
        "opencode/big-pickle"
      ]
    },
    "inkling-explorer": {
      "fallbackModels": [
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro",
        "openrouter/minimax/minimax-m3:free",
        "opencode/big-pickle"
      ]
    },
    "reviewer": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "openrouter/minimax/minimax-m3:free",
        "opencode/big-pickle"
      ]
    },
    "critic": {
      "fallbackModels": [
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash",
        "openrouter/minimax/minimax-m3:free",
        "opencode/big-pickle"
      ]
    }
  }
};

const opencodePaths = [
  'm:/.opencode/opencode.jsonc',
  'C:/Users/rey.echavez/.config/opencode/opencode.jsonc',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/opencode.jsonc'
];

for (const p of opencodePaths) {
  fs.writeFileSync(p, JSON.stringify(opencodeConfig, null, 2), 'utf8');
  console.log('[+] Written clean opencode.jsonc:', p);
}

const fallbackPaths = [
  'm:/.opencode/model-fallback.json',
  'C:/Users/rey.echavez/.config/opencode/model-fallback.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/model-fallback.json'
];

for (const p of fallbackPaths) {
  fs.writeFileSync(p, JSON.stringify(modelFallbackConfig, null, 2), 'utf8');
  console.log('[+] Written clean model-fallback.json:', p);
}
