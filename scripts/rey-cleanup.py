#!/usr/bin/env python3
"""
R.E.Y. // Backup Cleanup Utility
Scans for .bak* files, groups by family, and safely prunes old backups.
Never deletes tracked git files, .env, or live configs.
Never touches bin/rey.js.
"""

import os
import sys
import glob
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Set


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ANSI colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
GRAY = "\033[90m"


def get_repo_root() -> str:
    """Detect repo root by checking for .git directory."""
    cwd = os.getcwd()
    while True:
        if os.path.isdir(os.path.join(cwd, ".git")):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            return cwd
        cwd = parent


def get_scan_paths() -> List[str]:
    """Return all directories to scan for .bak files (deduplicated)."""
    home_config = os.path.expanduser("~/.config/opencode")
    repo_root = get_repo_root()
    paths = []
    seen = set()
    for path in [home_config, repo_root]:
        norm = os.path.normcase(os.path.normpath(path))
        if os.path.isdir(path) and norm not in seen:
            seen.add(norm)
            paths.append(path)
    return paths


def is_backup_file(filepath: str) -> bool:
    """Check if a filename matches the backup pattern (*.bak*)."""
    basename = os.path.basename(filepath)
    if ".bak" not in basename:
        return False
    # Must not be a live config name without backup suffix
    # e.g., opencode.json without .bak is a live config
    name_no_ext = os.path.splitext(basename)[0]
    # A backup file must have ".bak" somewhere in the name
    return True


def is_live_config(filepath: str) -> bool:
    """Check if the file is a live configuration (not a backup)."""
    basename = os.path.basename(filepath)
    # Files that are live configs, never to be deleted
    live_names = {"opencode.json", "opencode.jsonc", "model-fallback.json", ".env"}
    name_no_ext = os.path.splitext(basename)[0]
    if name_no_ext in live_names:
        return True
    return False


def is_env_file(filepath: str) -> bool:
    """Check if file is an .env file."""
    basename = os.path.basename(filepath)
    return basename.startswith(".env")


def is_bin_rey_js(filepath: str) -> bool:
    """Check if the file is bin/rey.js."""
    return os.path.basename(filepath) == "rey.js" and "bin" in filepath


def get_tracked_files() -> Set[str]:
    """Get set of git-tracked file paths (relative to repo root)."""
    tracked = set()
    repo_root = get_repo_root()
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                tracked.add(os.path.normpath(os.path.join(repo_root, line)))
    except Exception:
        pass
    return tracked


def group_backups_by_family(files: List[str]) -> Dict[str, List[str]]:
    """
    Group backup files by family name.
    E.g., opencode.json.bak.switcher.20260915-152834 -> 'opencode.json'
         model-fallback.json.bak.20260910-151348 -> 'model-fallback.json'
         opencode.jsonc.bak.20260910-154205 -> 'opencode.jsonc'
    """
    families = defaultdict(list)
    for filepath in files:
        basename = os.path.basename(filepath)
        # Extract family: everything before ".bak"
        idx = basename.find(".bak")
        if idx == -1:
            continue
        family = basename[:idx]
        families[family].append(filepath)
    # Sort each family by mtime newest first
    for family in families:
        families[family].sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return families


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def file_age_days(filepath: str) -> float:
    """Get file age in days."""
    mtime = os.path.getmtime(filepath)
    now = time.time()
    return (now - mtime) / 86400


