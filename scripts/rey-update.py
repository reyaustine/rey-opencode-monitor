#!/usr/bin/env python3
"""
R.E.Y. // Self-Update Command - Git Pull & NPM Registry Installer
Fetches latest from origin/main, stashes dirty state, merges, restores stash,
and optionally installs from GitHub Packages NPM registry.
"""

import os
import sys
import subprocess
import glob
import argparse
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
WHITE = "\033[37m"
GRAY = "\033[90m"

HOME = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
NPM_REGISTRY = "https://npm.pkg.github.com"
PACKAGE_NAME = "@reyaustine/rey-opencode-monitor"


def run_cmd(cmd, cwd=None, capture=False):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return result.returncode, result.stdout if capture else "", result.stderr if capture else ""
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out after 120s"


def check_status(branch="main"):
    """Compare local HEAD vs origin/main via git fetch + rev-list."""
    print(f"\n  {CYAN}R.E.Y. // Update Status Check{RESET}")
    print(f"  {'─' * 50}")

    # Ensure we're in a git repo
    rc, out, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_ROOT, capture=True)
    if rc != 0:
        print(f"  {RED}[!] Not a git repository: {REPO_ROOT}{RESET}")
        return False

    # Get current branch
    rc, cur_branch, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, capture=True)
    cur_branch = cur_branch.strip()
    print(f"  Current branch : {WHITE}{cur_branch}{RESET}")

    # Get current HEAD SHA
    rc, head_sha, _ = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture=True)
    head_sha = head_sha.strip()
    print(f"  Local HEAD     : {WHITE}{head_sha}{RESET}")

    # Fetch origin
    print(f"\n  Fetching from origin...", end="", flush=True)
    rc, _, fetch_err = run_cmd(["git", "fetch", "origin"], cwd=REPO_ROOT, capture=True)
    if rc != 0:
        print(f"\n  {RED}[!] git fetch failed: {fetch_err.strip()}{RESET}")
        return False
    print(f" {GREEN}OK{RESET}")

    # Check if remote branch exists
    rc, remote_ref, _ = run_cmd(["git", "rev-parse", "--verify", f"origin/{branch}"], cwd=REPO_ROOT, capture=True)
    if rc != 0:
        print(f"  {YELLOW}[!] Remote branch origin/{branch} not found{RESET}")
        return True

    # Count ahead/behind
    rc, ahead_out, _ = run_cmd(
        ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
        cwd=REPO_ROOT, capture=True,
    )
    behind_count = ahead_out.strip() if rc == 0 and ahead_out.strip().isdigit() else "?"

    rc, behind_out, _ = run_cmd(
        ["git", "rev-list", "--count", f"origin/{branch}..HEAD"],
        cwd=REPO_ROOT, capture=True,
    )
    ahead_count = behind_out.strip() if rc == 0 and behind_out.strip().isdigit() else "?"

    # Remote HEAD SHA
    rc, remote_sha, _ = run_cmd(["git", "rev-parse", "--short", f"origin/{branch}"], cwd=REPO_ROOT, capture=True)
    remote_sha = remote_sha.strip()
    print(f"  Remote HEAD    : {WHITE}{remote_sha}{RESET} (origin/{branch})")

    # Dirty check
    rc, status_out, _ = run_cmd(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture=True)
    dirty = bool(status_out.strip())
    dirty_label = f"{YELLOW}dirty ({len(status_out.strip().splitlines())} modified){RESET}" if dirty else f"{GREEN}clean{RESET}"
    print(f"  Working tree   : {dirty_label}")

    # Summary
    if behind_count == "0" and ahead_count == "0":
        print(f"\n  {GREEN}[✓] Up to date with origin/{branch}{RESET}")
    else:
        if behind_count != "0" and behind_count != "?":
            print(f"\n  {YELLOW}↓ {behind_count} commit(s) behind origin/{branch}{RESET}")
        if ahead_count != "0" and ahead_count != "?":
            print(f"  {CYAN}↑ {ahead_count} commit(s) ahead of origin/{branch}{RESET}")

    print()
    return True


