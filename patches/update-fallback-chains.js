const fs = require('fs');

const defaultChain = [
  "openrouter/minimax/minimax-m3:free",
  "opencode/big-pickle",
  "openrouter/google/gemma-4-31b-it:free",
  "openrouter/qwen/qwen-2.5-72b-instruct:free",
  "opencode/minimax-m2.5-free",
  "openrouter/meta/llama-3.3-70b:free",
  "openrouter/deepseek/deepseek-chat"
];

const agents = {
  "*": {
    "fallbackModels": defaultChain
  },
  "architect": {
    "fallbackModels": [
      "openrouter/minimax/minimax-m3:free",
      "opencode/big-pickle",
      "openrouter/deepseek/deepseek-chat",
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "openrouter/meta/llama-3.3-70b:free",
      "opencode/mimo-v2.5-free"
    ]
  },
  "orchestrator": {
    "fallbackModels": [
      "openrouter/minimax/minimax-m3:free",
      "opencode/big-pickle",
      "openrouter/deepseek/deepseek-chat",
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/meta/llama-3.3-70b:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "opencode/minimax-m2.5-free"
    ]
  },
  "coder": {
    "fallbackModels": [
      "openrouter/deepseek/deepseek-chat",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/meta/llama-3.3-70b:free",
      "opencode/big-pickle"
    ]
  },
  "glm-coder": {
    "fallbackModels": [
      "openrouter/deepseek/deepseek-chat",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/meta/llama-3.3-70b:free",
      "opencode/big-pickle"
    ]
  },
  "critic": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "opencode/big-pickle",
      "opencode/minimax-m2.5-free",
      "openrouter/meta/llama-3.3-70b:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free"
    ]
  },
  "researcher": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "opencode/big-pickle",
      "opencode/minimax-m2.5-free",
      "openrouter/meta/llama-3.3-70b:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free"
    ]
  },
  "test_engineer": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "opencode/big-pickle",
      "openrouter/meta/llama-3.3-70b:free"
    ]
  },
  "reviewer": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/qwen/qwen-2.5-72b-instruct:free",
      "opencode/big-pickle",
      "openrouter/meta/llama-3.3-70b:free"
    ]
  },
  "explorer": {
    "fallbackModels": [
      "opencode/big-pickle",
      "opencode/minimax-m2.5-free",
      "openrouter/google/gemma-4-31b-it:free",
      "openrouter/meta/llama-3.3-70b:free"
    ]
  },
  "docs": {
    "fallbackModels": [
      "opencode/big-pickle",
      "opencode/minimax-m2.5-free",
      "openrouter/google/gemma-4-31b-it:free"
    ]
  },
  "sme": {
    "fallbackModels": [
      "openrouter/deepseek/deepseek-chat",
      "openrouter/google/gemma-4-31b-it:free",
      "opencode/big-pickle"
    ]
  },
  "designer": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "opencode/big-pickle",
      "openrouter/qwen/qwen-2.5-72b-instruct:free"
    ]
  },
  "spec_writer": {
    "fallbackModels": [
      "openrouter/google/gemma-4-31b-it:free",
      "opencode/big-pickle",
      "openrouter/qwen/qwen-2.5-72b-instruct:free"
    ]
  }
};

const fullConfig = {
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
  "agents": agents
};

const jsonStr = JSON.stringify(fullConfig, null, 2);

const dests = [
  'm:/.opencode/model-fallback.json',
  'C:/Users/rey.echavez/.config/opencode/model-fallback.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/model-fallback.json'
];

for (const d of dests) {
  fs.writeFileSync(d, jsonStr, 'utf8');
  console.log('Updated:', d);
}
