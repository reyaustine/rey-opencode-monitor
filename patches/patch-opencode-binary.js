const fs = require('fs');
const path = require('path');

// Locate opencode.exe
const defaultPaths = [
  path.join(process.env.APPDATA || '', 'npm', 'node_modules', 'opencode-ai', 'bin', 'opencode.exe'),
  'C:/Users/rey.echavez/AppData/Roaming/npm/node_modules/opencode-ai/bin/opencode.exe'
];

let binPath = null;
for (const p of defaultPaths) {
  if (fs.existsSync(p)) {
    binPath = p;
    break;
  }
}

if (!binPath) {
  console.error('[-] opencode.exe not found in expected default paths.');
  process.exit(1);
}

console.log('[*] Found opencode.exe at:', binPath);

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
    console.log('[✓] opencode.exe is successfully patched (3-second maximum retry backoff).');
  } else {
    console.warn('[!] Target sequence not found. Binary may be a different version or format.');
  }
} catch (err) {
  if (err.code === 'EBUSY') {
    console.error('[!] opencode.exe is currently locked by a running process.');
    console.error('    Please close OpenCode Desktop / CLI before running this patch.');
  } else {
    console.error('[-] Patch error:', err.message);
  }
  process.exit(1);
}
