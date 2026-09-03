#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "Usage: ./inject.sh <path-to-target-project> [--include-skills]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/configs"
SKILLS_DIR="$SCRIPT_DIR/skills"
TARGET_DIR="$(cd "$1" 2>/dev/null && pwd || echo "$1")"

echo "=========================================================="
echo "   OpenCode Swarm Project Injector (macOS / Linux)        "
echo "=========================================================="
echo "[*] Target project: $TARGET_DIR"

mkdir -p "$TARGET_DIR/.opencode"

cp -f "$CONFIGS_DIR/opencode.jsonc" "$TARGET_DIR/.opencode/"
cp -f "$CONFIGS_DIR/opencode-swarm.json" "$TARGET_DIR/.opencode/"
cp -f "$CONFIGS_DIR/model-fallback.json" "$TARGET_DIR/.opencode/"
cp -f "$CONFIGS_DIR/skill-routing.yaml" "$TARGET_DIR/.opencode/"
echo "[+] Injected: .opencode/ configurations"

if [ "$2" == "--include-skills" ] || [ "$2" == "-s" ]; then
  mkdir -p "$TARGET_DIR/.agents/skills"
  cp -Rf "$SKILLS_DIR"/* "$TARGET_DIR/.agents/skills/"
  echo "[+] Injected bundled skills into .agents/skills/"
fi

# Run runtime patches
echo ""
echo "[*] Applying machine runtime patches..."
node "$SCRIPT_DIR/patches/patch-opencode-binary.js"
node "$SCRIPT_DIR/patches/patch-swarm-posix.js"
node "$SCRIPT_DIR/patches/patch-watchdog-timeout.js"

echo ""
echo "=========================================================="
echo "[OK] Project injection complete for $TARGET_DIR!"
echo "=========================================================="
