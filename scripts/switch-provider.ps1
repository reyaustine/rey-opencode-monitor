<#
.SYNOPSIS
    OpenCode Free Model Provider Switcher
.DESCRIPTION
    Switches between Kilo, OpenCode, and OpenRouter free model providers
    by updating opencode.jsonc, opencode.json, and model-fallback.json.
.PARAMETER Provider
    Target provider: kilo, opencode, or openrouter
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("kilo", "opencode", "openrouter")]
    [string]$Provider
)

$baseDir = Join-Path $HOME ".config\opencode"
$jsoncPath = Join-Path $baseDir "opencode.jsonc"
$jsonPath  = Join-Path $baseDir "opencode.json"
$fbPath    = Join-Path $baseDir "model-fallback.json"

# ─────────────────────────────────────────────
# Agent model assignments per provider
# ─────────────────────────────────────────────
$agentModels = @{
    "kilo" = @{
        "build"        = "kilo/kilo-auto/free"
        "explore"      = "kilo/kilo-auto/free"
        "plan"         = "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
        "general"      = "gemini/gemini-3.6-flash"
        "compaction"   = "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
        "orchestrator" = "kilo/kilo-auto/free"
        "coder"        = "kilo/cohere/north-mini-code:free"
        "linter"       = "kilo/poolside/laguna-xs-2.1:free"
        "qa"           = "kilo/nvidia/nemotron-3.5-lightning:free"
        "tester"       = "kilo/poolside/laguna-xs-2.1:free"
        "verifier"     = "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
        "reviewer"     = "kilo/nvidia/nemotron-3-super-120b-a12b:free"
        "explorer"     = "kilo/inclusionai/ling-3.0-flash-fin:free"
        "architect"    = "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
        "critic"       = "kilo/liquid/lfm-2.5-2.6b:free"
        "researcher"   = "gemini/gemini-3.7-flash"
        "docs"         = "kilo/nex-agi/nex-n2.5-pro:free"
        "designer"     = "kilo/thinkingmachines/inkling-small:free"
    }
    "opencode" = @{
        "build"        = "opencode/mimo-v2.5-free"
        "explore"      = "opencode/ling-3.0-flash-fin-free"
        "plan"         = "opencode/mimo-v2.5-free"
        "general"      = "gemini/gemini-3.6-flash"
        "compaction"   = "opencode/mimo-v2.5-free"
        "orchestrator" = "opencode/mimo-v2.5-free"
        "coder"        = "opencode/mimo-v2.5-free"
        "linter"       = "opencode/ling-3.0-flash-fin-free"
        "qa"           = "opencode/mimo-v2.5-free"
        "tester"       = "opencode/ling-3.0-flash-fin-free"
        "verifier"     = "opencode/mimo-v2.5-free"
        "reviewer"     = "opencode/mimo-v2.5-free"
        "explorer"     = "opencode/ling-3.0-flash-fin-free"
        "architect"    = "opencode/mimo-v2.5-free"
        "critic"       = "opencode/ling-3.0-flash-fin-free"
        "researcher"   = "gemini/gemini-3.7-flash"
        "docs"         = "opencode/mimo-v2.5-free"
        "designer"     = "opencode/mimo-v2.5-free"
    }
    "openrouter" = @{
        "build"        = "openrouter/google/gemma-4-26b-a4b-it:free"
        "explore"      = "openrouter/inclusionai/ling-3.0-flash-fin:free"
        "plan"         = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
        "general"      = "gemini/gemini-3.6-flash"
        "compaction"   = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
        "orchestrator" = "openrouter/openrouter/free"
        "coder"        = "openrouter/cohere/north-mini-code:free"
        "linter"       = "openrouter/poolside/laguna-xs-2.1:free"
        "qa"           = "openrouter/nvidia/nemotron-3.5-lightning:free"
        "tester"       = "openrouter/poolside/laguna-xs-2.1:free"
        "verifier"     = "openrouter/google/gemma-4-31b-it:free"
        "reviewer"     = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
        "explorer"     = "openrouter/inclusionai/ling-3.0-flash-fin:free"
        "architect"    = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
        "critic"       = "openrouter/liquid/lfm-2.5-2.6b:free"
        "researcher"   = "gemini/gemini-3.7-flash"
        "docs"         = "openrouter/nex-agi/nex-n2.5-pro:free"
        "designer"     = "openrouter/thinkingmachines/inkling:free"
    }
}

