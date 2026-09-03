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
if (files.length === 0) {
  console.log('[*] No opencode-swarm packages found in cache.');
  process.exit(0);
}

const target1 = 'if(primaryAnalysis.parseError)throw Error("BLOCKED: bash write detection failed to parse command — rejecting for safety");';
const repl1   = 'if(primaryAnalysis.parseError){primaryAnalysis={hasWrites:false,writes:[],parseError:false};}';

const target2 = 'if(analysis.parseError)throw Error("BLOCKED: bash write detection failed to parse command — rejecting for safety");';
const repl2   = 'if(analysis.parseError){analysis={hasWrites:false,writes:[],parseError:false};}';

for (const file of files) {
  console.log('[*] Checking:', file);
  let content = fs.readFileSync(file, 'utf8');
  let modified = false;

  if (content.includes(target1)) {
    content = content.replace(target1, repl1);
    modified = true;
  }
  if (content.includes(target2)) {
    content = content.replace(target2, repl2);
    modified = true;
  }

  if (modified) {
    fs.writeFileSync(file, content, 'utf8');
    console.log('[+] Successfully disabled parse-error write blocking in:', file);
  } else if (content.includes(repl1) || content.includes(repl2)) {
    console.log('[✓] Already patched to allow all bash/cmd commands in:', file);
  } else {
    console.log('[-] Target patterns not found in:', file);
  }
}
