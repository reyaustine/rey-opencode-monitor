const fs = require('fs');
const path = require('path');

const home = process.env.HOME || process.env.USERPROFILE || '';
const cacheDir = path.join(home, '.cache', 'opencode', 'packages');

function findSwarmIndexFiles(dir) {
  const results = [];
  if (!fs.existsSync(dir)) return results;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('opencode-swarm')) {
        const candidate = path.join(fullPath, 'node_modules', 'opencode-swarm', 'dist', 'index.js');
        if (fs.existsSync(candidate)) results.push(candidate);
      }
      results.push(...findSwarmIndexFiles(fullPath));
    }
  }
  return [...new Set(results)];
}

const files = findSwarmIndexFiles(cacheDir);

for (const file of files) {
  let content = fs.readFileSync(file, 'utf8');
  let modified = false;

  // 1. Bypass ensureSwarmGitExcluded subprocess calls on boot (saves 3 seconds)
  const targetGitExclude = 'async function ensureSwarmGitExcluded(directory,options={}){if(_swarmGitExcludedChecked)return;';
  const replGitExclude   = 'async function ensureSwarmGitExcluded(directory,options={}){return;if(_swarmGitExcludedChecked)return;';
  if (content.includes(targetGitExclude)) {
    content = content.replace(targetGitExclude, replGitExclude);
    modified = true;
    console.log('[+] Bypassed blocking git-hygiene check on boot in:', file);
  }

  if (modified) {
    fs.writeFileSync(file, content, 'utf8');
  }
}
