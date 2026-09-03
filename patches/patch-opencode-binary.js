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
    console.log('[✓] opencode binary successfully patched (3-second maximum retry backoff).');
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