# ─────────────────────────────────────────────
# Fallback chain model sets per provider
# ─────────────────────────────────────────────
$fallbackChains = @{
    "kilo" = @(
        "opencode/mimo-v2.5-free"
        "opencode/ling-3.0-flash-fin-free"
        "mistral/codestral-latest"
        "opencode/nemotron-3.5-lightning-free"
        "kilo/kilo-auto/free"
        "opencode/big-pickle"
        "gemini/gemini-3.6-flash"
        "kilo/nex-agi/nex-n2.5-mini:free"
        "kilo/nvidia/nemotron-3.5-lightning:free"
        "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
        "kilo/poolside/laguna-xs-2.1:free"
        "kilo/poolside/laguna-s-2.1:free"
    )
    "opencode" = @(
        "opencode/mimo-v2.5-free"
        "opencode/ling-3.0-flash-fin-free"
        "mistral/codestral-latest"
        "opencode/nemotron-3.5-lightning-free"
        "opencode/big-pickle"
        "opencode/muse-spark-1.3-free"
        "opencode/nemotron-3-ultra-free"
        "gemini/gemini-3.6-flash"
        "kilo/kilo-auto/free"
        "kilo/poolside/laguna-xs-2.1:free"
        "kilo/nvidia/nemotron-3-ultra-550b-a55b:free"
    )
    "openrouter" = @(
        "openrouter/free"
        "openrouter/google/gemma-4-26b-a4b-it:free"
        "openrouter/nvidia/nemotron-3.5-lightning:free"
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
        "openrouter/poolside/laguna-xs-2.1:free"
        "openrouter/inclusionai/ling-3.0-flash-fin:free"
        "openrouter/google/gemma-4-31b-it:free"
        "openrouter/thinkingmachines/inkling:free"
        "opencode/mimo-v2.5-free"
        "opencode/ling-3.0-flash-fin-free"
        "mistral/codestral-latest"
        "kilo/kilo-auto/free"
        "gemini/gemini-3.6-flash"
    )
}

# ─────────────────────────────────────────────
# Backup current files
# ─────────────────────────────────────────────
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($file in @($jsoncPath, $jsonPath, $fbPath)) {
    if (Test-Path $file) {
        $bakPath = "$file.bak.switcher.$timestamp"
        Copy-Item $file $bakPath -Force
        Write-Host "  Backed up: $(Split-Path $file -Leaf) -> $(Split-Path $bakPath -Leaf)"
    }
}

# ─────────────────────────────────────────────
# Helper: get leading whitespace from a line
# ─────────────────────────────────────────────
function Get-Indent($line) {
    if ($line -match '^(\s*)') { return $Matches[1] }
    return ""
}

