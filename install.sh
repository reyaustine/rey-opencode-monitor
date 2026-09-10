#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/configs"
SKILLS_DIR="$SCRIPT_DIR/skills"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
GLOBAL_DIR="$HOME/.config/opencode"
GLOBAL_SKILLS_DIR="$HOME/.agents/skills"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

echo "=========================================================="
echo "   R.E.Y. // Runtime Execution & Yield Monitor Installer  "
echo "   (macOS & Linux Support)                                "
echo "=========================================================="

# Safe-Copy with non-destructive backup
safe_copy() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then return; fi
  mkdir -p "$(dirname "$dst")"
  if [ -f "$dst" ]; then
    local src_hash dst_hash
    if command -v md5 >/dev/null 2>&1; then
      src_hash=$(md5 -q "$src")
      dst_hash=$(md5 -q "$dst")
    elif command -v md5sum >/dev/null 2>&1; then
      src_hash=$(md5sum "$src" | awk '{print $1}')
      dst_hash=$(md5sum "$dst" | awk '{print $1}')
    else
      src_hash="1"
      dst_hash="2"
    fi
    if [ "$src_hash" != "$dst_hash" ]; then
      local bak="${dst}.bak.${TIMESTAMP}"
      cp -f "$dst" "$bak"
      echo "  [BACKUP] Existing file backed up to $(basename "$bak")"
    fi
  fi
  cp -f "$src" "$dst"
}

# 1. Check Python 3 (Required for macOS R.E.Y. monitor)
echo "[*] Checking Python 3..."
if command -v python3 >/dev/null 2>&1; then
  echo "  [+] Python 3 found: $(python3 --version)"
elif command -v python >/dev/null 2>&1; then
  echo "  [+] Python found: $(python --version)"
else
  echo "[-] Python 3 is recommended for running R.E.Y. CLI on macOS."
fi

# 2. Check Node.js and OpenCode CLI
echo ""
echo "[*] Checking Node.js and OpenCode CLI..."
if ! command -v node >/dev/null 2>&1; then
  echo "[!] Node.js not found. Please install Node.js (v20+) if you need OpenCode desktop/CLI."
fi

# 3. Setup Machine-Global Configurations (~/.config/opencode/)
echo ""
echo "[*] Setting up machine-global configs in $GLOBAL_DIR..."
mkdir -p "$GLOBAL_DIR"

for cfg in "opencode.json" "opencode.jsonc" "model-fallback.json" "skill-routing.yaml"; do
  if [ -f "$CONFIGS_DIR/$cfg" ]; then
    safe_copy "$CONFIGS_DIR/$cfg" "$GLOBAL_DIR/$cfg"
    echo "  [+] Installed $cfg"
  fi
done

# 4. Deploy R.E.Y. Monitor Scripts (~/.config/opencode/scripts/)
echo ""
echo "[*] Deploying R.E.Y. monitor scripts..."
mkdir -p "$GLOBAL_DIR/scripts"

if [ -d "$SCRIPTS_DIR" ]; then
  for s in "$SCRIPTS_DIR"/*; do
    if [ -f "$s" ]; then
      safe_copy "$s" "$GLOBAL_DIR/scripts/$(basename "$s")"
    fi
  done
fi

chmod +x "$GLOBAL_DIR/scripts/rey" 2>/dev/null || true
chmod +x "$GLOBAL_DIR/scripts/jarvis" 2>/dev/null || true
chmod +x "$GLOBAL_DIR/scripts/rey-monitor.py" 2>/dev/null || true

# 5. Register Global 'rey' Command in PATH
echo ""
echo "[*] Registering global 'rey' CLI command..."
INSTALLED_BIN=false

# Try linking into standard bin directories if writable
for bin_dir in "$HOME/.local/bin" "$HOME/bin" "/usr/local/bin"; do
  if [ -d "$bin_dir" ] && [ -w "$bin_dir" ]; then
    ln -sf "$GLOBAL_DIR/scripts/rey" "$bin_dir/rey" 2>/dev/null || cp -f "$GLOBAL_DIR/scripts/rey" "$bin_dir/rey"
    ln -sf "$GLOBAL_DIR/scripts/jarvis" "$bin_dir/jarvis" 2>/dev/null || cp -f "$GLOBAL_DIR/scripts/jarvis" "$bin_dir/jarvis"
    echo "  [+] Linked 'rey' and 'jarvis' commands into $bin_dir"
    INSTALLED_BIN=true
    break
  fi
done

# Also ensure ~/.config/opencode/scripts is added to shell profiles
SHELL_PROFILES=("$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc")
EXPORT_LINE='export PATH="$HOME/.config/opencode/scripts:$PATH"'

for prof in "${SHELL_PROFILES[@]}"; do
  if [ -f "$prof" ]; then
    if ! grep -q "opencode/scripts" "$prof"; then
      echo "" >> "$prof"
      echo "# R.E.Y. // OpenCode Monitor CLI" >> "$prof"
      echo "$EXPORT_LINE" >> "$prof"
      echo "  [+] Added R.E.Y. scripts to $prof"
    fi
  fi
done

# 6. Install Global Skills (~/.agents/skills/)
echo ""
echo "[*] Installing bundled skills to $GLOBAL_SKILLS_DIR..."
mkdir -p "$GLOBAL_SKILLS_DIR"
if [ -d "$SKILLS_DIR" ]; then
  cp -Rf "$SKILLS_DIR"/* "$GLOBAL_SKILLS_DIR/"
  echo "  [+] Global skills library installed successfully!"
fi

# 7. Apply Runtime Stability Patches
echo ""
echo "[*] Applying machine-level runtime patches..."
if [ -d "$SCRIPT_DIR/patches" ] && command -v node >/dev/null 2>&1; then
  for p in "$SCRIPT_DIR/patches"/*.js; do
    if [ -f "$p" ]; then
      node "$p" 2>/dev/null || true
    fi
  done
fi

echo ""
echo "=========================================================="
echo "[OK] Installation Complete!"
echo "     Your Mac is now fully equipped with:"
echo "     - 30-Model Free Fleet & 10-Agent Swarm Team"
echo "     - R.E.Y. // Runtime Execution & Yield Monitor"
echo "     - All-Time & Per-Model Token Usage Tracker"
echo "     - Launch anytime in Terminal by typing: rey"
echo "=========================================================="
