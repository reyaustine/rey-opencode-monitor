const fs = require('fs');

const p1 = 'C:/Users/rey.echavez/.cache/opencode/packages/@smart-coders-hq/opencode-model-fallback/node_modules/@smart-coders-hq/opencode-model-fallback/dist/index.js';
const p2 = 'C:/Users/rey.echavez/.cache/opencode/packages/@smart-coders-hq/opencode-model-fallback@latest/node_modules/@smart-coders-hq/opencode-model-fallback/dist/index.js';

function fixModelKeyRegex(file) {
  if (!fs.existsSync(file)) return;
  let content = fs.readFileSync(file, 'utf8');
  const target = 'var MODEL_KEY_RE2 = /^[a-zA-Z0-9_-]{1,100}\\/[a-zA-Z0-9._-]{1,100}$/;';
  const replacement = 'var MODEL_KEY_RE2 = /^[a-zA-Z0-9_-]{1,100}\\/[a-zA-Z0-9._/:-]{1,150}$/;';
  if (content.includes(target)) {
    content = content.replace(target, replacement);
    fs.writeFileSync(file, content, 'utf8');
    console.log('Fixed MODEL_KEY_RE2 in:', file);
  } else {
    console.log('Already fixed or target not found in:', file);
  }
}

fixModelKeyRegex(p1);
fixModelKeyRegex(p2);