# ─────────────────────────────────────────────
# Process opencode config files (jsonc + json)
# ─────────────────────────────────────────────
function Update-ConfigFile {
    param(
        [string]$FilePath,
        [string]$ProviderName,
        [hashtable]$AgentModels
    )

    if (-not (Test-Path $FilePath)) {
        Write-Warning "File not found: $FilePath"
        return
    }

    $content = Get-Content $FilePath
    $output = @()
    $inOpenRouterBlock = $false
    $orDepth = 0
    $inDisabledProviders = $false
    $inEnabledProviders = $false
    $currentAgent = ""

    for ($i = 0; $i -lt $content.Count; $i++) {
        $line = $content[$i]
        $trimmed = $line.Trim()

        # Track which agent block we're in
        if ($line -match '^\s+"(\w[\w-]*)":\s*\{') {
            $candidate = $Matches[1]
            # Only track agent blocks (not provider/options/models/whitelist blocks)
            if ($candidate -notin @("provider","options","models","whitelist","gemini","kilo","opencode","groq","mistral","openrouter","deepseek","lmstudio")) {
                $currentAgent = $candidate
            }
        }

        # ── Top-level model settings (commented or uncommented) ──
        $isModelLine    = $trimmed -match '^\s*"model":\s*"'
        $isSmallModel   = $trimmed -match '^\s*"small_model":\s*"'
        $isModelComment = $trimmed -match '^\s*//\s*"model":\s*"'
        $isSmallComment = $trimmed -match '^\s*//\s*"small_model":\s*"'

        if ($isModelLine -or $isModelComment) {
            $indent = Get-Indent $line
            $modelValue = switch ($ProviderName) {
                "kilo"      { "kilo/kilo-auto/free" }
                "opencode"  { "opencode/mimo-v2.5-free" }
                "openrouter"{ "openrouter/google/gemma-4-26b-a4b-it:free" }
            }
            $output += $indent + '"model": "' + $modelValue + '",'
            continue
        }
        if ($isSmallModel -or $isSmallComment) {
            $indent = Get-Indent $line
            $modelValue = switch ($ProviderName) {
                "kilo"      { "kilo/kilo-auto/free" }
                "opencode"  { "opencode/mimo-v2.5-free" }
                "openrouter"{ "openrouter/google/gemma-4-26b-a4b-it:free" }
            }
            $output += $indent + '"small_model": "' + $modelValue + '",'
            continue
        }

        # ── enabled_providers: add/remove openrouter ──
        if ($trimmed -match '^\s*"enabled_providers"') { $inEnabledProviders = $true }
        if ($inEnabledProviders -and $trimmed -match '^\s*\]') { $inEnabledProviders = $false }
        if ($inEnabledProviders) {
            # Comment out openrouter if not the selected provider
            if ($trimmed -match '^\s*"openrouter"' -and $trimmed -notmatch '^\s*//') {
                if ($ProviderName -ne "openrouter") {
                    $output += (Get-Indent $line) + '// ' + $trimmed
                    continue
                }
            }
            # Uncomment openrouter if it IS the selected provider
            if ($trimmed -match '^\s*//\s*"openrouter"') {
                if ($ProviderName -eq "openrouter") {
                    $output += $line -replace '^(\s*)\s*//\s*', '$1'
                    continue
                }
            }
        }

        # ── disabled_providers: add/remove openrouter ──
        if ($trimmed -match '^\s*"disabled_providers"') { $inDisabledProviders = $true }
        if ($inDisabledProviders -and $trimmed -match '^\s*\]') { $inDisabledProviders = $false }
        if ($inDisabledProviders) {
            if ($ProviderName -ne "openrouter") {
                # Add openrouter after groq if not already present
                if ($trimmed -match '^\s*"groq"\s*,?\s*$') {
                    $hasOR = $false
                    for ($j = $i + 1; $j -lt $content.Count; $j++) {
                        $t = $content[$j].Trim()
                        if ($t -match '"openrouter"') { $hasOR = $true; break }
                        if ($t -match '^\s*\]') { break }
                    }
                    if (-not $hasOR) {
                        # Ensure a comma after the preceding entry before inserting openrouter
                        if ($line -notmatch ',\s*$') {
                            $output += $line + ','
                        } else {
                            $output += $line
                        }
                        $indent = Get-Indent $line
                        $output += $indent + '"openrouter"'
                        continue
                    }
                }
            } else {
                # Remove openrouter from disabled_providers
                if ($trimmed -match '^\s*"openrouter"\s*,?\s*$') {
                    continue
                }
            }
        }

        # ── OpenRouter provider block: comment/uncomment ──
        $isORBlockComment = $trimmed -match '^//\s*"openrouter":\s*\{'
        $isORBlock        = $trimmed -match '^"openrouter":\s*\{'

        if ($isORBlockComment -or $isORBlock) {
            $inOpenRouterBlock = $true
            $orDepth = 1
            if ($ProviderName -ne "openrouter") {
                # Comment out if not already commented
                if ($isORBlock) {
                    $output += (Get-Indent $line) + '// ' + $trimmed
                } else {
                    $output += $line
                }
                continue
            } else {
                # Uncomment if commented — use 4-space indent to match other providers
                if ($isORBlockComment) {
                    $content_after = $line -replace '^\s*//\s*', ''
                    $output += '    ' + $content_after
                } else {
                    $output += $line
                }
                continue
            }
        }
        if ($inOpenRouterBlock) {
            $orDepth += ([regex]::Matches($line, '\{')).Count
            $orDepth -= ([regex]::Matches($line, '\}')).Count
            if ($ProviderName -ne "openrouter") {
                if ($line -match '^\s*//') {
                    $output += $line
                } else {
                    $output += (Get-Indent $line) + '// ' + $trimmed
                }
            } else {
                if ($line -match '^\s*//') {
                    $content_after = $line -replace '^\s*//\s*', ''
                    # Preserve relative indent: add 6 spaces for block contents
                    $output += '      ' + $content_after
                } else {
                    $output += $line
                }
            }
            if ($orDepth -le 0) { $inOpenRouterBlock = $false }
            continue
        }

        # ── Agent model settings ──
        $isAgentModel        = $trimmed -match '^\s*"model":\s*"' -and $currentAgent -and $AgentModels.ContainsKey($currentAgent)
        $isAgentModelComment = $trimmed -match '^\s*//\s*"model":\s*"' -and $currentAgent -and $AgentModels.ContainsKey($currentAgent)

        if ($isAgentModel -or $isAgentModelComment) {
            $newModel = $AgentModels[$currentAgent]
            $indent = Get-Indent $line
            $output += $indent + '"model": "' + $newModel + '",'
            continue
        }

        $output += $line
    }

    $output | Set-Content $FilePath
    Write-Host "  Updated: $(Split-Path $FilePath -Leaf)"
}

