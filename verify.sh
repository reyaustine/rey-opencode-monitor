#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "   OpenCode Swarm Diagnostic & Health Check (macOS/Linux) "
echo "=========================================================="

if command -v opencode >/dev/null 2>&1; then
  VERSION=$(opencode --version 2>/dev/null || echo "detected")
  echo "[OK] OpenCode CLI installed: v$VERSION"
else
  echo "[-] OpenCode CLI not found in PATH."
fi

echo ""
echo "[*] Verifying runtime stability patches..."
for patch in patch-opencode-binary.js patch-desktop-asar.js patch-gemini-enum.js \
             patch-watchdog-timeout.js patch-context-length-fallback.js fix-model-key-regex.js; do
  p="$SCRIPT_DIR/patches/$patch"
  if [ -f "$p" ]; then
    node "$p" 2>/dev/null || true
  else
    echo "  [SKIP] $patch not found"
  fi
done

echo ""
echo "[*] Querying opencode agent list..."
AGENT_COUNT=$(opencode agent list 2>&1 | grep -E '^\s*-\s+[a-zA-Z]' | wc -l | tr -d ' ' || echo "0")
if [ "$AGENT_COUNT" -gt 0 ]; then
  echo "[OK] Successfully loaded $AGENT_COUNT agents into OpenCode Swarm!"
else
  echo "[!] Agent list returned no items or output was verbose."
fi

echo ""
echo "=========================================================="
echo "[OK] Diagnostic Complete."
echo "=========================================================="