def update_git(branch="main"):
    """Stash local changes, git pull, restore stash, print SHA."""
    print(f"\n  {CYAN}R.E.Y. // Git Update{RESET}")
    print(f"  {'─' * 50}")

    # Verify git repo
    rc, _, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_ROOT, capture=True)
    if rc != 0:
        print(f"  {RED}[!] Not a git repository: {REPO_ROOT}{RESET}")
        return False

    # Check dirty state
    rc, status_out, _ = run_cmd(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture=True)
    dirty = bool(status_out.strip())
    stashed = False

    if dirty:
        print(f"  {YELLOW}[*] Working tree is dirty, stashing changes...{RESET}")
        rc, _, stash_err = run_cmd(
            ["git", "stash", "push", "-m", f"rey-update auto-stash {time.strftime('%Y%m%d-%H%M%S')}"],
            cwd=REPO_ROOT, capture=True,
        )
        if rc != 0:
            print(f"  {RED}[!] git stash failed: {stash_err.strip()}{RESET}")
            return False
        stashed = True
        print(f"  {GREEN}[✓] Changes stashed{RESET}")

    # Fetch first
    print(f"  Fetching origin...", end="", flush=True)
    rc, _, fetch_err = run_cmd(["git", "fetch", "origin"], cwd=REPO_ROOT, capture=True)
    if rc != 0:
        print(f"\n  {RED}[!] git fetch failed: {fetch_err.strip()}{RESET}")
        if stashed:
            run_cmd(["git", "stash", "pop"], cwd=REPO_ROOT, capture=True)
        return False
    print(f" {GREEN}OK{RESET}")

    # Try fast-forward first
    print(f"  Pulling origin/{branch} (--ff-only)...", end="", flush=True)
    rc, _, pull_err = run_cmd(
        ["git", "pull", "--ff-only", "origin", branch],
        cwd=REPO_ROOT, capture=True,
    )
    if rc != 0:
        print(f" {YELLOW}FF failed, trying merge...{RESET}")
        rc2, _, merge_err = run_cmd(
            ["git", "pull", "--no-rebase", "origin", branch],
            cwd=REPO_ROOT, capture=True,
        )
        if rc2 != 0:
            print(f"  {RED}[!] git pull failed: {merge_err.strip()}{RESET}")
            if stashed:
                print(f"  Restoring stash...", end="", flush=True)
                run_cmd(["git", "stash", "pop"], cwd=REPO_ROOT, capture=True)
                print(f" {GREEN}OK{RESET}")
            return False
    else:
        print(f" {GREEN}OK{RESET}")

    # Restore stash
    if stashed:
        print(f"  Restoring stashed changes...", end="", flush=True)
        rc, _, pop_err = run_cmd(["git", "stash", "pop"], cwd=REPO_ROOT, capture=True)
        if rc != 0:
            print(f"\n  {YELLOW}[!] Stash pop had conflicts: {pop_err.strip()}{RESET}")
            print(f"  {YELLOW}    Your changes are still in git stash. Run 'git stash pop' manually when ready.{RESET}")
        else:
            print(f" {GREEN}OK{RESET}")

    # Print current SHA
    rc, sha, _ = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture=True)
    sha = sha.strip()
    rc2, full_sha, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture=True)
    full_sha = full_sha.strip()
    print(f"\n  {GREEN}[✓] Updated to {sha}{RESET}")
    print(f"  Full SHA: {DIM}{full_sha}{RESET}")

    # BOM check
    bom_check_ps1()

    return True


