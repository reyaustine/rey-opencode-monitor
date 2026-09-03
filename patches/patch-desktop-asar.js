const fs = require('fs');
const path = require('path');

function findAppAsar() {
  const candidates = [
    'C:/Users/rey.echavez/AppData/Local/Programs/@opencode-aidesktop/resources/app.asar',
    path.join(process.env.LOCALAPPDATA || '', 'Programs/@opencode-aidesktop/resources/app.asar'),
    '/Applications/OpenCode.app/Contents/Resources/app.asar',
    path.join(process.env.HOME || '', 'Applications/OpenCode.app/Contents/Resources/app.asar')
  ];

  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

const asarPath = findAppAsar();
if (!asarPath) {
  console.log('[info] OpenCode Desktop app.asar not found (headless or CLI-only mode). Skipping.');
  process.exit(0);
}

console.log('[*] Found OpenCode Desktop app.asar at:', asarPath);

// Target string:
const target = 'RETRY_MAX_DELAY_NO_HEADERS = 3e4, RETRY_MAX_DELAY = 2147483647';
const replacement = 'RETRY_MAX_DELAY_NO_HEADERS = 3000, RETRY_MAX_DELAY = 3000     ';

const fd = fs.openSync(asarPath, 'r+');
const stat = fs.fstatSync(fd);
const chunkSize = 16 * 1024 * 1024;
const buf = Buffer.alloc(chunkSize);
const targetBuf = Buffer.from(target, 'utf8');
const replBuf = Buffer.from(replacement, 'utf8');

let offset = 0;
let patched = false;

while (offset < stat.size) {
  const read = fs.readSync(fd, buf, 0, Math.min(chunkSize, stat.size - offset), offset);
  const idx = buf.indexOf(targetBuf);
  if (idx !== -1 && idx < read) {
    const writeOffset = offset + idx;
    fs.writeSync(fd, replBuf, 0, replBuf.length, writeOffset);
    console.log('[OK] Successfully patched app.asar retry clamp at offset:', writeOffset);
    patched = true;
    break;
  }
  if (buf.indexOf(replBuf) !== -1) {
    console.log('[OK] app.asar is already patched (3s clamp active).');
    patched = true;
    break;
  }
  offset += read - 100;
}

fs.closeSync(fd);

if (!patched) {
  console.log('[-] Target sequence not found in app.asar.');
}
