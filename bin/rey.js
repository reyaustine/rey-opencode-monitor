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

function pyScript(name, extra) {
  return () => {
    const script = path.join(rootDir, 'scripts', name);
    if (!fs.existsSync(script)) {
      console.error(`[rey] script not found: ${script}`);
      process.exit(1);
    }
    const py = isWin ? 'python' : 'python3';
    run(py, [script, ...(extra || [])]);
  };
}

// First non-flag token = the command. Everything else = args for the command.
const cmd = args.find(a => !a.startsWith('-')) || '';
const rest = args.filter(a => a !== cmd);

switch (cmd) {
  case 'install':
    if (isWin) {
      run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', path.join(rootDir, 'install.ps1'), ...rest]);
    } else {
      run('bash', [path.join(rootDir, 'install.sh'), ...rest]);
    }
    break;

  case 'health':
    pyScript('rey-health.py', rest)();
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
    if (isWin) {
      // Interactive menu mode (no provider arg) or direct: rey switch-provider <provider>
      const switchScript =
        path.join(rootDir, 'scripts', 'switch-provider.ps1');
      if (fs.existsSync(switchScript)) {
        const provider = rest[0];
        const pass = provider && ['kilo', 'opencode', 'openrouter'].includes(provider)
          ? ['-Provider', provider]
          : rest;
        run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-NoProfile', '-File', switchScript, ...pass]);
      } else {
        console.error('[rey] switch-provider.ps1 not found. Run "rey deploy" first.');
        process.exit(1);
      }
    } else {
      console.log('Provider switcher is only available on Windows (PowerShell).');
      process.exit(1);
    }
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
        run('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', path.join(rootDir, 'scripts', 'rey-monitor.ps1'), ...args]);
      } else {
        const monitorPy = path.join(rootDir, 'scripts', 'rey-monitor.py');
        run('python3', [monitorPy, ...args]);
      }
    } else {
      console.log('');
      console.log('  Unknown command: ' + cmd);
      console.log('');
      console.log('  Usage: rey [command]');
      console.log('    status | health | quota | models | fix | logs | deals | override');
      console.log('    switch-provider | deploy | install');
      console.log('    (no command) -> start the R.E.Y. Monitor');
      console.log('');
      process.exit(1);
    }
    break;
}
