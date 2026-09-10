const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function findOpencodeBinary() {
  // 1. Try finding via system PATH
  try {
    const cmd = process.platform === 'win32' ? 'where opencode' : 'which opencode';
    const out = execSync(cmd, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }).trim();
    const lines = out.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    for (const line of lines) {
      if (fs.existsSync(line)) {
        let real = fs.realpathSync(line);
        if (fs.existsSync(real)) {
          if (process.platform === 'win32') {
            if (real.endsWith('.exe')) return real;
            const exeSibling = path.join(path.dirname(real), 'node_modules', 'opencode-ai', 'bin', 'opencode.exe');
            if (fs.existsSync(exeSibling)) return exeSibling;
          } else {
            const unixBin = path.join(path.dirname(real), 'node_modules', 'opencode-ai', 'bin', 'opencode');
            if (fs.existsSync(unixBin)) return unixBin;
            return real;
          }
        }
      }
    }
  } catch {}

  // 2. Standard paths per OS
  const home = process.env.HOME || process.env.USERPROFILE || '';
  const candidates = [
    path.join(process.env.APPDATA || '', 'npm', 'node_modules', 'opencode-ai', 'bin', 'opencode.exe'),
    '/usr/local/lib/node_modules/opencode-ai/bin/opencode',
    '/opt/homebrew/lib/node_modules/opencode-ai/bin/opencode',
    path.join(home, '.local', 'share', 'npm', 'node_modules', 'opencode-ai', 'bin', 'opencode'),
    path.join(home, '.bun', 'bin', 'opencode')
  ];

  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

const binPath = findOpencodeBinary();

if (!binPath) {
  console.log('[*] opencode binary not found in standard paths. Skipping binary patch.');
  process.exit(0);
}

console.log('[*] Found opencode binary at:', binPath);

const target = Buffer.from('$i=30000,xi=2147483647;');
const replacement = Buffer.from('$i=3000 ,xi=3000      ;');

if (target.length !== replacement.length) {
  throw new Error(`Length mismatch: target=${target.length}, replacement=${replacement.length}`);
}

try {
  const bakPath = binPath + '.bak';
  if (!fs.existsSync(bakPath)) {
    console.log('[*] Creating backup:', bakPath);
    fs.copyFileSync(binPath, bakPath);
  }

  const fd = fs.openSync(binPath, 'r+');
  const stat = fs.fstatSync(fd);
  const chunkSize = 16 * 1024 * 1024;
  const buf = Buffer.alloc(chunkSize);
  let offset = 0;
  let patched = false;

  while (offset < stat.size) {
    const read = fs.readSync(fd, buf, 0, Math.min(chunkSize, stat.size - offset), offset);
    const idx = buf.indexOf(target);
    if (idx !== -1 && idx < read) {
      const writeOffset = offset + idx;
      console.log(`[+] Found target sequence at offset ${writeOffset}. Patching retry timeout to 3s...`);
      fs.writeSync(fd, replacement, 0, replacement.length, writeOffset);
      patched = true;
      break;
    }
    const repIdx = buf.indexOf(replacement);
    if (repIdx !== -1 && repIdx < read) {
      console.log(`[✓] Already patched at offset ${offset + repIdx}.`);
      patched = true;
      break;
    }
    offset += read - target.length;
  }

  fs.closeSync(fd);

  if (patched) {
    console.log('[✓] opencode CLI binary successfully patched (3-second maximum retry backoff).');
  } else {
    console.log('[*] Target pattern not found or already optimized in this build.');
  }
} catch (err) {
  if (err.code === 'EBUSY' || err.code === 'ETXTBSY') {
    console.error('[!] opencode binary is currently locked by a running process.');
    console.error('    Please close OpenCode Desktop / CLI before running this patch.');
  } else {
    console.error('[-] Patch error:', err.message);
  }
}

// 2. Patch OpenCode Desktop IDE app.asar
function patchDesktopAsar() {
  const asarPaths = [
    path.join(process.env.LOCALAPPDATA || '', 'Programs', '@opencode-aidesktop', 'resources', 'app.asar'),
    'C:/Users/rey.echavez/AppData/Local/Programs/@opencode-aidesktop/resources/app.asar'
  ];

  let asarPath = null;
  for (const p of asarPaths) {
    if (fs.existsSync(p)) {
      asarPath = p;
      break;
    }
  }

  if (!asarPath) {
    return;
  }

  console.log('[*] Found OpenCode Desktop app.asar at:', asarPath);
  const targetAsar = Buffer.from('RETRY_MAX_DELAY_NO_HEADERS = 3e4, RETRY_MAX_DELAY = 2147483647, RETRY_MAX_RETRIES = 5,');
  const replacementAsar = Buffer.from('RETRY_MAX_DELAY_NO_HEADERS = 3e3, RETRY_MAX_DELAY = 3000      , RETRY_MAX_RETRIES = 2,');

  try {
    const bakPath = asarPath + '.bak';
    if (!fs.existsSync(bakPath)) {
      console.log('[*] Creating desktop backup:', bakPath);
      fs.copyFileSync(asarPath, bakPath);
    }

    const data = fs.readFileSync(asarPath);
    if (data.includes(replacementAsar)) {
      console.log('[✓] OpenCode Desktop app.asar is already patched (attempt #2 only, 3s countdown).');
      return;
    }

    const idx = data.indexOf(targetAsar);
    if (idx !== -1) {
      console.log(`[+] Found target sequence at offset ${idx} in app.asar. Patching to attempt #2 & 3s delay...`);
      const fd = fs.openSync(asarPath, 'r+');
      fs.writeSync(fd, replacementAsar, 0, replacementAsar.length, idx);
      fs.closeSync(fd);
      console.log('[✓] OpenCode Desktop app.asar successfully patched (attempt #2 only, 3s countdown).');
    } else {
      console.log('[*] Target sequence not found in app.asar.');
    }
  } catch (err) {
    if (err.code === 'EBUSY') {
      console.warn('[!] app.asar is locked by running OpenCode process.');
    } else {
      console.warn('[-] Error patching app.asar:', err.message);
    }
  }
}

patchDesktopAsar();
