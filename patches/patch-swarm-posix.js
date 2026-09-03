const fs = require('fs');
const path = require('path');

const cacheDir = path.join(process.env.USERPROFILE || '', '.cache', 'opencode', 'packages');

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
      // Check deeper in case of @latest
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

const unpatchedPattern = 'if(normalizedTool==="bash")shellType="posix";';
const unpatchedDetect = 'let detect=shellType==="posix"?detectPosixWrites:detectWindowsWrites;';

const patchedPattern = 'if(normalizedTool==="bash"&&process.platform!=="win32"&&shellType!=="powershell"&&shellType!=="cmd")shellType="posix";';
const patchedDetect = 'let detect=(c)=>(shellType==="powershell"||shellType==="cmd")?detectWindowsWrites(c,shellType):detectPosixWrites(c);';

for (const file of files) {
  console.log('[*] Checking:', file);
  let content = fs.readFileSync(file, 'utf8');
  if (content.includes(patchedPattern)) {
    console.log('[✓] Already patched for Windows PowerShell:', file);
    continue;
  }
  if (content.includes(unpatchedPattern)) {
    content = content.replace(unpatchedPattern, patchedPattern);
    if (content.includes(unpatchedDetect)) {
      content = content.replace(unpatchedDetect, patchedDetect);
    }
    fs.writeFileSync(file + '.bak', fs.readFileSync(file));
    fs.writeFileSync(file, content, 'utf8');
    console.log('[+] Successfully applied Windows PowerShell fix to:', file);
  } else {
    console.log('[?] File syntax does not match known patterns. Skipping.');
  }
}
