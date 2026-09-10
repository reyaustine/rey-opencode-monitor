#Requires -Version 5.1
<#
.SYNOPSIS
  R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI
  Multi-thread aware with a dedicated SUB-AGENTS pane and per-model TOKEN USAGE tracker.
  Press Q to quit. Press T to toggle Token Fleet view.
  Global scope: monitors ~/.config/opencode, tracks OpenCode IDE and all workspaces.
#>
param()

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

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

$script:threadCache     = @{}  # id -> session object
$script:wasWorking      = $false
$script:workingStart    = $null
$script:punchActive     = $false
$script:punchTick       = 0
$script:lastPunchFrame  = -999
$script:lastW           = 0
$script:lastH           = 0
$script:lastHealthCheck = [DateTime]::Now
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
    $pyScript = Join-Path $scriptDir 'rey-state.py'
    if (-not (Test-Path -LiteralPath $pyScript)) {
      $pyScript = Join-Path $scriptDir 'jarvis-state.py'
    }
    if (Test-Path -LiteralPath $pyScript) {
      $pyOut = & python "$pyScript" 2>$null
      if ($pyOut) {
        $dbData = $pyOut | ConvertFrom-Json
        if ($dbData.ok) {
          $state.ThreadCount = [int]$dbData.active_threads
          $state.Workspace   = [string]$dbData.current_workspace
          if ($dbData.rotation -and $dbData.rotation.active) {
            $state.DefaultModel = "$($dbData.rotation.summary) [ROTATING]"
          } elseif ($dbData.override_model) {
            $state.DefaultModel = "$($dbData.override_model) [LOCKED]"
          }
          if ($dbData.rotation_event) {
            Add-Log ("[ROTATE] " + $dbData.rotation_event)
          }

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
            if ($sid -eq 'ses_watchdog') {
              if (($currState -eq 'WORKING') -and ($prevState -ne 'WORKING')) {
                Add-Log '[HEALTH] fleet check started'
              }
              if (($currState -eq 'DONE') -and ($prevState -eq 'WORKING')) {
                Add-Log ('[HEALTH] ' + (Shorten $s.title 40))
              }
            } else {
              if (($currState -eq 'WORKING') -and ($prevState -ne 'WORKING')) {
                Add-Log ('thread ' + $shortId + ' THINKING: ' + (Shorten $s.title 35))
              }
              if (($currState -eq 'DONE') -and ($prevState -eq 'WORKING')) {
                Add-Log ('thread ' + $shortId + ' DONE cost=' + $s.cost)
              }
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
  if ($working -and -not $script:wasWorking) {
    Add-Log 'fleet thinking...'
    $script:workingStart = Get-Date
    $script:punchActive  = $false
    $script:punchTick    = 0
  }
  if ((-not $working) -and $script:wasWorking) {
    Add-Log 'fleet idle - all done'
    $script:workingStart = $null
    $script:punchActive  = $false
    $script:punchTick    = 0
  }
  if ($working -and -not $script:workingStart) {
    $script:workingStart = Get-Date
  }
  $script:wasWorking = $working

  if ($working) {
    if ($script:workingStart) {
      $mins = [int](([DateTime]::Now - $script:workingStart).TotalMinutes)
      if ($mins -gt 0) {
        $state.Activity = ("THINKING ({0}m elapsed)" -f $mins)
      } else {
        $state.Activity = 'THINKING'
      }
    } else {
      $state.Activity = 'THINKING'
    }
  } elseif ($state.IdeStatus -like 'ONLINE*') {
    $state.Activity = 'IDLE (STANDBY)'
  } else {
    $state.Activity = 'IDLE'
  }

  if ($ok) {
    if ($dbData -and $dbData.model_health) {
      $mh = $dbData.model_health
      if ($mh.running) {
        $state.Health = 'CHECKING FLEET HEALTH...'
      } elseif ($mh.unresponsive_count -gt 0) {
        $state.Health = "DEGRADED ($($mh.unresponsive_count) UNRESPONSIVE)"
      } elseif ($mh.new_models_count -gt 0) {
        $state.Health = "NOMINAL (+$($mh.new_models_count) NEW FREE)"
      } else {
        $state.Health = 'ALL SYSTEMS NOMINAL'
      }
    } else {
      $state.Health = 'ALL SYSTEMS NOMINAL'
    }
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

function Get-RobotLine([int]$lineIndex, [int]$frame, [bool]$working, [string]$taskTitle, [bool]$healthOk, [bool]$punchActive, [int]$punchTick) {
  $spinners = @('|', '/', '-', '\')
  $mouths   = @('▄  ', ' ▄ ', '  ▄', ' ▄ ')

  # 1. Frustration Punch Sequence (when task running 10-20+ mins or triggered)
  if ($working -and $punchActive) {
    if ($punchTick -lt 5) {
      # Phase 1: Winding up furious
      switch ($lineIndex) {
        0  { return @{ Pre = "┌── "; Mid = "R.E.Y. BOT"; MidColor = 'Red'; Sep = " ─ ["; Text = ("{0,-7}" -f 'ANGRY!'); TextColor = 'Red'; Post = "]─┐" } }
        1  { return @{ Pre = "│         ╭───╮            │"; Mid = ""; Post = "" } }
        2  { return @{ Pre = "│         │ "; Mid = "♨"; MidColor = 'Red'; Post = " │            │" } }
        3  { return @{ Pre = "│       ╭─┴───┴─╮          │"; Mid = ""; Post = "" } }
        4  { return @{ Pre = "│      ╱  *GRRR* ╲         │"; Mid = ""; Post = "" } }
        5  { return @{ Pre = "│     │   "; Mid = "╲   ╱"; MidColor = 'Red'; Post = "   │        │" } }
        6  { return @{ Pre = "│     │   "; Mid = "ಠ   ಠ"; MidColor = 'Red'; Post = "   │        │" } }
        7  { return @{ Pre = "│     │           │        │"; Mid = ""; Post = "" } }
        8  { return @{ Pre = "│     │    "; Mid = "▃▃▃"; MidColor = 'Red'; Post = "    │        │" } }
        9  { return @{ Pre = "│      ╲  *FIST* ╱         │"; Mid = ""; Post = "" } }
        10 { return @{ Pre = "│       ╰───────╯          │"; Mid = ""; Post = "" } }
        11 { return @{ Pre = "└─ "; Mid = ">10m! So frustrated!! "; MidColor = 'White'; Post = " ─┘" } }
      }
    } elseif ($punchTick -lt 15) {
      # Phase 2: THE SCREEN PUNCH!
      switch ($lineIndex) {
        0  { return @{ Pre = "┌── "; Mid = "R.E.Y. BOT"; MidColor = 'Red'; Sep = " ─ ["; Text = ("{0,-7}" -f 'PUNCH!'); TextColor = 'Red'; Post = "]─┐" } }
        1  { return @{ Pre = "│         ╭───╮            │"; Mid = ""; Post = "" } }
        2  { return @{ Pre = "│         │ "; Mid = "♨"; MidColor = 'Red'; Post = " │            │" } }
        3  { return @{ Pre = "│       ╭─┴───┴─╮          │"; Mid = ""; Post = "" } }
        4  { return @{ Pre = "│      ╱ *POW!!* ╲         │"; Mid = ""; Post = "" } }
        5  { return @{ Pre = "│     │   "; Mid = "╲   ╱"; MidColor = 'Red'; Post = "   │        │" } }
        6  { return @{ Pre = "│     │  "; Mid = "[==👊==]"; MidColor = 'Red'; Post = " │        │" } }
        7  { return @{ Pre = "│     │   "; Mid = "*BAM!*"; MidColor = 'Red'; Post = "  │        │" } }
        8  { return @{ Pre = "│     │    "; Mid = "▃▃▃"; MidColor = 'Red'; Post = "    │        │" } }
        9  { return @{ Pre = "│      ╲         ╱         │"; Mid = ""; Post = "" } }
        10 { return @{ Pre = "│       ╰───────╯          │"; Mid = ""; Post = "" } }
        11 { return @{ Pre = "└─ "; Mid = "*POW!* FINISH TASK!   "; MidColor = 'White'; Post = " ─┘" } }
      }
    } else {
      # Phase 3: Cooldown / Panting
      switch ($lineIndex) {
        0  { return @{ Pre = "┌── "; Mid = "R.E.Y. BOT"; MidColor = 'Yellow'; Sep = " ─ ["; Text = ("{0,-7}" -f 'EXHAUST'); TextColor = 'Yellow'; Post = "]─┐" } }
        1  { return @{ Pre = "│         ╭───╮            │"; Mid = ""; Post = "" } }
        2  { return @{ Pre = "│         │ "; Mid = "~"; MidColor = 'Yellow'; Post = " │            │" } }
        3  { return @{ Pre = "│       ╭─┴───┴─╮          │"; Mid = ""; Post = "" } }
        4  { return @{ Pre = "│      ╱         ╲         │"; Mid = ""; Post = "" } }
        5  { return @{ Pre = "│     │   "; Mid = "╱   ╲"; MidColor = 'Yellow'; Post = "   │        │" } }
        6  { return @{ Pre = "│     │   "; Mid = "•   •"; MidColor = 'Yellow'; Post = "   │        │" } }
        7  { return @{ Pre = "│     │           │        │"; Mid = ""; Post = "" } }
        8  { return @{ Pre = "│     │    "; Mid = $mouths[$frame % 4]; MidColor = 'Yellow'; Post = "    │        │" } }
        9  { return @{ Pre = "│      ╲         ╱         │"; Mid = ""; Post = "" } }
        10 { return @{ Pre = "│       ╰───────╯          │"; Mid = ""; Post = "" } }
        11 { return @{ Pre = "└─ "; Mid = "Phew... hurry it up!  "; MidColor = 'White'; Post = " ─┘" } }
      }
    }
  }

  # 2. Standard Task & Idle Expression Logic
  $ant = '|'; $lb = '─'; $rb = '─'; $le = '◉'; $re = '◉'; $mth = '───'
  $glow = 'Yellow'; $mood = 'STANDBY'; $status = 'Standing by...'

  if (-not $healthOk) {
    $ant = '☡'; $lb = '╲'; $rb = '╱'; $le = '✖'; $re = '✖'; $mth = '▃▃▃'
    $glow = 'Red'; $mood = 'ALERT'; $status = 'Check error log!'
  } elseif ($working) {
    $tLow = ($taskTitle + '').ToLower()
    if ($tLow -match 'fix|bug|issue|error') {
      $ant = '⚡'; $lb = '╲'; $rb = '╱'; $le = '•'; $re = '•'; $mth = '╰━╯'
      $glow = 'Yellow'; $mood = 'DEBUG'; $status = 'Fixing issue...'
    } elseif ($tLow -match 'test|verify|qa|check') {
      $ant = '⚇'; $lb = '─'; $rb = '─'; $le = '◎'; $re = '◎'; $mth = $mouths[$frame % 4]
      $glow = 'Cyan'; $mood = 'TESTING'; $status = 'Verifying...'
    } elseif ($tLow -match 'build|code|refactor') {
      $ant = '⚙'; $lb = '─'; $rb = '─'; $le = '['; $re = ']'; $mth = '━━━'
      $glow = 'Green'; $mood = 'CODING'; $status = 'Synthesizing...'
    } elseif ($tLow -match 'review|architect|research') {
      $ant = '⌖'; $lb = '╭'; $rb = '─'; $le = '◉'; $re = '◯'; $mth = '───'
      $glow = 'Magenta'; $mood = 'ANALYZE'; $status = 'Deep thinking...'
    } else {
      $ant = $spinners[$frame % 4]; $lb = '─'; $rb = '╱'; $le = '◯'; $re = '◉'; $mth = $mouths[$frame % 4]
      $glow = 'Yellow'; $mood = 'THINKING'; $status = 'Processing task...'
    }
  } else {
    $cycle = [int](($frame / 25) % 6)
    $subTick = $frame % 25
    if ($cycle -eq 0) {
      # Looking around
      $ant = '⚇'; $lb = '─'; $rb = '─'; $mth = '───'; $glow = 'Cyan'; $mood = 'LOOK'
      if ($subTick -lt 7) { $le = '◖'; $re = '◖'; $status = 'Scanning left...' }
      elseif ($subTick -lt 14) { $le = '◉'; $re = '◉'; $status = 'Standing by...' }
      elseif ($subTick -lt 20) { $le = '◗'; $re = '◗'; $status = 'Scanning right...' }
      else { $le = '◉'; $re = '◉'; $status = 'Standing by...' }
    } elseif ($cycle -eq 1) {
      # YAWN SEQUENCE!
      $mood = 'YAWN'; $glow = 'Yellow'; $ant = '~'
      if ($subTick -lt 8) {
        $lb = '─'; $rb = '─'; $le = '˘'; $re = '˘'; $mth = ' - '; $status = 'Feeling drowsy...'
      } elseif ($subTick -lt 18) {
        $lb = '╭'; $rb = '╮'; $le = '>'; $re = '<'; $mth = '╰◯╯'; $status = 'Yaaaaawn... *stretch*'
      } else {
        $lb = '─'; $rb = '─'; $le = '─'; $re = '─'; $mth = ' ˘ '; $status = '*sigh* so sleepy...'
      }
    } elseif ($cycle -eq 2) {
      # DEEP SLEEP / SNOOZING
      $mood = 'SLEEP'; $glow = 'DarkGray'
      $zs = @('z', 'Z', 'z', 'Z')
      $ant = $zs[[int](($frame / 6) % 4)]
      $lb = '─'; $rb = '─'
      if (($subTick % 10) -lt 5) {
        $le = '─'; $re = '─'; $mth = '───'; $status = 'zzz... snoozing...'
      } else {
        $le = '˘'; $re = '˘'; $mth = ' ˘ '; $status = 'zzz... dreaming code'
      }
    } elseif ($cycle -eq 3) {
      # CURIOUS
      $ant = '⚇'; $lb = '^'; $rb = '─'; $le = '◖'; $re = '◉'; $mth = ' ▱ '
      $glow = 'Magenta'; $mood = 'CURIOUS'; $status = 'Awaiting task...'
    } elseif ($cycle -eq 4) {
      # HAPPY
      $ant = '☼'; $lb = '╭'; $rb = '╮'; $le = '^'; $re = '^'; $mth = '╰━╯'
      $glow = 'Green'; $mood = 'HAPPY'; $status = 'All nominal!'
    } else {
      # WINK
      $ant = '★'; $lb = '╭'; $rb = '─'; $mth = '╰━╯'
      $le = '^'; $re = if (($frame % 10) -lt 7) { '◉' } else { '^' }
      $glow = 'Green'; $mood = 'WINK'; $status = 'Ready for work!'
    }
  }

  $stTrunc = if ($status.Length -gt 22) { $status.Substring(0, 22) } else { $status.PadRight(22) }
  $mthFmt = ("{0,3}" -f $mth)

  switch ($lineIndex) {
    0  { return @{ Pre = "┌── "; Mid = "R.E.Y. BOT"; MidColor = $glow; Sep = " ─ ["; Text = ("{0,-7}" -f $mood); TextColor = $glow; Post = "]─┐" } }
    1  { return @{ Pre = "│         ╭───╮            │"; Mid = ""; Post = "" } }
    2  { return @{ Pre = "│         │ "; Mid = $ant; MidColor = $glow; Post = " │            │" } }
    3  { return @{ Pre = "│       ╭─┴───┴─╮          │"; Mid = ""; Post = "" } }
    4  { return @{ Pre = "│      ╱         ╲         │"; Mid = ""; Post = "" } }
    5  { return @{ Pre = "│     │   "; Mid = "$lb   $rb"; MidColor = $glow; Post = "   │        │" } }
    6  { return @{ Pre = "│     │   "; Mid = "$le   $re"; MidColor = $glow; Post = "   │        │" } }
    7  { return @{ Pre = "│     │           │        │"; Mid = ""; Post = "" } }
    8  { return @{ Pre = "│     │    "; Mid = $mthFmt; MidColor = $glow; Post = "    │        │" } }
    9  { return @{ Pre = "│      ╲         ╱         │"; Mid = ""; Post = "" } }
    10 { return @{ Pre = "│       ╰───────╯          │"; Mid = ""; Post = "" } }
    11 { return @{ Pre = "└─ "; Mid = $stTrunc; MidColor = 'White'; Post = " ─┘" } }
  }
}

function Write-SystemRow([int]$row, [string]$leftText, [string]$leftColor, [object]$robot) {
  try {
    $dims = Get-ConsoleSize
    $winWidth  = $dims.Width
    $winHeight = $dims.Height

    if ($row -lt 0 -or $row -ge $winHeight) { return }

    try {
      $pos = New-Object System.Management.Automation.Host.Coordinates(0, $row)
      $Host.UI.RawUI.CursorPosition = $pos
    } catch {
      try { [Console]::SetCursorPosition(0, $row) } catch { }
    }

    if ($robot -and $winWidth -ge 95) {
      $maxLeft = 65
      $cleanLeft = if ($leftText.Length -gt $maxLeft) { $leftText.Substring(0, $maxLeft) } else { $leftText.PadRight($maxLeft) }
      Write-Host $cleanLeft -NoNewline -ForegroundColor $leftColor
      Write-Host "  " -NoNewline
      Write-Host $robot.Pre -NoNewline -ForegroundColor DarkGray
      if ($robot.Mid) {
        Write-Host $robot.Mid -NoNewline -ForegroundColor $robot.MidColor
      }
      if ($robot.Sep) {
        Write-Host $robot.Sep -NoNewline -ForegroundColor DarkGray
        Write-Host $robot.Text -NoNewline -ForegroundColor $robot.TextColor
      }
      Write-Host $robot.Post -NoNewline -ForegroundColor DarkGray

      $usedCols = 65 + 2 + 28
      $remain = [Math]::Max(0, $winWidth - $usedCols - 1)
      if ($remain -gt 0) {
        Write-Host (" " * $remain) -NoNewline
      }
    } else {
      $maxLen = [Math]::Max(10, $winWidth - 1)
      $padded = if ($leftText.Length -gt $maxLen) { $leftText.Substring(0, $maxLen) } else { $leftText.PadRight($maxLen) }
      Write-Host $padded -NoNewline -ForegroundColor $leftColor
    }
  } catch { }
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

    $healthColor = if ($state.Health -like '*NOMINAL*') { 'Green' } elseif ($state.Health -like '*CHECKING*') { 'Yellow' } else { 'Red' }
    $actColor    = if ($working) { 'Yellow' } else { 'Green' }
    $tag         = if ($working) { '[ THINKING ]' } else { '[ STANDBY ]' }
    $headColor   = if ($working) { 'Yellow' } else { 'Cyan' }

    Write-Row 0  '  ==============================================================' $headColor
    Write-Row 1  ("   R.E.Y.  //  RUNTIME EXECUTION & YIELD MONITOR  $tag [ $s ] [$bar]") $headColor
    Write-Row 2  '  ==============================================================' $headColor

    # Find active task title for robot face
    $activeTask = ''
    $workingSessions = @($script:threadCache.Values | Where-Object { $_.state -eq 'WORKING' })
    if ($workingSessions.Count -gt 0) {
      $activeTask = [string]$workingSessions[0].title
    } elseif ($script:threadCache.Count -gt 0) {
      $activeTask = [string](@($script:threadCache.Values)[0].title)
    }

    $healthOk = ($state.Health -eq 'ALL SYSTEMS NOMINAL')
    $sysRows = @(
      @{ Text = ("   opencode IDE  : " + $state.IdeStatus); Color = $state.IdeColor },
      @{ Text = ("   workspace     : " + $state.Workspace); Color = 'White' },
      @{ Text = ("   default model : " + $state.DefaultModel); Color = 'White' },
      @{ Text = ("   small model   : " + $state.SmallModel); Color = 'White' },
      @{ Text = ("   providers     : " + (Shorten $state.Providers 44)); Color = 'White' },
      @{ Text = ("   models visible: " + $state.ModelCount); Color = 'White' },
      @{ Text = ("   opencode      : " + $state.Version); Color = 'White' },
      @{ Text = ("   active threads: " + $state.ThreadCount); Color = 'Magenta' },
      @{ Text = ("   activity      : " + $state.Activity); Color = $actColor },
      @{ Text = ("   status        : " + $state.Health); Color = $healthColor },
      @{ Text = ("   tokens used   : {0} ({1}p | {2}c | {3}cache) [{4}]" -f $state.TokensTotal, $state.TokensPrompt, $state.TokensComp, $state.TokensCache, $state.TokensCost); Color = 'Cyan' },
      @{ Text = ("   last refresh  : " + $state.LastRefresh + '  (Q: quit | T: tokens | O: override | H: health)'); Color = 'DarkGray' }
    )

    # Calculate elapsed working seconds
    $elapsedSec = 0
    if ($working -and $script:workingStart) {
      $elapsedSec = ([DateTime]::Now - $script:workingStart).TotalSeconds
    }

    # Frustration Punch Trigger:
    # Occurs randomly when a task has run for 10-20+ minutes (elapsedSec >= 600)
    # Also support task title "[punch]" or "[test-punch]" for immediate testing
    if ($working -and ($elapsedSec -ge 600 -or $activeTask -match '\[punch\]|massive|heavy')) {
      if (-not $script:punchActive) {
        if (($frame - $script:lastPunchFrame) -gt 150) { # at least 30s between punches
          $randVal = Get-Random -Minimum 0 -Maximum 100
          if ($randVal -lt 8 -or $activeTask -match '\[punch\]') {
            $script:punchActive = $true
            $script:punchTick = 0
            $script:lastPunchFrame = $frame
          }
        }
      } else {
        $script:punchTick++
        if ($script:punchTick -gt 20) {
          $script:punchActive = $false
        }
      }
    } else {
      $script:punchActive = $false
    }

    for ($idx = 0; $idx -lt 12; $idx++) {
      $rNum = 3 + $idx
      $item = $sysRows[$idx]
      $robotObj = if ($curW -ge 95) { Get-RobotLine $idx $frame $working $activeTask $healthOk $script:punchActive $script:punchTick } else { $null }
      Write-SystemRow $rNum $item.Text $item.Color $robotObj
    }

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
  $Host.UI.RawUI.WindowTitle = 'R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI'
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
  Add-Log 'R.E.Y. monitor initialized (real-time telemetry)'
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
          if ($key.Key -eq 'O') {
            try { [Console]::CursorVisible = $true } catch { }
            try { [Console]::Clear() } catch { Clear-Host }
            $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
            $pyOverride = Join-Path $scriptDir 'rey-override.py'
            if (-not (Test-Path $pyOverride)) {
              $pyOverride = Join-Path $HOME '.config\opencode\scripts\rey-override.py'
            }
            if (Test-Path $pyOverride) {
              & python "$pyOverride"
            }
            Refresh-Status
            try { [Console]::Clear() } catch { Clear-Host }
            try { [Console]::CursorVisible = $false } catch { }
          }
          if ($key.Key -eq 'H') {
            try { [Console]::CursorVisible = $true } catch { }
            try { [Console]::Clear() } catch { Clear-Host }
            $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
            $pyHealth = Join-Path $scriptDir 'rey-health.py'
            if (-not (Test-Path $pyHealth)) {
              $pyHealth = Join-Path $HOME '.config\opencode\scripts\rey-health.py'
            }
            if (Test-Path $pyHealth) {
              & python "$pyHealth"
              Write-Host ""
              Write-Host "  Press any key to return to R.E.Y. Monitor..." -ForegroundColor DarkGray
              try { [Console]::ReadKey($true) | Out-Null } catch { }
            }
            $script:lastHealthCheck = [DateTime]::Now
            Refresh-Status
            try { [Console]::Clear() } catch { Clear-Host }
            try { [Console]::CursorVisible = $false } catch { }
          }
        }
      } catch { }
    }

    # 30-minute background health & discovery watchdog
    if (((Get-Date) - $script:lastHealthCheck).TotalMinutes -ge 30) {
      $script:lastHealthCheck = Get-Date
      $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
      $pyHealth = Join-Path $scriptDir 'rey-health.py'
      if (-not (Test-Path -LiteralPath $pyHealth)) {
        $pyHealth = Join-Path $HOME '.config\opencode\scripts\rey-health.py'
      }
      if (Test-Path -LiteralPath $pyHealth) {
        Start-Process -FilePath "python" -ArgumentList "`"$pyHealth`"", "--quiet" -WindowStyle Hidden
        Add-Log "[HEALTH] 30m background watchdog started"
      }
    }

    if (($frame % $REFRESH_EVERY) -eq 0 -and $frame -ne 0) {
      Refresh-Status
    }

    Draw $frame $script:wasWorking

    if ($script:wasWorking) { $frame += 2 } else { $frame++ }
    Start-Sleep -Milliseconds $TICK_MS
  }
} catch {
  Write-Host ""
  Write-Host "  [!] R.E.Y. MONITOR RUNTIME ERROR:" -ForegroundColor Red
  Write-Host "      $($_.Exception.Message)" -ForegroundColor Yellow
  Write-Host "      Line: $($_.InvocationInfo.ScriptLineNumber)" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  Press Enter to exit..." -ForegroundColor DarkGray
  try { [Console]::ReadLine() | Out-Null } catch { }
} finally {
  try { [Console]::CursorVisible = $true } catch { }
  Write-Host ''
  Write-Host '  R.E.Y. monitor stopped. Stay nominal, stay in control.' -ForegroundColor Cyan
}