def update_npm(version=None):
    """Verify .npmrc auth, then npm install from GitHub Packages registry."""
    print(f"\n  {CYAN}R.E.Y. // NPM Update (GitHub Packages){RESET}")
    print(f"  {'─' * 50}")

    npmrc_path = os.path.join(HOME, ".npmrc")
    npmrc_global = os.path.join(HOME, ".npmrc")

    # Check .npmrc for GitHub Packages auth token
    auth_found = False
    for rc_path in [npmrc_global, os.path.join(REPO_ROOT, ".npmrc")]:
        if os.path.exists(rc_path):
            try:
                with open(rc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "//npm.pkg.github.com/:_authToken" in content:
                    auth_found = True
                    print(f"  {GREEN}[✓] Found GitHub Packages auth token in {rc_path}{RESET}")
                    break
            except Exception:
                pass

    if not auth_found:
        print(f"\n  {RED}[!] No GitHub Packages auth token found in ~/.npmrc{RESET}")
        print(f"\n  {YELLOW}To set up authentication for github.com:npm.pkg.github.com:{RESET}")
        print(f"  {WHITE}1.{RESET} Generate a Personal Access Token (PAT) at:")
        print(f"     {DIM}https://github.com/settings/tokens{RESET}")
        print(f"  {WHITE}2.{RESET} Select scope: {GREEN}read:packages{RESET}")
        print(f"  {WHITE}3.{RESET} Add to ~/.npmrc:")
        print(f"     {DIM}//npm.pkg.github.com/:_authToken=ghp_YOUR_TOKEN_HERE{RESET}")
        print(f"  {WHITE}4.{RESET} Run: {GREEN}rey update --mode npm{RESET}")
        print()
        return False

    # Determine version
    if not version:
        # Try to read from package.json
        pkg_json = os.path.join(REPO_ROOT, "package.json")
        if os.path.exists(pkg_json):
            import json
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                version = data.get("version", "latest")
            except Exception:
                version = "latest"
        else:
            version = "latest"

    pkg_ref = f"{PACKAGE_NAME}@{version}"
    print(f"  Installing {WHITE}{pkg_ref}{RESET}...")
    print(f"  Registry: {DIM}{NPM_REGISTRY}{RESET}\n")

    rc, out, err = run_cmd(
        ["npm", "install", "-g", pkg_ref, f"--registry={NPM_REGISTRY}"],
        cwd=REPO_ROOT, capture=False,
    )

    if rc != 0:
        print(f"\n  {RED}[!] npm install failed (exit code {rc}){RESET}")
        if err:
            print(f"  {err.strip()}")
        return False

    print(f"\n  {GREEN}[✓] Successfully installed {pkg_ref}{RESET}")

    # BOM check
    bom_check_ps1()

    return True


def bom_check_ps1():
    """Scan scripts/*.ps1 for multibyte UTF-8 without BOM and warn."""
    ps1_files = glob.glob(os.path.join(SCRIPT_DIR, "*.ps1"))
    warned = 0
    for fpath in ps1_files:
        try:
            with open(fpath, "rb") as f:
                raw = f.read(3)
            has_bom = raw[:3] == b"\xef\xbb\xbf"
            if not has_bom:
                # Check if file actually has multibyte chars
                with open(fpath, "rb") as f:
                    full = f.read()
                has_multibyte = any(b > 127 for b in full)
                if has_multibyte:
                    fname = os.path.basename(fpath)
                    print(f"  {YELLOW}[BOM]{RESET} {fname} has multibyte chars but no UTF-8 BOM")
                    warned += 1
        except Exception:
            pass

    if warned == 0:
        print(f"  {GREEN}[✓] BOM check passed — all .ps1 files OK{RESET}")
    else:
        print(f"\n  {YELLOW}Tip:{RESET} PowerShell on Windows may misbehave without BOM on multibyte files.")
        print(f"         Use: {DIM}[System.IO.File]::WriteAllBytes($path, (New-Object byte[] @(0xEF,0xBB,0xBF)) + [System.IO.File]::ReadAllBytes($path)){RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="rey update",
        description="R.E.Y. Self-Updater — git pull or npm install from GitHub Packages",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Dry-run status check (compare local vs remote, no changes applied)",
    )
    parser.add_argument(
        "--mode", choices=["git", "npm"], default="git",
        help="Update method: git (pull origin) or npm (install from registry). Default: git",
    )
    parser.add_argument(
        "--branch", default="main",
        help="Git branch to pull from (default: main)",
    )
    parser.add_argument(
        "--version", default=None,
        help="NPM package version to install (default: read from package.json)",
    )
    parser.add_argument(
        "--bom-check", action="store_true",
        help="Run BOM check on .ps1 files only (skip update)",
    )


    args = parser.parse_args()

    print(f"\n  {BOLD}{CYAN}R.E.Y. // Self-Updater{RESET}")
    print(f"  Repository: {DIM}{REPO_ROOT}{RESET}")
    print(f"  Mode: {WHITE}{args.mode}{RESET}")
    print(f"  Branch: {WHITE}{args.branch}{RESET}")
    if args.version:
        print(f"  Version: {WHITE}{args.version}{RESET}")

    if args.bom_check:
        bom_check_ps1()
        return 0

    if args.check:
        ok = check_status(branch=args.branch)
        return 0 if ok else 1

    if args.mode == "git":
        ok = update_git(branch=args.branch)
    else:
        ok = update_npm(version=args.version)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
