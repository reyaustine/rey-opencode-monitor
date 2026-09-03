#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/configs"
SKILLS_DIR="$SCRIPT_DIR/skills"
GLOBAL_DIR="$HOME/.config/opencode"
GLOBAL_SKILLS_DIR="$HOME/.agents/skills"

echo "=========================================================="
echo "   OpenCode Swarm & Model-Fallback Master Installer       "
echo "=========================================================="

# 1. Check Node.js and OpenCode CLI
echo "[*] Checking Node.js and OpenCode CLI..."
if ! command -v node >/dev/null 2>&1; then
  echo "[-] Node.js is not found. Please install Node.js (v20+) first."
  exit 1
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "[!] OpenCode CLI not found. Installing globally via npm..."
  npm install -g opencode-ai
fi

# 2. Add required plugins
echo ""
echo "[*] Ensuring OpenCode plugins are installed..."
opencode plugin add @smart-coders-hq/opencode-model-fallback opencode-swarm >/dev/null 2>&1 || true
echo "[OK] Plugins registered."

# 3. Setup Machine-Global Configurations (~/.config/opencode/)
echo ""
echo "[*] Setting up machine-global configs in $GLOBAL_DIR..."
mkdir -p "$GLOBAL_DIR"

cp -f "$CONFIGS_DIR/opencode.jsonc" "$GLOBAL_DIR/opencode.jsonc"
cp -f "$CONFIGS_DIR/opencode-swarm.json" "$GLOBAL_DIR/opencode-swarm.json"
cp -f "$CONFIGS_DIR/model-fallback.json" "$GLOBAL_DIR/model-fallback.json"
echo "[+] Installed global configs into ~/.config/opencode/"

# 4. Install Global Skills (~/.agents/skills/)
echo ""
echo "[*] Installing bundled skills to $GLOBAL_SKILLS_DIR..."
mkdir -p "$GLOBAL_SKILLS_DIR"
cp -Rf "$SKILLS_DIR"/* "$GLOBAL_SKILLS_DIR/"
echo "[OK] Global skills library installed successfully!"

# 5. Apply Runtime Stability Patches
echo ""
echo "[*] Applying machine-level runtime patches..."
node "$SCRIPT_DIR/patches/patch-opencode-binary.js"
node "$SCRIPT_DIR/patches/patch-desktop-asar.js"
node "$SCRIPT_DIR/patches/patch-swarm-posix.js"
node "$SCRIPT_DIR/patches/patch-swarm-parse-error.js"
node "$SCRIPT_DIR/patches/patch-watchdog-timeout.js"
node "$SCRIPT_DIR/patches/fix-model-key-regex.js"

# 6. Optional Target Project Injection
if [ -n "$1" ] && [ "$1" != "--global-only" ] && [ "$1" != "-g" ]; then
  TARGET_DIR="$(cd "$1" 2>/dev/null && pwd || echo "$1")"
  echo ""
  echo "[*] Injecting OpenCode Swarm into project: $TARGET_DIR"
  mkdir -p "$TARGET_DIR/.opencode"
  cp -f "$CONFIGS_DIR/opencode.jsonc" "$TARGET_DIR/.opencode/"
  cp -f "$CONFIGS_DIR/opencode-swarm.json" "$TARGET_DIR/.opencode/"
  cp -f "$CONFIGS_DIR/model-fallback.json" "$TARGET_DIR/.opencode/"
  cp -f "$CONFIGS_DIR/skill-routing.yaml" "$TARGET_DIR/.opencode/"
  echo "[+] Injected configs into $TARGET_DIR/.opencode/"
fi

echo ""
echo "=========================================================="
echo "[OK] Installation Complete!"
echo "     This machine is now fully equipped with:"
echo "     - 22-agent specialized Swarm roster (DeepSeek primary)"
echo "     - Automatic 3-second rate-limit retry clamp"
echo "     - 90-second watchdog auto-abort & failover"
echo "     - Full bundled skills library (~/.agents/skills/)"
echo "=========================================================="
