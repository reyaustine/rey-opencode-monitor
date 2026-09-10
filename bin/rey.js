#!/usr/bin/env node

/**
 * R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI
 * Cross-platform runner for npm / npx
 */

const { spawn } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);
const isWin = process.platform === 'win32';
const rootDir = path.resolve(__dirname, '..');

if (args.includes('--install') || args.includes('install')) {
  if (isWin) {
    const installScript = path.join(rootDir, 'install.ps1');
    const child = spawn('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', installScript], { stdio: 'inherit' });
    child.on('exit', (code) => process.exit(code || 0));
  } else {
    const installScript = path.join(rootDir, 'install.sh');
    const child = spawn('bash', [installScript], { stdio: 'inherit' });
    child.on('exit', (code) => process.exit(code || 0));
  }
} else if (args.includes('--health') || args.includes('health')) {
  const healthScript = path.join(rootDir, 'scripts', 'rey-health.py');
  const pythonCmd = isWin ? 'python' : 'python3';
  const child = spawn(pythonCmd, [healthScript, ...args.filter(a => a !== 'health' && a !== '--health')], { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code || 0));
} else if (args.includes('--override') || args.includes('override')) {
  const overrideScript = path.join(rootDir, 'scripts', 'rey-override.py');
  const pythonCmd = isWin ? 'python' : 'python3';
  const child = spawn(pythonCmd, [overrideScript, ...args.filter(a => a !== 'override' && a !== '--override')], { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code || 0));
} else {
  if (isWin) {
    const monitorScript = path.join(rootDir, 'scripts', 'rey-monitor.ps1');
    const child = spawn('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', monitorScript, ...args], { stdio: 'inherit' });
    child.on('exit', (code) => process.exit(code || 0));
  } else {
    const monitorPy = path.join(rootDir, 'scripts', 'rey-monitor.py');
    const child = spawn('python3', [monitorPy, ...args], { stdio: 'inherit' });
    child.on('error', () => {
      const fallback = spawn('python', [monitorPy, ...args], { stdio: 'inherit' });
      fallback.on('exit', (code) => process.exit(code || 0));
    });
    child.on('exit', (code) => process.exit(code || 0));
  }
}
