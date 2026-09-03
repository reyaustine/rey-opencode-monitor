const fs = require('fs');

const targets = [
  'm:/.opencode/opencode-swarm.json',
  'C:/Users/rey.echavez/.config/opencode/opencode-swarm.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/opencode-swarm.json'
];

for (const t of targets) {
  if (!fs.existsSync(t)) continue;
  const cfg = JSON.parse(fs.readFileSync(t, 'utf8'));
  if (cfg.agents) {
    for (const [name, agent] of Object.entries(cfg.agents)) {
      if (agent.fallback_models) {
        delete agent.fallback_models;
      }
    }
  }
  fs.writeFileSync(t, JSON.stringify(cfg, null, 2), 'utf8');
  console.log('Cleaned fallback_models from:', t);
}
