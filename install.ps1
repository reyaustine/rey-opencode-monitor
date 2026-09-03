[CmdletBinding()]
param(
  [string]$Target,
  [switch]$GlobalOnly,
  [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigsDir = Join-Path $ScriptDir "configs"
$SkillsDir = Join-Path $ScriptDir "skills"
$GlobalDir = Join-Path $HOME ".config\opencode"
$GlobalSkillsDir = Join-Path $HOME ".agents\skills"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   OpenCode Swarm & Model-Fallback Master Installer       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment pre-flight
Write-Host "[*] Checking Node.js and OpenCode installation..." -ForegroundColor White
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "[-] Node.js is not found. Please install Node.js (v20+) first." -ForegroundColor Red
  exit 1
}

if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
  Write-Host "[!] OpenCode CLI not found in PATH. Installing globally..." -ForegroundColor Yellow
  npm install -g opencode-ai
}

# 2. Add required plugins
Write-Host "`n[*] Ensuring OpenCode plugins are installed..." -ForegroundColor White
try {
  opencode plugin add @smart-coders-hq/opencode-model-fallback opencode-swarm 2>$null
  Write-Host "[OK] Plugins verified." -ForegroundColor Green
} catch {
  Write-Host "[!] Note: Plugin registration will finalize on next opencode run." -ForegroundColor Yellow
}

# 3. Setup Machine-Global Configurations (~/.config/opencode/)
Write-Host "`n[*] Setting up machine-global configs in $GlobalDir..." -ForegroundColor White
if (-not (Test-Path $GlobalDir)) {
  New-Item -ItemType Directory -Path $GlobalDir -Force | Out-Null
}

$ConfigFiles = @("opencode.jsonc", "opencode-swarm.json", "model-fallback.json")
foreach ($file in $ConfigFiles) {
  $src = Join-Path $ConfigsDir $file
  $dst = Join-Path $GlobalDir $file
  Copy-Item $src $dst -Force
  Write-Host "[+] Installed global config: $file" -ForegroundColor Green
}

# 4. Install Global Skills (~/.agents/skills/)
Write-Host "`n[*] Installing bundled skills to $GlobalSkillsDir..." -ForegroundColor White
if (-not (Test-Path $GlobalSkillsDir)) {
  New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
}
Copy-Item -Recurse -Force (Join-Path $SkillsDir "*") $GlobalSkillsDir
Write-Host "[OK] Global skills library installed successfully!" -ForegroundColor Green

# 5. Apply Runtime Patches
Write-Host "`n[*] Applying machine-level runtime patches..." -ForegroundColor Cyan
node (Join-Path $ScriptDir "patches\patch-opencode-binary.js")
node (Join-Path $ScriptDir "patches\patch-desktop-asar.js")
node (Join-Path $ScriptDir "patches\patch-swarm-posix.js")
node (Join-Path $ScriptDir "patches\patch-swarm-parse-error.js")
node (Join-Path $ScriptDir "patches\patch-fast-boot.js")
node (Join-Path $ScriptDir "patches\patch-watchdog-timeout.js")
node (Join-Path $ScriptDir "patches\fix-model-key-regex.js")

# 6. Optional Target Project Injection
if ($Target -and -not $GlobalOnly) {
  $TargetDir = [System.IO.Path]::GetFullPath($Target)
  Write-Host "`n[*] Injecting OpenCode Swarm into project: $TargetDir" -ForegroundColor White
  if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
  }
  $DestOpenCode = Join-Path $TargetDir ".opencode"
  if (-not (Test-Path $DestOpenCode)) {
    New-Item -ItemType Directory -Path $DestOpenCode -Force | Out-Null
  }
  foreach ($file in @("opencode.jsonc", "opencode-swarm.json", "model-fallback.json", "skill-routing.yaml")) {
    $src = Join-Path $ConfigsDir $file
    $dst = Join-Path $DestOpenCode $file
    Copy-Item $src $dst -Force
    Write-Host "[+] Injected: .opencode/$file" -ForegroundColor Green
  }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "[OK] Installation Complete!" -ForegroundColor Green
Write-Host "     This machine is now fully equipped with:" -ForegroundColor White
Write-Host "     - 22-agent specialized Swarm roster (DeepSeek primary)" -ForegroundColor Gray
Write-Host "     - Automatic 3-second rate-limit retry clamp" -ForegroundColor Gray
Write-Host "     - 90-second watchdog auto-abort & failover" -ForegroundColor Gray
Write-Host "     - Windows PowerShell write-detection fix" -ForegroundColor Gray
Write-Host "     - Full bundled skills library (~/.agents/skills/)" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Green
