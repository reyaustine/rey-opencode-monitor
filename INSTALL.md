# OpenServe Config Export
## Portable Global Config Package

### Install Instructions

**Windows (PowerShell):**
  Expand-Archive -Path '.\opencode-config.zip' -DestinationPath $env:USERPROFILE -Force

**Linux / macOS:**
  unzip opencode-config.zip -d ~/

This will extract to ~/.config/opencode/ (global level).

### Included Files
- opencode.json          (primary config)
- opencode.jsonc         (jsonc variant)
- model-fallback.json    (fallback chain config)
- skill-routing.yaml     (skill-to-agent routing)
- package.json           (plugin dependencies)
- instructions/delegation.md (swarm delegation policy)

### Post-Install
  cd ~/.config/opencode && npm install
  (installs @opencode-ai/plugin dependency)
