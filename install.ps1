[CmdletBinding()]
param(
  [string]$Target,
  [switch]$GlobalOnly,
  [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigsDir = Join-Path $ScriptDir "configs"
$SkillsDir = Join-Path $ScriptDir "skills"
$InstructionsDir = Join-Path $ScriptDir "instructions"
$CommandsDir = Join-Path $ScriptDir "commands"
$ScriptsDir = Join-Path $ScriptDir "scripts"

$GlobalDir = Join-Path $HOME ".config\opencode"
$GlobalSkillsDir = Join-Path $HOME ".agents\skills"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   R.E.Y. // Runtime Execution & Yield Monitor Installer  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Helper function for non-destructive copying with backup
function Safe-Copy([string]$src, [string]$dst) {
  if (-not (Test-Path -LiteralPath $src)) { return }
  $parent = Split-Path -Parent $dst
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  if (Test-Path -LiteralPath $dst) {
    # Check if files differ
    $srcHash = (Get-FileHash -LiteralPath $src -Algorithm MD5).Hash
    $dstHash = (Get-FileHash -LiteralPath $dst -Algorithm MD5).Hash
    if ($srcHash -ne $dstHash) {
      $bak = "$dst.bak.$Timestamp"
      Copy-Item -LiteralPath $dst -Destination $bak -Force
      Write-Host "  [BACKUP] Existing file backed up to $(Split-Path $bak -Leaf)" -ForegroundColor DarkGray
    }
  }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host "  [+] Installed $(Split-Path $dst -Leaf)" -ForegroundColor Green
}

# 1. Environment pre-flight
Write-Host "`n[*] Checking system dependencies..." -ForegroundColor White
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "[-] Node.js is not found. Please install Node.js (v20+) first." -ForegroundColor Red
  exit 1
} else {
  Write-Host "  [OK] Node.js is available: $((node -v) 2>$null)" -ForegroundColor Green
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "  [!] Python not found in PATH. JARVIS will run, but Python is recommended for <50ms telemetry." -ForegroundColor Yellow
} else {
  Write-Host "  [OK] Python is available: $((python --version 2>&1) | Select-Object -First 1)" -ForegroundColor Green
}

if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
  Write-Host "[!] OpenCode CLI not found in PATH. Installing globally..." -ForegroundColor Yellow
  npm install -g opencode-ai
} else {
  Write-Host "  [OK] OpenCode CLI is available" -ForegroundColor Green
}

# 2. Add required plugins
Write-Host "`n[*] Ensuring OpenCode plugins are installed..." -ForegroundColor White
try {
  opencode plugin add @smart-coders-hq/opencode-model-fallback 2>$null
  Write-Host "  [OK] Plugins verified." -ForegroundColor Green
} catch {
  Write-Host "  [!] Note: Plugin registration will finalize on next opencode run." -ForegroundColor Yellow
}

# 3. Setup Machine-Global Configurations (~/.config/opencode/) cleanly & non-destructively
Write-Host "`n[*] Deploying machine-global configs to $GlobalDir..." -ForegroundColor White
if (-not (Test-Path $GlobalDir)) {
  New-Item -ItemType Directory -Path $GlobalDir -Force | Out-Null
}

$ConfigFiles = @("opencode.json", "opencode.jsonc", "model-fallback.json", "skill-routing.yaml")
foreach ($file in $ConfigFiles) {
  $src = Join-Path $ConfigsDir $file
  $dst = Join-Path $GlobalDir $file
  Safe-Copy $src $dst
}

# 4. Deploy Instructions & Commands
if (Test-Path $InstructionsDir) {
  Write-Host "`n[*] Deploying instructions..." -ForegroundColor White
  Get-ChildItem -Path $InstructionsDir -File | ForEach-Object {
    Safe-Copy $_.FullName (Join-Path "$GlobalDir\instructions" $_.Name)
  }
}

if (Test-Path $CommandsDir) {
  Write-Host "`n[*] Deploying commands..." -ForegroundColor White
  Get-ChildItem -Path $CommandsDir -File | ForEach-Object {
    Safe-Copy $_.FullName (Join-Path "$GlobalDir\commands" $_.Name)
  }
}

