#!/usr/bin/env bash
set -e

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
node "$SCRIPT_DIR/patches/patch-opencode-binary.js"
node "$SCRIPT_DIR/patches/patch-desktop-asar.js"
node "$SCRIPT_DIR/patches/patch-gemini-enum.js"
node "$SCRIPT_DIR/patches/patch-swarm-posix.js"
node "$SCRIPT_DIR/patches/patch-swarm-parse-error.js"
node "$SCRIPT_DIR/patches/patch-fast-boot.js"
node "$SCRIPT_DIR/patches/patch-watchdog-timeout.js"
node "$SCRIPT_DIR/patches/patch-context-length-fallback.js"
node "$SCRIPT_DIR/patches/fix-model-key-regex.js"

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