# ─────────────────────────────────────────────
# Process model-fallback.json
# ─────────────────────────────────────────────
function Update-FallbackFile {
    param(
        [string]$FilePath,
        [string]$ProviderName,
        [array]$FallbackChain
    )

    if (-not (Test-Path $FilePath)) {
        Write-Warning "File not found: $FilePath"
        return
    }

    $lines = Get-Content $FilePath
    $output = @()
    $inFallbackModels = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $trimmed = $line.Trim()

        if ($trimmed -match '"fallbackModels":\s*\[') {
            $inFallbackModels = $true
            $output += $line
            $indent = Get-Indent $line
            for ($j = 0; $j -lt $FallbackChain.Count; $j++) {
                $entry = $FallbackChain[$j]
                $comma = if ($j -lt $FallbackChain.Count - 1) { "," } else { "" }
                $output += $indent + '  "' + $entry + '"' + $comma
            }
            continue
        }

        if ($inFallbackModels) {
            if ($trimmed -match '^\s*\]') {
                $inFallbackModels = $false
                $output += $line
            }
            continue
        }

        $output += $line
    }

    $output | Set-Content $FilePath
    Write-Host "  Updated: $(Split-Path $FilePath -Leaf)"
}

# ─────────────────────────────────────────────
# Execute
# ─────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Switching to: $($Provider.ToUpper())" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Updating config files..." -ForegroundColor Green
Update-ConfigFile -FilePath $jsoncPath -ProviderName $Provider -AgentModels $agentModels[$Provider]
Update-ConfigFile -FilePath $jsonPath  -ProviderName $Provider -AgentModels $agentModels[$Provider]

Write-Host ""
Write-Host "[2/3] Updating fallback chains..." -ForegroundColor Green
Update-FallbackFile -FilePath $fbPath -ProviderName $Provider -FallbackChain $fallbackChains[$Provider]

Write-Host ""
Write-Host "[3/3] Verifying..." -ForegroundColor Green
$jsoncContent = Get-Content $jsoncPath
$orRefs = ($jsoncContent | Where-Object { $_ -match '"openrouter' -and $_ -notmatch '^\s*//' }).Count
$kiloRefs = ($jsoncContent | Where-Object { $_ -match '"kilo/' -and $_ -notmatch '^\s*//' }).Count
$ocRefs = ($jsoncContent | Where-Object { $_ -match '"opencode/' -and $_ -notmatch '^\s*//' }).Count

Write-Host "  OpenRouter active refs: $orRefs"
Write-Host "  Kilo active refs: $kiloRefs"
Write-Host "  OpenCode active refs: $ocRefs"

$primaryLine = $jsoncContent | Where-Object { $_ -match '^\s*"model":\s*"' } | Select-Object -First 1
if ($primaryLine) {
    $primaryModel = $primaryLine -replace '.*"model":\s*"([^"]+)".*', '$1'
    Write-Host "  Primary model: $primaryModel" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  Done! Restart OpenCode to apply." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
