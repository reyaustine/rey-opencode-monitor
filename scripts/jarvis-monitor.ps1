#Requires -Version 5.1
<#
.SYNOPSIS
  J.A.R.V.I.S.-style background monitor for the free-only OpenCode model fleet.
  Multi-thread aware with a dedicated SUB-AGENTS pane: every tracked thread
  gets its own titled row (id | workspace | agent | model | task | state).
  Press Q to quit. Safe: runs read-only checks (no model inference calls).
  Global scope: monitors ~/.config/opencode, tracks OpenCode IDE and all workspaces.
#>
param()

$ErrorActionPreference = 'Continue'
$TICK_MS       = 200
$REFRESH_EVERY = 15   # ticks between status refreshes (~3s for fast live updates)
$MAX_THREADS   = 7    # threads displayed in sub-agents pane

$spin  = @('|', '/', '-', '\')
$state = @{
  Tick         = 0
  IdeStatus    = 'CHECKING...'
  IdeColor     = 'DarkGray'
  Workspace    = '-'
  DefaultModel = 'unknown'
  SmallModel   = 'unknown'
  Providers    = 'unknown'
  ModelCount   = 'unknown'
  Version      = 'unknown'
  ThreadCount  = 0
  Activity     = 'IDLE'
  Health       = 'STARTING'
  TokensTotal  = '0'
  TokensPrompt = '0'
  TokensComp   = '0'
  TokensCache  = '0'
  TokensCost   = '$0.00'
  TokenModels  = @()
  ViewMode     = 'FLEET'
  LastRefresh  = 'never'
}

$script:threadCache = @{}  # id -> session object
$script:wasWorking  = $false
$script:lastW       = 0
$script:lastH       = 0
$logs = New-Object System.Collections.Generic.List[string]

function Add-Log([string]$msg) {
  $logs.Add(('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $msg))
  while ($logs.Count -gt 6) { $logs.RemoveAt(0) }
}

function Shorten([string]$text, [int]$max) {
  if ([string]::IsNullOrEmpty($text)) { return '-' }
  $text = $text.Trim()
  if ($max -le 3) {
    if ($text.Length -gt $max) { return $text.Substring(0, $max) }
    return $text
  }
  if ($text.Length -gt $max) {
    return $text.Substring(0, $max - 2) + '..'
  }
  return $text
}

function Safe-Sub([string]$text, [int]$start, [int]$len) {
  if ([string]::IsNullOrEmpty($text)) { return '' }
  if ($start -ge $text.Length) { return '' }
  $avail = $text.Length - $start
  $take = [Math]::Min($avail, $len)
  return $text.Substring($start, $take)
}

function Refresh-Status {
  $ok = $true

  # 1. Detect OpenCode Desktop IDE Process
  try {
    $ideProc = Get-Process -Name 'OpenCode' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ideProc) {
      $state.IdeStatus = "ONLINE (PID $($ideProc.Id))"
      $state.IdeColor  = 'Green'
    } else {
      $state.IdeStatus = "OFFLINE"
      $state.IdeColor  = 'DarkGray'
    }
  } catch {
    $state.IdeStatus = "UNKNOWN"
    $state.IdeColor  = 'Yellow'
  }

  # 2. Read Global Config fast directly from JSON / JSONC (<5ms)
  try {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
    $confDir = Split-Path -Parent $scriptDir
    $cfgJson = Join-Path $confDir 'opencode.json'
    $cfgJsonc = Join-Path $confDir 'opencode.jsonc'

    if (Test-Path -LiteralPath $cfgJson) {
      $cfg = Get-Content -LiteralPath $cfgJson -Raw | ConvertFrom-Json
      if ($cfg.model) { $state.DefaultModel = [string]$cfg.model }
      if ($cfg.small_model) { $state.SmallModel = [string]$cfg.small_model }
    }

    if (Test-Path -LiteralPath $cfgJsonc) {
      $jsoncRaw = Get-Content -LiteralPath $cfgJsonc -Raw
      # Strip single-line comments for JSON parsing
      $cleanJson = $jsoncRaw -replace '(?m)^\s*//.*$', ''
      $cfgc = $cleanJson | ConvertFrom-Json
      if ($cfgc.enabled_providers) {
        $state.Providers = ($cfgc.enabled_providers -join ', ')
      }
      # Calculate total visible allowlisted models
      $mCount = 0
      if ($cfgc.provider) {
        foreach ($prop in $cfgc.provider.psobject.properties) {
          if ($prop.Value.whitelist) {
            $mCount += @($prop.Value.whitelist).Count
          }
          if ($prop.Value.models) {
            $mCount += @($prop.Value.models.psobject.properties).Count
          }
        }
      }
      if ($mCount -gt 0) {
        $state.ModelCount = "$mCount allowlisted"
      }
    }
  } catch {
    $ok = $false
    Add-Log ('config parse FAILED: ' + (Shorten $_.Exception.Message 40))
  }

  # 3. Get OpenCode version (fast safe package.json read, avoiding opencode.ps1 exit trap)
  if ($state.Version -eq 'unknown') {
    try {
      $pkgPath = Join-Path $env:APPDATA 'npm\node_modules\opencode-ai\package.json'
      if (Test-Path -LiteralPath $pkgPath) {
        $pkg = Get-Content -LiteralPath $pkgPath -Raw | ConvertFrom-Json
        if ($pkg.version) { $state.Version = [string]$pkg.version }
        else { $state.Version = 'opencode' }
      } else {
        $state.Version = 'opencode'
      }
    } catch {
      $state.Version = 'opencode'
    }
  }

  # 4. Read Live Session and Sub-agent Telemetry from opencode.db via python helper (<50ms)
  try {
    $pyScript = Join-Path $scriptDir 'jarvis-state.py'
    if (Test-Path -LiteralPath $pyScript) {
      $pyOut = & python "$pyScript" 2>$null
      if ($pyOut) {
        $dbData = $pyOut | ConvertFrom-Json
        if ($dbData.ok) {
          $state.ThreadCount = [int]$dbData.active_threads
          $state.Workspace   = [string]$dbData.current_workspace

          $sessions = @($dbData.sessions)
          $liveIds = @($sessions | ForEach-Object { $_.id })

          # Prune dead threads from cache
          foreach ($key in @($script:threadCache.Keys)) {
            if ($liveIds -notcontains $key) {
              $script:threadCache.Remove($key)
            }
          }

          # Update cache & log transitions
          foreach ($s in $sessions) {
            $sid = [string]$s.id
            $prev = $script:threadCache[$sid]
            $prevState = if ($prev) { $prev.state } else { '' }
            $currState = [string]$s.state

            $shortId = Safe-Sub $sid 0 12
            if (($currState -eq 'WORKING') -and ($prevState -ne 'WORKING')) {
              Add-Log ('thread ' + $shortId + ' THINKING: ' + (Shorten $s.title 35))
            }
            if (($currState -eq 'DONE') -and ($prevState -eq 'WORKING')) {
              Add-Log ('thread ' + $shortId + ' DONE cost=' + $s.cost)
            }

            $script:threadCache[$sid] = $s
          }

          # Update token metrics
          if ($dbData.tokens) {
            $gt = $dbData.tokens.grand_total
            if ($gt) {
              $state.TokensTotal  = [string]$gt.total_fmt
              $state.TokensPrompt = [string]$gt.prompt_fmt
              $state.TokensComp   = [string]$gt.completion_fmt
              $state.TokensCache  = [string]$gt.cache_read_fmt
              $costVal = [double]($gt.cost)
              $state.TokensCost   = ('${0:N4}' -f $costVal)
            }
            if ($dbData.tokens.models) {
              $state.TokenModels = @($dbData.tokens.models)
            }
          }
        } else {
          $ok = $false
          Add-Log ('db query err: ' + (Shorten $dbData.error 35))
        }
      }
    }
  } catch {
    $ok = $false
    Add-Log ('session sync FAILED: ' + (Shorten $_.Exception.Message 40))
  }

  $working = ($state.ThreadCount -gt 0)
  if ($working -and -not $script:wasWorking) { Add-Log 'fleet thinking...' }
  if ((-not $working) -and $script:wasWorking) { Add-Log 'fleet idle - all done' }
  $script:wasWorking = $working

  if ($working) {
    $state.Activity = 'THINKING'
  } elseif ($state.IdeStatus -like 'ONLINE*') {
    $state.Activity = 'IDLE (STANDBY)'
  } else {
    $state.Activity = 'IDLE'
  }

  if ($ok) {
    $state.Health = 'ALL SYSTEMS NOMINAL'
  } else {
    $state.Health = 'DEGRADED - CHECK LOG'
  }
  $state.LastRefresh = (Get-Date -Format 'HH:mm:ss')
}

function Get-ConsoleSize {
  $w = 80
  $h = 30
  try {
    if ($Host.UI.RawUI.WindowSize) {
      $w = $Host.UI.RawUI.WindowSize.Width
      $h = $Host.UI.RawUI.WindowSize.Height
    }
  } catch {
    try {
      $w = [Console]::WindowWidth
      $h = [Console]::WindowHeight
    } catch { }
  }
  return @{ Width = [Math]::Max(20, $w); Height = [Math]::Max(10, $h) }
}

function Write-Row([int]$row, [string]$text, [string]$color) {
  try {
    $dims = Get-ConsoleSize
    $winWidth  = $dims.Width
    $winHeight = $dims.Height

    # Prevent out of bounds cursor placement that causes crashes during resize
    if ($row -lt 0 -or $row -ge $winHeight) { return }

    # Leave 1 column margin so the console never auto-wraps and scrolls
    $maxLen = [Math]::Max(10, $winWidth - 1)
    if ($text.Length -gt $maxLen) {
      $text = $text.Substring(0, $maxLen)
    } else {
      $text = $text.PadRight($maxLen)
    }

    try {
      $pos = New-Object System.Management.Automation.Host.Coordinates(0, $row)
      $Host.UI.RawUI.CursorPosition = $pos
    } catch {
      try {
        [Console]::SetCursorPosition(0, $row)
      } catch { }
    }
    Write-Host $text -NoNewline -ForegroundColor $color
  } catch {
    # Swallow transient resize coordinate exceptions
  }
}

function Draw([int]$frame, [bool]$working) {
  try {
    # Detect console window resize and clear stale characters
    $dims = Get-ConsoleSize
    $curW = $dims.Width
    $curH = $dims.Height

    if ($curW -ne $script:lastW -or $curH -ne $script:lastH) {
      $script:lastW = $curW
      $script:lastH = $curH
      try { [Console]::Clear() } catch { try { Clear-Host } catch { } }
    }

    $s = $spin[$frame % 4]
    $amp = if ($working) { 10 } else { 8 }
    $level = [int](10 + $amp * [Math]::Sin($frame / 4.0))
    $level = [Math]::Max(0, [Math]::Min(20, $level))
    $bar = ('#' * $level).PadRight(20, '.')

    $healthColor = if ($state.Health -eq 'ALL SYSTEMS NOMINAL') { 'Green' } else { 'Red' }
    $actColor    = if ($working) { 'Yellow' } else { 'Green' }
    $tag         = if ($working) { '[ THINKING ]' } else { '[ STANDBY ]' }
    $headColor   = if ($working) { 'Yellow' } else { 'Cyan' }

    Write-Row 0  '  ==============================================================' $headColor
    Write-Row 1  ("   J.A.R.V.I.S.  //  MODEL FLEET MONITOR  $tag [ $s ] [$bar]") $headColor
    Write-Row 2  '  ==============================================================' $headColor
    Write-Row 3  ("   opencode IDE  : " + $state.IdeStatus) $state.IdeColor
    Write-Row 4  ("   workspace     : " + $state.Workspace) 'White'
    Write-Row 5  ("   default model : " + $state.DefaultModel) 'White'
    Write-Row 6  ("   small model   : " + $state.SmallModel) 'White'
    Write-Row 7  ("   providers     : " + $state.Providers) 'White'
    Write-Row 8  ("   models visible: " + $state.ModelCount) 'White'
    Write-Row 9  ("   opencode      : " + $state.Version) 'White'
    Write-Row 10 ("   active threads: " + $state.ThreadCount) 'Magenta'
    Write-Row 11 ("   activity      : " + $state.Activity) $actColor
    Write-Row 12 ("   status        : " + $state.Health) $healthColor
    Write-Row 13 ("   tokens used   : {0}  (prompt: {1} | compl: {2} | cache: {3})  [{4}]" -f $state.TokensTotal, $state.TokensPrompt, $state.TokensComp, $state.TokensCache, $state.TokensCost) 'Cyan'
    Write-Row 14 ("   last refresh  : " + $state.LastRefresh + '   (Q: quit | T: toggle model tokens)') 'DarkGray'

    if ($state.ViewMode -eq 'TOKENS') {
      # --- VIEW MODE: PER-MODEL TOKEN FLEET BREAKDOWN ---
      Write-Row 15 '  --------------------------------------------------------------' 'DarkCyan'
      Write-Row 16 ("  TOKEN FLEET BREAKDOWN (TOTAL: {0} | COST: {1})  [PRESS T FOR LOGS/FLEET]" -f $state.TokensTotal, $state.TokensCost) 'Cyan'
      Write-Row 17 '  PROVIDER     | MODEL                               | PROMPT    | COMPL    | TOTAL     | CALLS' 'Yellow'
      Write-Row 18 '  --------------------------------------------------------------------------------------------' 'DarkGray'

      $maxTokenRows = [Math]::Max(3, $curH - 21)
      for ($i = 0; $i -lt $maxTokenRows; $i++) {
        $rowNum = 19 + $i
        if ($i -lt $state.TokenModels.Count) {
          $m = $state.TokenModels[$i]
          $p = Shorten $m.provider 12
          $mod = Shorten $m.model 35
          $p_fmt = [string]$m.prompt_fmt
          $c_fmt = [string]$m.completion_fmt
          $t_fmt = [string]$m.total_fmt
          $calls = [string]$m.calls

          $line = ('  {0,-12} | {1,-35} | {2,-9} | {3,-8} | {4,-9} | {5,-5}' -f $p, $mod, $p_fmt, $c_fmt, $t_fmt, $calls)
          $color = if ($m.provider -eq 'openrouter') { 'Magenta' } elseif ($m.provider -eq 'kilo') { 'Green' } else { 'White' }
          Write-Row $rowNum $line $color
        } else {
          Write-Row $rowNum '' 'DarkGray'
        }
      }
      Write-Row (19 + $maxTokenRows) '  --------------------------------------------------------------' 'DarkCyan'
    } else {
      # --- VIEW MODE: FLEET THREADS & LIVE LOG ---
      $logStartRow = 15
      if ($curH -ge 38) {
        Write-Row 15 '  --------------------------------------------------------------' 'DarkCyan'
        Write-Row 16 '  TOP MODEL TOKENS  [PRESS T FOR FULL BREAKDOWN]' 'Cyan'
        for ($j = 0; $j -lt [Math]::Min(3, $state.TokenModels.Count); $j++) {
          $tm = $state.TokenModels[$j]
          $tLine = ('   {0,-10} {1,-30} total:{2,-8} (prompt:{3}, comp:{4})' -f $tm.provider, (Shorten $tm.model 30), $tm.total_fmt, $tm.prompt_fmt, $tm.completion_fmt)
          Write-Row (17 + $j) $tLine 'DarkGray'
        }
        $logStartRow = 20
      }

      Write-Row $logStartRow '  --------------------------------------------------------------' 'DarkCyan'
      Write-Row ($logStartRow + 1) '  LIVE LOG' 'Yellow'

      # Adaptive log lines based on terminal height
      $maxLogLines = 5
      if ($curH -lt ($logStartRow + 14)) { $maxLogLines = [Math]::Max(1, $curH - ($logStartRow + 10)) }
      for ($i = 0; $i -lt $maxLogLines; $i++) {
        $line = ''
        if ($i -lt $logs.Count) { $line = '  ' + $logs[$i] }
        Write-Row ($logStartRow + 2 + $i) $line 'Gray'
      }

      $subHeaderRow = $logStartRow + 2 + $maxLogLines
      Write-Row $subHeaderRow '  --------------------------------------------------------------' 'DarkCyan'
      Write-Row ($subHeaderRow + 1) '  SUB-AGENTS (ID | WORKSPACE | AGENT | MODEL | TASK | STATE)' 'Yellow'

      # Order sessions: WORKING first, then by recency
      $ordered = @($script:threadCache.Values | Sort-Object {
        if ($_.state -eq 'WORKING') { 0 } else { 1 }
      })

      $maxSubRows = $MAX_THREADS
      if ($curH -lt ($subHeaderRow + 10)) {
        $maxSubRows = [Math]::Max(1, $curH - ($subHeaderRow + 3))
      }

      for ($i = 0; $i -lt $maxSubRows; $i++) {
        $line = ''
        $color = 'DarkGray'
        if ($i -lt $ordered.Count) {
          $t = $ordered[$i]
          $sid   = Safe-Sub $t.id 0 12
          $ws    = Shorten $t.workspace 12
          $ag    = Shorten $t.agent 7
          $mod   = Shorten $t.model 22
          $task  = Shorten $t.title 24
          $st    = [string]$t.state

          $line = ('  {0,-12} | {1,-12} | {2,-7} | {3,-22} | {4,-24} [{5}]' -f $sid, $ws, $ag, $mod, $task, $st)
          $color = if ($st -eq 'WORKING') { 'Yellow' } else { 'Gray' }
        }
        Write-Row ($subHeaderRow + 2 + $i) $line $color
      }

      Write-Row ($subHeaderRow + 2 + $maxSubRows) '  --------------------------------------------------------------' 'DarkCyan'
    }
  } catch {
    # Ignore any redraw exceptions during dynamic screen resize
  }
}

# --- Initialization ---
try {
  $Host.UI.RawUI.WindowTitle = 'JARVIS // Model Fleet Monitor'
} catch { }

try {
  $size = $Host.UI.RawUI.WindowSize
  if ($size.Width -lt 80) { $size.Width = 80 }
  if ($size.Height -lt 30) { $size.Height = 30 }
  $Host.UI.RawUI.WindowSize = $size
} catch { }

try {
  [Console]::CursorVisible = $false
} catch { }

try {
  Add-Log 'JARVIS monitor initialized (real-time telemetry)'
  Refresh-Status

  $frame = 0
  while ($true) {
    if (-not [Console]::IsInputRedirected) {
      try {
        if ([Console]::KeyAvailable) {
          $key = [Console]::ReadKey($true)
          if ($key.Key -eq 'Q') { break }
          if ($key.Key -eq 'T') {
            if ($state.ViewMode -eq 'TOKENS') {
              $state.ViewMode = 'FLEET'
            } else {
              $state.ViewMode = 'TOKENS'
            }
            try { [Console]::Clear() } catch { try { Clear-Host } catch { } }
          }
        }
      } catch { }
    }

    if (($frame % $REFRESH_EVERY) -eq 0 -and $frame -ne 0) {
      Refresh-Status
    }

    Draw $frame $script:wasWorking

    if ($script:wasWorking) { $frame += 2 } else { $frame++ }
    Start-Sleep -Milliseconds $TICK_MS
  }
} finally {
  try { [Console]::CursorVisible = $true } catch { }
  Write-Host ''
  Write-Host '  Monitor stopped. Stay free, stay nominal.' -ForegroundColor Cyan
}