def get_candidates(
    scan_paths: List[str],
    older_than: Optional[timedelta] = None,
    prune_keeps: Optional[int] = None
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """
    Scan for backup files and return candidates with metadata.
    Returns (all_candidates, family_groups).
    """
    all_files = []
    seen_files = set()
    for path in scan_paths:
        # Scan for *.bak* and .bak.* patterns
        for pattern in ["**/*.bak*", ".bak*"]:
            for f in glob.glob(os.path.join(path, pattern), recursive=True):
                if os.path.isfile(f):
                    norm = os.path.normcase(os.path.normpath(f))
                    if norm not in seen_files:
                        seen_files.add(norm)
                        all_files.append(f)

    # Filter to only actual backup files
    backup_files = []
    for f in all_files:
        basename = os.path.basename(f)
        if ".bak" not in basename:
            continue
        # Skip if not a backup pattern
        if not is_backup_file(f):
            continue
        backup_files.append(f)

    families = group_backups_by_family(backup_files)

    # Build candidate list with metadata
    candidates = []
    for filepath in backup_files:
        stat = os.stat(filepath)
        age = file_age_days(filepath)
        candidates.append({
            "path": filepath,
            "basename": os.path.basename(filepath),
            "family": os.path.basename(filepath)[:os.path.basename(filepath).find(".bak")],
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "age_days": age,
        })

    return candidates, families


def should_delete(
    candidate: Dict,
    tracked_files: Set[str],
    older_than: Optional[timedelta] = None,
    prune_keeps: Optional[int] = None,
    family_order: Optional[Dict[str, List[Dict]]] = None
) -> Tuple[bool, str]:
    """
    Determine if a candidate should be deleted.
    Returns (should_delete, reason).
    """
    filepath = candidate["path"]
    basename = candidate["basename"]

    # Safety: never touch bin/rey.js
    if is_bin_rey_js(filepath):
        return False, "bin/rey.js protected"

    # Safety: never touch .env files
    if is_env_file(filepath):
        return False, ".env file protected"

    # Safety: never delete tracked git files
    if filepath in tracked_files:
        return False, "git-tracked file protected"

    # Safety: never touch live configs (files without .bak suffix that happen to match)
    if is_live_config(filepath):
        return False, "live config protected"

    # Only delete files that actually contain .bak in their name
    if ".bak" not in basename:
        return False, "not a backup file"

    # Age filter
    if older_than is not None:
        if candidate["age_days"] < older_than.days:
            return False, f"younger than {older_than.days}d threshold"

    # Prune keeps: keep the newest N per family, delete the rest
    if prune_keeps is not None and family_order is not None:
        family = candidate["family"]
        family_files = family_order.get(family, [])
        # family_files is a list of filepath strings sorted newest-first
        if filepath in family_files:
            keep_index = family_files.index(filepath)
            if keep_index < prune_keeps:
                return False, f"within top {prune_keeps} of family"

    return True, "eligible for deletion"


def main():
    parser = argparse.ArgumentParser(
        description="R.E.Y. Backup Cleanup Utility — Safely prune .bak* files"
    )
    parser.add_argument(
        "path", nargs="?", default=".",
        help="Path to scan (default: current directory / repo root)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List candidates without deleting"
    )
    parser.add_argument(
        "--older-than", type=int, default=None,
        help="Delete only files older than N days"
    )
    parser.add_argument(
        "--prune-keeps", type=int, default=None,
        help="Keep newest N files per family, delete the rest"
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Confirm deletion without interactive prompt"
    )

    args = parser.parse_args()

    scan_paths = get_scan_paths()
    if not scan_paths:
        print(f"{RED}[!] No scan paths found.{RESET}")
        sys.exit(1)

    print(f"{CYAN}{'═' * 65}{RESET}")
    print(f"  {BOLD}🧹 R.E.Y. Backup Cleanup Utility{RESET}")
    print(f"{CYAN}{'═' * 65}{RESET}\n")

    # Get tracked files for safety
    tracked_files = get_tracked_files()

    # Get candidates
    candidates, families = get_candidates(scan_paths)

    if not candidates:
        print(f"{GREEN}[✓]{RESET} No .bak* files found to clean.")
        sys.exit(0)

    # Apply filters
    older_than = timedelta(days=args.older_than) if args.older_than else None
    family_order = families if args.prune_keeps is not None else None

    to_delete = []
    to_keep = []

    for cand in candidates:
        delete, reason = should_delete(
            cand, tracked_files, older_than, args.prune_keeps, family_order
        )
        if delete:
            to_delete.append((cand, reason))
        else:
            to_keep.append((cand, reason))

    # Print summary header
    print(f"  Scan paths: {', '.join(scan_paths)}")
    print(f"  Total .bak* files found: {len(candidates)}")
    print(f"  Candidates for deletion: {len(to_delete)}")
    print(f"  Files to keep: {len(to_keep)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}{BOLD}--- DRY RUN MODE (no files will be deleted) ---{RESET}\n")

    # Print candidates for deletion
    if to_delete:
        print(f"{RED}{BOLD}── Files Eligible for Deletion ──{RESET}")
        total_space = 0
        for cand, reason in sorted(to_delete, key=lambda x: x[0]["path"]):
            age_str = f"{cand['age_days']:.1f}d"
            size_str = format_size(cand['size'])
            print(f"  {RED}✗{RESET} {cand['basename']:<50} {size_str:>10}  {age_str:>8}  [{cand['family']}]")
            total_space += cand['size']
        print(f"  {'':>50} {'─' * 30}")
        print(f"  {RED}Total reclaimable:{RESET} {format_size(total_space)} ({len(to_delete)} files)")
        print()

    # Print kept files
    if to_keep:
        print(f"{GREEN}{BOLD}── Files Kept ──{RESET}")
        for cand, reason in sorted(to_keep, key=lambda x: x[0]["path"]):
            age_str = f"{cand['age_days']:.1f}d"
            size_str = format_size(cand['size'])
            print(f"  {GREEN}✓{RESET} {cand['basename']:<50} {size_str:>10}  {age_str:>8}  [{cand['family']}]  ({reason})")
        print()

    # Per-family summary
    print(f"{CYAN}{BOLD}── Per-Family Summary ──{RESET}")
    for family, files in sorted(families.items()):
        kept_count = sum(1 for c, _ in to_keep if c["family"] == family)
        delete_count = sum(1 for c, _ in to_delete if c["family"] == family)
        total_count = len(files)
        total_size = sum(os.path.getsize(f) for f in files)
        print(f"  {family}: {total_count} total ({kept_count} kept, {delete_count} deletable), {format_size(total_size)}")
    print()

    # If not dry-run, ask for confirmation and delete
    if not args.dry_run:
        if not args.yes:
            if to_delete:
                confirm = input(f"  {YELLOW}Delete {len(to_delete)} files? [y/N] {RESET}")
                if confirm.lower() != "y":
                    print(f"  {GRAY}Aborted.{RESET}")
                    sys.exit(0)
            else:
                print(f"  {GREEN}Nothing to delete.{RESET}")
                sys.exit(0)

        # Perform deletion
        deleted_count = 0
        reclaimed = 0
        for cand, _ in to_delete:
            try:
                os.remove(cand["path"])
                deleted_count += 1
                reclaimed += cand["size"]
                print(f"  {GREEN}[DEL]{RESET} {cand['basename']}")
            except Exception as e:
                print(f"  {RED}[ERR]{RESET} {cand['basename']}: {e}")

        print(f"\n  {GREEN}{BOLD}── Deletion Complete ──{RESET}")
        print(f"  Deleted: {deleted_count} files")
        print(f"  Space reclaimed: {format_size(reclaimed)}")

        # Show remaining per family
        remaining_families = defaultdict(int)
        for cand, _ in to_keep:
            remaining_families[cand["family"]] += 1
        print(f"\n  {CYAN}{BOLD}── Remaining Files Per Family ──{RESET}")
        for family, count in sorted(remaining_families.items()):
            print(f"  {family}: {count} remaining")
    else:
        print(f"\n  {YELLOW}{BOLD}── Dry Run Complete ──{RESET}")
        print(f"  {YELLOW}Run with --yes to actually delete {len(to_delete)} files.{RESET}")
        print(f"  {YELLOW}Reclaimable space: {format_size(sum(c['size'] for c, _ in to_delete))}{RESET}")

    print(f"\n{CYAN}{'═' * 65}{RESET}")


if __name__ == "__main__":
    main()
