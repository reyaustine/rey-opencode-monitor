[CmdletBinding()]
param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$Target,
  [switch]$IncludeSkills,
  [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigsDir = Join-Path $ScriptDir "configs"
$SkillsDir = Join-Path $ScriptDir "skills"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   OpenCode Swarm Project Injector                        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$TargetDir = [System.IO.Path]::GetFullPath($Target)
Write-Host "[*] Target project: $TargetDir" -ForegroundColor White

if (-not (Test-Path $TargetDir)) {
  Write-Host "[*] Creating target directory: $TargetDir" -ForegroundColor Yellow
  New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

$DestOpenCode = Join-Path $TargetDir ".opencode"
if (-not (Test-Path $DestOpenCode)) {
  New-Item -ItemType Directory -Path $DestOpenCode -Force | Out-Null
  Write-Host "[+] Created .opencode/ folder in target" -ForegroundColor Green
}

$ConfigFiles = @("opencode.jsonc", "opencode-swarm.json", "model-fallback.json", "skill-routing.yaml")
foreach ($file in $ConfigFiles) {
  $src = Join-Path $ConfigsDir $file
  $dst = Join-Path $DestOpenCode $file
  if ((Test-Path $dst) -and -not $Force) {
    Write-Host "[!] $file already exists. (Use -Force to overwrite)" -ForegroundColor Yellow
  } else {
    Copy-Item $src $dst -Force
    Write-Host "[+] Injected: .opencode/$file" -ForegroundColor Green
  }
}

if ($IncludeSkills) {
  $TargetSkills = Join-Path $TargetDir ".agents\skills"
  New-Item -ItemType Directory -Path $TargetSkills -Force | Out-Null
  Copy-Item -Recurse -Force (Join-Path $SkillsDir "*") $TargetSkills
  Write-Host "[+] Injected bundled skills into .agents/skills" -ForegroundColor Green
}

# Run runtime patches to ensure machine stability
Write-Host "`n[*] Applying machine stability patches..." -ForegroundColor Cyan
node (Join-Path $ScriptDir "patches\patch-opencode-binary.js")
node (Join-Path $ScriptDir "patches\patch-swarm-posix.js")
node (Join-Path $ScriptDir "patches\patch-watchdog-timeout.js")

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "[OK] Project injection complete for $TargetDir!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