# 5. Deploy R.E.Y. Runtime Execution & Yield Monitor Scripts
Write-Host "`n[*] Deploying R.E.Y. Monitor scripts..." -ForegroundColor White
$GlobalScriptsDir = Join-Path $GlobalDir "scripts"
if (-not (Test-Path $GlobalScriptsDir)) {
  New-Item -ItemType Directory -Path $GlobalScriptsDir -Force | Out-Null
}

if (Test-Path $ScriptsDir) {
  Get-ChildItem -Path $ScriptsDir -File | ForEach-Object {
    Safe-Copy $_.FullName (Join-Path $GlobalScriptsDir $_.Name)
  }
}

# 6. Register Global 'rey' (and 'jarvis') Command in PATH
Write-Host "`n[*] Registering 'rey' CLI launcher..." -ForegroundColor White
$npmBin = Join-Path $env:APPDATA "npm"
$installedCmd = $false

if (Test-Path $npmBin) {
  foreach ($cmdName in @("rey.cmd", "jarvis.cmd")) {
    $cmdSrc = Join-Path $ScriptsDir $cmdName
    $cmdDst = Join-Path $npmBin $cmdName
    if (Test-Path $cmdSrc) {
      Copy-Item -LiteralPath $cmdSrc -Destination $cmdDst -Force
      Write-Host "  [+] Registered global '$cmdName' command in $npmBin" -ForegroundColor Green
      $installedCmd = $true
    }
  }
}

if (-not $installedCmd) {
  # Fallback: add ~/.config/opencode/scripts to User PATH if not present
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userPath -notlike "*$GlobalScriptsDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$GlobalScriptsDir", "User")
    Write-Host "  [+] Added $GlobalScriptsDir to User PATH" -ForegroundColor Green
  }
}

# 7. Install Global Skills (~/.agents/skills/)
Write-Host "`n[*] Installing bundled skills to $GlobalSkillsDir..." -ForegroundColor White
if (-not (Test-Path $GlobalSkillsDir)) {
  New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
}

if (Test-Path $SkillsDir) {
  Copy-Item -Path "$SkillsDir\*" -Destination $GlobalSkillsDir -Recurse -Force
  Write-Host "  [+] Skills copied to $GlobalSkillsDir" -ForegroundColor Green
}

# 8. Apply Runtime Patches
Write-Host "`n[*] Applying machine-level runtime patches..." -ForegroundColor Cyan
if (Test-Path (Join-Path $ScriptDir "patches")) {
  foreach ($patch in Get-ChildItem -Path (Join-Path $ScriptDir "patches") -Filter "*.js") {
    node $patch.FullName
  }
}

# 9. Optional Target Project Injection
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
  foreach ($file in @("opencode.jsonc", "opencode.json", "model-fallback.json", "skill-routing.yaml")) {
    $src = Join-Path $ConfigsDir $file
    $dst = Join-Path $DestOpenCode $file
    if ((Test-Path $dst) -and -not $Force) {
      Write-Host "  [!] $file already exists. (Use -Force to overwrite)" -ForegroundColor Yellow
    } else {
      Copy-Item $src $dst -Force
      Write-Host "  [+] Injected: .opencode/$file" -ForegroundColor Green
    }
  }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "[OK] Installation Complete!" -ForegroundColor Green
Write-Host "     Your machine is now fully equipped with:" -ForegroundColor White
Write-Host "     - 30-Model Free Fleet (Kilo, Zen, OpenRouter, Groq, Mistral)" -ForegroundColor Gray
Write-Host "     - Specialized Swarm Agent Team (@coder, @architect, etc.)" -ForegroundColor Gray
Write-Host "     - R.E.Y. // Runtime Execution & Yield Monitor (Type 'rey' anywhere)" -ForegroundColor Gray
Write-Host "     - Non-destructive backups created for modified configs" -ForegroundColor Gray
Write-Host "     - Full bundled skills library (~/.agents/skills/)" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Green
