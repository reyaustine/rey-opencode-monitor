#!/usr/bin/env node

/**
 * R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI
 * Cross-platform runner for npm / npx
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const isWin = process.platform === 'win32';
const rootDir = path.resolve(__dirname, '..');

function run(cmd, argv) {
  const child = spawn(cmd, argv, { stdio: 'inherit' });
  let done = false;
  child.on('error', (err) => {
    if (!done) {
      done = true;
      console.error(`[rey] cannot run ${cmd}: ${err.message}`);
      process.exit(1);
    }
  });
  child.on('exit', (code) => {
    if (!done) {
      done = true;
      process.exit(code == null ? 1 : code);
    }
  });
}

function resolveScript(name) {
  const candidates = [
    path.join(rootDir, 'scripts', name),
    path.join(rootDir, name),
    path.join(require('os').homedir(), '.config', 'opencode', 'scripts', name),
    path.join(require('os').homedir(), '.config', 'opencode', name)
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return path.join(rootDir, 'scripts', name);
}

function pyScript(name, extra) {
  return () => {
    const script = resolveScript(name);
    if (!fs.existsSync(script)) {
      console.error(`[rey] script not found: ${name} (checked package and ~/.config/opencode)`);
      process.exit(1);
    }
    const py = isWin ? 'python' : 'python3';
    run(py, [script, ...(extra || [])]);
  };
}

// First non-flag token = the command. Everything else = args for the command.
const cmd = args.find(a => !a.startsWith('-')) || '';
const rest = args.filter(a => a !== cmd);

// Help handling before running any command
if (args.includes('--help') || args.includes('-h') || args.includes('-?') || cmd === 'help') {
  console.log('');
  console.log('  R.E.Y. // Runtime Execution & Yield Monitor');
  console.log('  OpenCode Swarm Load Balancer & Fleet Commander');
  console.log('');
  console.log('  Usage: rey [command] [options]');
  console.log('');
  console.log('  Commands:');
  console.log('    status           One-line or JSON fleet status (--json)');
  console.log('    health           Audit provider gateways & live free/discounted models (--quiet)');
  console.log('    whitelist        Auto-whitelist newly discovered free models into OpenCode');
  console.log('    quota            Live multi-provider rate limits, credit balance & failover advice');
  console.log('    models           Browse all allowlisted & discovered models (--list, --json)');
  console.log('    fix, doctor      Run diagnostic checks & auto-repair configurations');
  console.log('    override         Lock or rotate IDE default model across all configs/DB/sessions');
  console.log('    roster           Auto-select specialized optimal models for subagent roles');
  console.log('    breaker          Check or trigger circuit breaker & auto-quarantine (--status)');
  console.log('    unblock          Reset circuit breakers & clear quarantined models/providers');
  console.log('    switch-provider  Switch primary provider (kilo | opencode | openrouter)');
  console.log('    deals            Browse active OpenRouter promotional discounted models');
  console.log('    logs             Stream & filter OpenCode runtime activity & fallback logs');
  console.log('    deploy           Deploy configs, instructions, & commands into OpenCode');
  console.log('    verify           Run binary & runtime patch verification suite');
  console.log('    update           Self-update via git pull or GitHub Packages (--check)');
  console.log('    report           Cost & quota report from token-tracker (--json, --top)');
  console.log('    cleanup          Prune stale .bak backups (--dry-run, --prune-keeps)');
  console.log('    install          Run system installer & dependencies setup');
  console.log('    (no command)     Launch the interactive real-time R.E.Y. HUD Terminal Monitor');
  console.log('');
  process.exit(0);
}

switch (cmd) {
  case 'install':
    if (isWin) {
      run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', resolveScript('install.ps1'), ...rest]);
    } else {
      run('bash', [resolveScript('install.sh'), ...rest]);
    }
    break;

  case 'verify':
    if (isWin) {
      run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', resolveScript('verify.ps1'), ...rest]);
    } else {
      run('bash', [resolveScript('verify.sh'), ...rest]);
    }
    break;

  case 'roster':
    pyScript('rey-roster.py', rest)();
    break;

  case 'breaker':
  case 'quarantine':
    pyScript('rey-breaker.py', rest)();
    break;

  case 'unblock':
  case 'reset-breaker':
    pyScript('rey-breaker.py', ['--reset', ...(rest.length ? rest : ['all'])])();
    break;

  case 'health':
    pyScript('rey-health.py', rest)();
    break;

  case 'whitelist':
    pyScript('rey-health.py', ['--whitelist', ...rest])();
    break;

  case 'logs':
    pyScript('rey-logs.py', rest)();
    break;

  case 'deals':
    pyScript('rey-deals.py', rest)();
    break;

  case 'override':
    pyScript('rey-override.py', rest)();
    break;

  case 'quota':
    pyScript('rey-quota.py', rest)();
    break;

  case 'fix':
  case 'doctor':
    pyScript('rey-fix.py', rest)();
    break;

  case 'status':
    pyScript('rey-status.py', rest)();
    break;

  case 'models':
    {
      let extra = rest;
      if (!extra.includes('--list') && !extra.includes('-l') && !extra.includes('--json')) {
        extra = ['--list', ...extra];
      }
      pyScript('rey-models.py', extra)();
    }
    break;

  case 'switch-provider':
  case 'switch':
    pyScript('rey-switch.py', rest)();
    break;

  case 'update':
    pyScript('rey-update.py', rest)();
    break;

  case 'report':
    pyScript('rey-report.py', rest)();
    break;

  case 'cleanup':
    pyScript('rey-cleanup.py', rest)();
    break;

  case 'deploy':
  case 'deploy-config':
    {
      const homeDir = require('os').homedir();
      const configsDir = path.join(rootDir, 'configs');
      const globalDir = path.join(homeDir, '.config', 'opencode');
      const files = ['opencode.jsonc', 'opencode.json', 'model-fallback.json', 'skill-routing.yaml'];

      console.log('');
      console.log('  Deploying swarm configs to ' + globalDir);
      console.log('');

      fs.mkdirSync(globalDir, { recursive: true });
      for (const f of files) {
        const src = path.join(configsDir, f);
        const dst = path.join(globalDir, f);
        if (fs.existsSync(src)) {
          try {
            fs.copyFileSync(src, dst);
            console.log('  [+] ' + f);
          } catch (e) {
            console.log('  [!] ' + f + ' failed: ' + e.message);
          }
        } else {
          console.log('  [-] ' + f + ' (not found in configs/)');
        }
      }

      // Also deploy instructions and commands
      for (const sub of ['instructions', 'commands']) {
        const srcDir = path.join(rootDir, sub);
        const dstDir = path.join(globalDir, sub);
        if (fs.existsSync(srcDir)) {
          fs.mkdirSync(dstDir, { recursive: true });
          for (const f of fs.readdirSync(srcDir)) {
            const s = path.join(srcDir, f);
            const d = path.join(dstDir, f);
            if (fs.statSync(s).isFile()) {
              try {
                fs.copyFileSync(s, d);
                console.log('  [+] ' + sub + '/' + f);
              } catch (e) {
                console.log('  [!] ' + sub + '/' + f + ' failed: ' + e.message);
              }
            }
          }
        }
      }

      console.log('');
      console.log('  Config deployed. Restart OpenCode to apply.');
      console.log('');
      process.exit(0);
    }
    break;

  default:
    // No command = launch monitor. Unknown command = error.
    if (!cmd) {
      if (isWin) {
        const psScript = resolveScript('rey-monitor.ps1');
        run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', psScript, ...args]);
      } else {
        const monitorPy = resolveScript('rey-monitor.py');
        run('python3', [monitorPy, ...args]);
      }
    } else {
      console.log('');
      console.log('  Unknown command: ' + cmd);
      console.log('');
      console.log('  Usage: rey [command]');
      console.log('    status | health | quota | models | fix | override | roster');
      console.log('    switch-provider | deals | logs | deploy | verify | install');
      console.log('    update | report | cleanup');
      console.log('    (no command) -> start the R.E.Y. Monitor');
      console.log('');
      process.exit(1);
    }
    break;
}
