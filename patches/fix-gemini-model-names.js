const fs = require('fs');

// ── Paths ─────────────────────────────────────────────────────────────────────
const opencodePaths = [
  'C:/Users/rey.echavez/.config/opencode/opencode.jsonc',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/opencode.jsonc',
];
const fallbackPaths = [
  'C:/Users/rey.echavez/.config/opencode/model-fallback.json',
  'C:/Users/rey.echavez/opencode-swarm-pack/configs/model-fallback.json',
];
const projectDelete = [
  'm:/.opencode/opencode.jsonc',
  'm:/.opencode/opencode.json',
];

// ── Fix JSONC file (strip comments first, parse, then replace and rewrite) ───
function fixJsonc(filePath) {
  let raw = fs.readFileSync(filePath, 'utf8');
  // Simple regex-based replacement directly on the raw text (no JSON parse needed)
  const fixed = raw.replace(/google\/gemini-2\.5-pro(?!-preview)/g, 'google/gemini-2.5-pro-preview');
  fs.writeFileSync(filePath, fixed, 'utf8');
  const count = (raw.match(/google\/gemini-2\.5-pro(?!-preview)/g) || []).length;
  console.log(`[+] ${filePath} — replaced ${count} instance(s)`);
}

// ── Fix JSON file ─────────────────────────────────────────────────────────────
function fixJson(filePath) {
  let raw = fs.readFileSync(filePath, 'utf8');
  const fixed = raw.replace(/google\/gemini-2\.5-pro(?!-preview)/g, 'google/gemini-2.5-pro-preview');
  fs.writeFileSync(filePath, fixed, 'utf8');
  const count = (raw.match(/google\/gemini-2\.5-pro(?!-preview)/g) || []).length;
  console.log(`[+] ${filePath} — replaced ${count} instance(s)`);
}

console.log('\n[*] Updating opencode.jsonc files...');
for (const p of opencodePaths) fixJsonc(p);

console.log('\n[*] Updating model-fallback.json files...');
for (const p of fallbackPaths) fixJson(p);

console.log('\n[*] Deleting project-level opencode config...');
for (const p of projectDelete) {
  if (fs.existsSync(p)) {
    fs.unlinkSync(p);
    console.log('[+] Deleted:', p);
  } else {
    console.log('[~] Not found (skipped):', p);
  }
}

// ── Verify: print all model values in the global opencode.jsonc ───────────────
console.log('\n[*] Verifying final model roster...');
const raw = fs.readFileSync(opencodePaths[0], 'utf8');
const modelMatches = [...raw.matchAll(/"model"\s*:\s*"([^"]+)"/g)];
const old = modelMatches.filter(m => m[1] === 'google/gemini-2.5-pro');

for (const m of modelMatches) {
  console.log(`    → ${m[1]}`);
}

if (old.length > 0) {
  console.log(`\n[!] WARNING: ${old.length} deprecated "google/gemini-2.5-pro" still remain!`);
} else {
  console.log('\n[✓] All agent models updated. No deprecated gemini-2.5-pro found!');
}
