const fs = require('fs');
const path = require('path');

const home = process.env.HOME || process.env.USERPROFILE || '';
const cacheDir = path.join(home, '.cache', 'opencode', 'packages');

function findFallbackIndexFiles(dir) {
  const results = [];
  if (!fs.existsSync(dir)) return results;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.includes('model-fallback')) {
        const candidate = path.join(fullPath, 'node_modules', '@smart-coders-hq', 'opencode-model-fallback', 'dist', 'index.js');
        if (fs.existsSync(candidate)) results.push(candidate);
      }
      results.push(...findFallbackIndexFiles(fullPath));
    }
  }
  return [...new Set(results)];
}

const files = findFallbackIndexFiles(cacheDir);

for (const file of files) {
  let content = fs.readFileSync(file, 'utf8');
  let modified = false;

  const target = 'var OVERLOADED_PATTERNS = [';
  const repl = 'var OVERLOADED_PATTERNS = ["max_num_tokens", "prompt length", "context length", "context_length_exceeded", "maximum context", ';

  if (content.includes(target) && !content.includes('"max_num_tokens"')) {
    content = content.replace(target, repl);
    modified = true;
    console.log('[+] Added context length & max_num_tokens triggers to:', file);
  }

  if (modified) {
    fs.writeFileSync(file, content, 'utf8');
  }
}
