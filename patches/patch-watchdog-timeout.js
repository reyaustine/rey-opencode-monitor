const fs = require('fs');
const path = require('path');

const cacheDir = path.join(process.env.USERPROFILE || '', '.cache', 'opencode', 'packages', '@smart-coders-hq');

function findFallbackIndexFiles(dir) {
  const results = [];
  if (!fs.existsSync(dir)) return results;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('opencode-model-fallback')) {
        const candidate = path.join(fullPath, 'node_modules', '@smart-coders-hq', 'opencode-model-fallback', 'dist', 'index.js');
        if (fs.existsSync(candidate)) results.push(candidate);
      }
      results.push(...findFallbackIndexFiles(fullPath));
    }
  }
  return [...new Set(results)];
}

const files = findFallbackIndexFiles(cacheDir);
if (files.length === 0) {
  console.log('[*] No opencode-model-fallback packages found in cache.');
  process.exit(0);
}

const target = `async function handleEvent(event, client, store, config, logger, directory) {
  logger.debug("event.received", { type: event.type });
  if (event.type === "session.status") {
    const { sessionID, status } = event.properties;
    if (status.type === "retry") {
      await handleRetry(sessionID, status.message, client, store, config, logger, directory);
    } else if (status.type === "idle") {
      await handleIdle(sessionID, client, store, config, logger);
    }
    return;
  }`;

const replacement = `const sessionWatchdogs = new Map();
async function handleEvent(event, client, store, config, logger, directory) {
  logger.debug("event.received", { type: event.type });
  if (event.type === "session.status") {
    const { sessionID, status } = event.properties;
    if (status.type === "busy") {
      if (!sessionWatchdogs.has(sessionID)) {
        const timeoutMs = (config.defaults && config.defaults.timeoutMs) || 90000;
        const timer = setTimeout(async () => {
          sessionWatchdogs.delete(sessionID);
          logger.warn("watchdog.timeout - model did not respond within timeout, triggering fallback", { sessionID, timeoutMs });
          try {
            const result = await attemptFallback(sessionID, "timeout", client, store, config, logger, directory);
            if (result.success && result.fallbackModel) {
              await notifyFallback(client, result.fromModel ?? null, result.fallbackModel, "timeout");
            }
          } catch (err) {
            logger.error("watchdog.fallback.error", { sessionID, error: String(err) });
          }
        }, timeoutMs);
        sessionWatchdogs.set(sessionID, timer);
      }
    } else {
      if (sessionWatchdogs.has(sessionID)) {
        clearTimeout(sessionWatchdogs.get(sessionID));
        sessionWatchdogs.delete(sessionID);
      }
      if (status.type === "retry") {
        await handleRetry(sessionID, status.message, client, store, config, logger, directory);
      } else if (status.type === "idle") {
        await handleIdle(sessionID, client, store, config, logger);
      }
    }
    return;
  }`;

for (const file of files) {
  console.log('[*] Checking:', file);
  let content = fs.readFileSync(file, 'utf8');
  if (content.includes('const sessionWatchdogs = new Map();')) {
    console.log('[✓] Already patched with 90s watchdog timeout:', file);
    continue;
  }
  if (content.includes(target)) {
    content = content.replace(target, replacement);

    const deletedTarget = `if (event.type === "session.deleted") {
    const { sessionID } = event.properties;
    if (!sessionID)
      return;
    store.sessions.delete(sessionID);`;

    const deletedReplacement = `if (event.type === "session.deleted") {
    const { sessionID } = event.properties;
    if (!sessionID)
      return;
    if (sessionWatchdogs.has(sessionID)) {
      clearTimeout(sessionWatchdogs.get(sessionID));
      sessionWatchdogs.delete(sessionID);
    }
    store.sessions.delete(sessionID);`;

    if (content.includes(deletedTarget)) {
      content = content.replace(deletedTarget, deletedReplacement);
    }

    fs.writeFileSync(file + '.bak', fs.readFileSync(file));
    fs.writeFileSync(file, content, 'utf8');
    console.log('[+] Successfully installed 90s watchdog timeout into:', file);
  } else {
    console.log('[?] Target function not found in:', file);
  }
}
