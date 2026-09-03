const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function rmrf(p) {
  if (!fs.existsSync(p)) { console.log('[~] Not found:', p); return; }
  try {
    fs.rmSync(p, { recursive: true, force: true });
    console.log('[+] Deleted:', p);
  } catch (e) {
    console.log('[!] Could not delete:', p, '-', e.message);
  }
}

function readJson(p) {
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; }
}

function writeJson(p, obj) {
  fs.writeFileSync(p, JSON.stringify(obj, null, 2), 'utf8');
  console.log('[+] Updated:', p);
}

// ── 1. LOCATIONS TO CLEAN ─────────────────────────────────────────────────────
const locations = [
  // Project-level (M: drive)
  { label: 'M:\\.opencode (project)', dir: 'm:/.opencode' },
  // Machine-global (~/.config/opencode)
  { label: '~/.config/opencode (global)', dir: 'C:/Users/rey.echavez/.config/opencode' },
  // User-local (~/.opencode) - this is where "opencode plugin list" wrote to
  { label: '~/.opencode (user-local)', dir: 'C:/Users/rey.echavez/.opencode' },
];

// ── 2. For each location: remove swarm from package.json + node_modules ───────
for (const loc of locations) {
  if (!fs.existsSync(loc.dir)) { console.log(`\n[~] Dir not found: ${loc.label}`); continue; }
  console.log(`\n[*] Cleaning: ${loc.label}`);

  // package.json — remove opencode-swarm dependency
  const pkgPath = path.join(loc.dir, 'package.json');
  const pkg = readJson(pkgPath);
  if (pkg) {
    let changed = false;
    for (const depKey of ['dependencies', 'devDependencies', 'optionalDependencies']) {
      if (pkg[depKey]) {
        for (const dep of Object.keys(pkg[depKey])) {
          if (dep.includes('swarm')) {
            delete pkg[depKey][dep];
            console.log('[+] Removed from package.json:', dep);
            changed = true;
          }
        }
      }
    }
    if (changed) writeJson(pkgPath, pkg);
    else console.log('[✓] No swarm deps in package.json');
  }

  // package-lock.json — remove swarm entries
  const lockPath = path.join(loc.dir, 'package-lock.json');
  const lock = readJson(lockPath);
  if (lock) {
    let changed = false;
    for (const section of ['packages', 'dependencies']) {
      if (lock[section]) {
        for (const k of Object.keys(lock[section])) {
          if (k.includes('swarm')) {
            delete lock[section][k];
            console.log('[+] Removed from package-lock.json:', k);
            changed = true;
          }
        }
      }
    }
    if (changed) writeJson(lockPath, lock);
    else console.log('[✓] No swarm entries in package-lock.json');
  }

  // node_modules — remove swarm directories
  const nmPath = path.join(loc.dir, 'node_modules');
  if (fs.existsSync(nmPath)) {
    const dirs = fs.readdirSync(nmPath, { withFileTypes: true });
    for (const d of dirs) {
      if (d.name.includes('swarm')) {
        rmrf(path.join(nmPath, d.name));
      }
      // Also check scoped packages
      if (d.isDirectory() && d.name.startsWith('@')) {
        const scopedDirs = fs.readdirSync(path.join(nmPath, d.name), { withFileTypes: true });
        for (const sd of scopedDirs) {
          if (sd.name.includes('swarm')) {
            rmrf(path.join(nmPath, d.name, sd.name));
          }
        }
      }
    }
  }

  // opencode.json — remove swarm from plugin array
  const ocJsonPath = path.join(loc.dir, 'opencode.json');
  const ocJson = readJson(ocJsonPath);
  if (ocJson) {
    if (Array.isArray(ocJson.plugin)) {
      const before = ocJson.plugin.length;
      ocJson.plugin = ocJson.plugin.filter(p => !p.includes('swarm'));
      if (ocJson.plugin.length !== before) {
        writeJson(ocJsonPath, ocJson);
        console.log('[+] Removed swarm from opencode.json plugin array');
      } else {
        console.log('[✓] No swarm in opencode.json plugin array');
      }
    }
  }

  // opencode.jsonc — remove swarm from plugin array (regex-based)
  const ocJsoncPath = path.join(loc.dir, 'opencode.jsonc');
  if (fs.existsSync(ocJsoncPath)) {
    let content = fs.readFileSync(ocJsoncPath, 'utf8');
    // Remove "opencode-swarm" entries from plugin array (various formats)
    const before = content;
    content = content
      .replace(/"opencode-swarm"\s*,?\s*/g, '')
      .replace(/,\s*"opencode-swarm"\s*/g, '')
      .replace(/\[\s*,/g, '[')
      .replace(/,\s*\]/g, ']');
    if (content !== before) {
      fs.writeFileSync(ocJsoncPath, content, 'utf8');
      console.log('[+] Removed swarm from opencode.jsonc plugin array');
    } else {
      console.log('[✓] No swarm in opencode.jsonc plugin array');
    }
  }
}

// ── 3. Also clean ~/.local/share/opencode (opencode data dir) ─────────────────
const dataDir = 'C:/Users/rey.echavez/.local/share/opencode';
if (fs.existsSync(dataDir)) {
  console.log('\n[*] Cleaning swarm from ~/.local/share/opencode...');
  const dataDirs = fs.readdirSync(dataDir, { withFileTypes: true });
  for (const d of dataDirs) {
    if (d.name.includes('swarm')) rmrf(path.join(dataDir, d.name));
  }
  console.log('[✓] Done');
}

// ── 4. Also clean opencode cache ──────────────────────────────────────────────
const cacheDir = 'C:/Users/rey.echavez/.cache/opencode/packages';
if (fs.existsSync(cacheDir)) {
  console.log('\n[*] Cleaning swarm from opencode cache...');
  const cachePkgs = fs.readdirSync(cacheDir, { withFileTypes: true });
  for (const p of cachePkgs) {
    if (p.name.includes('swarm')) rmrf(path.join(cacheDir, p.name));
  }
}

// ── 5. Summary ────────────────────────────────────────────────────────────────
console.log('\n[✓] Swarm removal complete.\n');
console.log('Remaining locations to verify manually:');
for (const loc of locations) {
  const nmPath = path.join(loc.dir, 'node_modules');
  if (!fs.existsSync(nmPath)) { console.log(`  ${loc.label}: node_modules not found`); continue; }
  const leftover = fs.readdirSync(nmPath).filter(n => n.includes('swarm'));
  if (leftover.length > 0) {
    console.log(`  [!] ${loc.label}: STILL HAS swarm:`, leftover);
  } else {
    console.log(`  [✓] ${loc.label}: clean`);
  }
}
