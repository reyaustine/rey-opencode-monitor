const fs = require('fs');

const asarPath = 'C:/Users/rey.echavez/AppData/Local/Programs/@opencode-aidesktop/resources/app.asar';
if (!fs.existsSync(asarPath)) {
  console.log('app.asar not found');
  process.exit(1);
}

const originalBuf = fs.readFileSync(asarPath);
const originalLen = originalBuf.length;

// Target code block in convertJSONSchemaToOpenAPISchema2
const targetStr = `  if (constValue !== void 0) {
    result42.enum = [constValue];
  }
  if (type) {
    if (Array.isArray(type)) {
      const hasNull = type.includes("null");
      const nonNullTypes = type.filter((t3) => t3 !== "null");
      if (nonNullTypes.length === 0) {
        result42.type = "null";
      } else {
        result42.anyOf = nonNullTypes.map((t3) => ({ type: t3 }));
        if (hasNull) {
          result42.nullable = true;
        }
      }
    } else {
      result42.type = type;
    }
  }
  if (enumValues !== void 0) {
    result42.enum = enumValues;
  }`;

const targetLen = Buffer.byteLength(targetStr, 'utf8');

// Replacement logic: convert constValue and enumValues items to String to comply with Gemini API
const minified = `  if(constValue!==void 0){result42.enum=[String(constValue)];}if(type){if(Array.isArray(type)){const hasNull=type.includes("null"),nonNullTypes=type.filter((t3)=>t3!=="null");if(nonNullTypes.length===0){result42.type="null";}else{result42.anyOf=nonNullTypes.map((t3)=>({type:t3}));if(hasNull){result42.nullable=true;}}}else{result42.type=type;}}if(enumValues!==void 0){result42.enum=enumValues.map(v=>String(v));}`;
const minifiedLen = Buffer.byteLength(minified, 'utf8');
const padding = ' '.repeat(targetLen - minifiedLen);
const replStr = minified + padding;

if (Buffer.byteLength(replStr, 'utf8') !== targetLen) {
  console.error('Byte length mismatch!', Buffer.byteLength(replStr, 'utf8'), 'vs', targetLen);
  process.exit(1);
}

const targetBuf = Buffer.from(targetStr, 'utf8');
const replBuf = Buffer.from(replStr, 'utf8');

const idx = originalBuf.indexOf(targetBuf);
if (idx === -1) {
  if (originalBuf.indexOf(replBuf) !== -1) {
    console.log('[✓] app.asar already patched for Gemini enum strings!');
    process.exit(0);
  }
  console.error('[-] Target block not found in app.asar');
  process.exit(1);
}

console.log('[*] Found target block at byte offset:', idx);

// Backup if not exists
const backupPath = asarPath + '.bak-enum';
if (!fs.existsSync(backupPath)) {
  fs.copyFileSync(asarPath, backupPath);
  console.log('[+] Created backup:', backupPath);
}

replBuf.copy(originalBuf, idx);

if (originalBuf.length !== originalLen) {
  console.error('CRITICAL: Total buffer length changed!');
  process.exit(1);
}

fs.writeFileSync(asarPath, originalBuf);
console.log('[+] Successfully patched app.asar! Gemini will now always receive string enums.');
