const fs = require('fs');

const apiKey = 'AQ.Ab8RN6K3sT729ZBROZ_prMPnCacOJg1u-7ZGHRGAlbPeDtLjAg';

// 1. Update opencode.jsonc
const opencodeConfigs = [
  'm:/.opencode/opencode.jsonc',
  'C:/Users/rey.echavez/.config/opencode/opencode.jsonc',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/opencode.jsonc'
];

for (const p of opencodeConfigs) {
  if (!fs.existsSync(p)) continue;
  let raw = fs.readFileSync(p, 'utf8');
  let cfg;
  try {
    cfg = JSON.parse(raw);
  } catch (e) {
    // If jsonc has comments, strip simple ones
    const clean = raw.replace(/\/\/.*$/gm, '');
    cfg = JSON.parse(clean);
  }

  if (!cfg.provider) cfg.provider = {};
  cfg.provider.google = {
    options: {
      apiKey: apiKey
    }
  };

  if (cfg.agent) {
    if (cfg.agent.orchestrator) {
      cfg.agent.orchestrator.model = "google/gemini-2.5-pro";
    }
    if (cfg.agent.architect) {
      cfg.agent.architect.model = "google/gemini-2.5-pro";
    }
  }

  fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf8');
  console.log('[+] Updated opencode.jsonc:', p);
}

// 2. Update opencode-swarm.json
const swarmConfigs = [
  'm:/.opencode/opencode-swarm.json',
  'C:/Users/rey.echavez/.config/opencode/opencode-swarm.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/opencode-swarm.json'
];

for (const p of swarmConfigs) {
  if (!fs.existsSync(p)) continue;
  const cfg = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (cfg.agents) {
    // Pro reasoning models
    if (cfg.agents.architect) cfg.agents.architect.model = "google/gemini-2.5-pro";
    if (cfg.agents.reviewer) cfg.agents.reviewer.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic) cfg.agents.critic.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_sounding_board) cfg.agents.critic_sounding_board.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_architecture_supervisor) cfg.agents.critic_architecture_supervisor.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_finding_validator) cfg.agents.critic_finding_validator.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_drift_verifier) cfg.agents.critic_drift_verifier.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_hallucination_verifier) cfg.agents.critic_hallucination_verifier.model = "google/gemini-2.5-pro";
    if (cfg.agents.critic_oversight) cfg.agents.critic_oversight.model = "google/gemini-2.5-pro";

    // Fast models
    if (cfg.agents.explorer) cfg.agents.explorer.model = "google/gemini-2.5-flash";
    if (cfg.agents.docs) cfg.agents.docs.model = "google/gemini-2.5-flash";
    if (cfg.agents.docs_design) cfg.agents.docs_design.model = "google/gemini-2.5-flash";
    if (cfg.agents.curator_init) cfg.agents.curator_init.model = "google/gemini-2.5-flash";
    if (cfg.agents.curator_phase) cfg.agents.curator_phase.model = "google/gemini-2.5-flash";
    if (cfg.agents.curator_postmortem) cfg.agents.curator_postmortem.model = "google/gemini-2.5-flash";
    if (cfg.agents.curator_consolidation) cfg.agents.curator_consolidation.model = "google/gemini-2.5-flash";
    if (cfg.agents.researcher) cfg.agents.researcher.model = "google/gemini-2.5-flash";
  }

  fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf8');
  console.log('[+] Updated opencode-swarm.json:', p);
}

// 3. Update model-fallback.json
const fallbackConfigs = [
  'm:/.opencode/model-fallback.json',
  'C:/Users/rey.echavez/.config/opencode/model-fallback.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/model-fallback.json'
];

const geminiFallbackPro = [
  "google/gemini-2.5-pro",
  "google/gemini-2.5-flash",
  "openrouter/minimax/minimax-m3:free",
  "opencode/big-pickle",
  "openrouter/deepseek/deepseek-chat",
  "openrouter/google/gemma-4-31b-it:free"
];

const geminiFallbackFlash = [
  "google/gemini-2.5-flash",
  "google/gemini-2.5-pro",
  "opencode/big-pickle",
  "openrouter/minimax/minimax-m3:free",
  "openrouter/google/gemma-4-31b-it:free"
];

for (const p of fallbackConfigs) {
  if (!fs.existsSync(p)) continue;
  const cfg = JSON.parse(fs.readFileSync(p, 'utf8'));

  cfg.defaults.fallbackOn = [
    "rate_limit",
    "quota_exceeded",
    "5xx",
    "timeout",
    "overloaded"
  ];

  if (cfg.agents) {
    if (cfg.agents["*"]) cfg.agents["*"].fallbackModels = geminiFallbackPro;
    if (cfg.agents.architect) cfg.agents.architect.fallbackModels = geminiFallbackPro;
    if (cfg.agents.orchestrator) cfg.agents.orchestrator.fallbackModels = geminiFallbackPro;
    if (cfg.agents.reviewer) cfg.agents.reviewer.fallbackModels = geminiFallbackPro;
    if (cfg.agents.critic) cfg.agents.critic.fallbackModels = geminiFallbackPro;
    if (cfg.agents.coder) cfg.agents.coder.fallbackModels = [
      "google/gemini-2.5-pro",
      "google/gemini-2.5-flash",
      "openrouter/deepseek/deepseek-chat",
      "opencode/big-pickle"
    ];

    if (cfg.agents.explorer) cfg.agents.explorer.fallbackModels = geminiFallbackFlash;
    if (cfg.agents.docs) cfg.agents.docs.fallbackModels = geminiFallbackFlash;
    if (cfg.agents.researcher) cfg.agents.researcher.fallbackModels = geminiFallbackFlash;
  }

  fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf8');
  console.log('[+] Updated model-fallback.json:', p);
}
