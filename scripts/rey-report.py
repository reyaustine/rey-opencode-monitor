#!/usr/bin/env python3
"""
R.E.Y. // USAGE REPORT
Aggregated usage report from token-tracker.json and openrouter-quota.json.
Supports --daily/--weekly/--monthly windows, --json output, and --top N.
"""

import os
import sys
import json
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
TOKEN_TRACKER_PATH = os.path.join(CONFIG_DIR, "token-tracker.json")
OPENROUTER_QUOTA_PATH = os.path.join(CONFIG_DIR, "openrouter-quota.json")


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _fmt_tokens(n):
    """Human-readable token count."""
    n = int(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_token_tracker():
    """Load token-tracker.json via expanduser. Returns dict or empty dict."""
    if not os.path.isfile(TOKEN_TRACKER_PATH):
        return {}
    try:
        with open(TOKEN_TRACKER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_quota():
    """Load openrouter-quota.json via expanduser. Returns dict or None."""
    if not os.path.isfile(OPENROUTER_QUOTA_PATH):
        return None
    try:
        with open(OPENROUTER_QUOTA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_by_model(data):
    """Return list of model dicts sorted by total cost desc, then calls desc."""
    models = data.get("models", [])
    result = []
    for m in models:
        result.append({
            "provider": m.get("provider", "unknown"),
            "model": m.get("model", "unknown"),
            "calls": _safe_int(m.get("calls")),
            "total_tokens": _safe_int(m.get("total")),
            "prompt_tokens": _safe_int(m.get("prompt")),
            "completion_tokens": _safe_int(m.get("completion")),
            "cache_read_tokens": _safe_int(m.get("cache_read")),
            "cost": _safe_float(m.get("cost")),
        })
    result.sort(key=lambda x: (-x["cost"], -x["calls"]))
    return result


def aggregate_by_provider(data):
    """Aggregate model rows into per-provider totals."""
    by_model = aggregate_by_model(data)
    providers = {}
    for m in by_model:
        p = m["provider"]
        if p not in providers:
            providers[p] = {
                "provider": p,
                "calls": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "models": [],
            }
        providers[p]["calls"] += m["calls"]
        providers[p]["total_tokens"] += m["total_tokens"]
        providers[p]["cost"] = round(providers[p]["cost"] + m["cost"], 6)
        providers[p]["models"].append(m["model"])
    result = list(providers.values())
    result.sort(key=lambda x: -x["cost"])
    return result


def budget_summary(quota, data):
    """Build a budget summary line from quota data and tracker totals."""
    if quota is None:
        return {
            "credits_remaining": None,
            "credit_limit": None,
            "credit_percent": None,
            "budget_status": "UNKNOWN",
            "free_remaining": None,
            "free_limit": None,
            "usage_daily": None,
            "usage_weekly": None,
            "usage_monthly": None,
            "projected_days": None,
        }

    credits = _safe_float(quota.get("credits_remaining"))
    limit = _safe_float(quota.get("credit_limit"))
    daily = _safe_float(quota.get("usage_daily"))
    weekly = _safe_float(quota.get("usage_weekly"))
    monthly = _safe_float(quota.get("usage_monthly"))

    # Use the most authoritative daily figure available
    # If usage_daily is 0, estimate from weekly/monthly
    effective_daily = daily
    if effective_daily <= 0 and weekly > 0:
        effective_daily = weekly / 7.0
    if effective_daily <= 0 and monthly > 0:
        effective_daily = monthly / 30.0

    projected_days = None
    if effective_daily > 0 and credits > 0:
        projected_days = round(credits / effective_daily, 1)

    return {
        "credits_remaining": round(credits, 6),
        "credit_limit": round(limit, 4) if limit > 0 else None,
        "credit_percent": round(_safe_float(quota.get("credit_percent_remaining")), 1),
        "budget_status": quota.get("budget_status", "UNKNOWN"),
        "free_remaining": _safe_int(quota.get("free_remaining")),
        "free_limit": _safe_int(quota.get("free_limit")),
        "usage_daily": round(daily, 6),
        "usage_weekly": round(weekly, 6),
        "usage_monthly": round(monthly, 6),
        "projected_days": projected_days,
    }


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _print_table(models, budget, top_n=None):
    """Print a formatted table of model usage + budget summary."""
    if not models:
        print("  (no usage data)")
        return

    rows = models[:top_n] if top_n else models

    # Header
    hdr = f"{'Provider':<14} {'Model':<42} {'Calls':>7} {'Tokens':>10} {'Cost':>8}"
    print(hdr)
    print("-" * len(hdr))

    total_calls = 0
    total_tokens = 0
    total_cost = 0.0

    for m in rows:
        total_calls += m["calls"]
        total_tokens += m["total_tokens"]
        total_cost += m["cost"]
        print(
            f"{m['provider']:<14} {m['model']:<42} {m['calls']:>7,} "
            f"{_fmt_tokens(m['total_tokens']):>10} ${m['cost']:>7.4f}"
        )

    print("-" * len(hdr))
    print(
        f"{'TOTAL':<14} {'':<42} {total_calls:>7,} "
        f"{_fmt_tokens(total_tokens):>10} ${total_cost:>7.4f}"
    )

    # Budget line
    if budget:
        status = budget["budget_status"]
        cr = budget["credits_remaining"]
        cl = budget["credit_limit"]
        pct = budget["credit_percent"]
        free_r = budget["free_remaining"]
        free_l = budget["free_limit"]
        proj = budget["projected_days"]

        credit_str = f"${cr:.4f}/${cl:.2f}" if cl is not None else f"${cr:.4f}"
        pct_str = f" ({pct}%)" if pct is not None else ""
        free_str = f"{free_r}/{free_l} free" if free_r is not None else "free: ?"
        proj_str = f"~{proj}d left" if proj is not None else "proj: N/A"
        daily = budget["usage_daily"]
        daily_str = f"daily ${daily:.4f}" if daily and daily > 0 else "daily $0"

        print(
            f"\n  Budget: {status} | {credit_str}{pct_str} | "
            f"{free_str} | {daily_str} | {proj_str}"
        )


def _print_provider_table(providers, top_n=None):
    """Print per-provider aggregation table."""
    if not providers:
        print("  (no provider data)")
        return

    rows = providers[:top_n] if top_n else providers

    hdr = f"{'Provider':<14} {'Calls':>7} {'Tokens':>10} {'Cost':>8}"
    print(hdr)
    print("-" * len(hdr))

    total_calls = 0
    total_tokens = 0
    total_cost = 0.0

    for p in rows:
        total_calls += p["calls"]
        total_tokens += p["total_tokens"]
        total_cost += p["cost"]
        print(
            f"{p['provider']:<14} {p['calls']:>7,} "
            f"{_fmt_tokens(p['total_tokens']):>10} ${p['cost']:>7.4f}"
        )

    print("-" * len(hdr))
    print(
        f"{'TOTAL':<14} {total_calls:>7,} "
        f"{_fmt_tokens(total_tokens):>10} ${total_cost:>7.4f}"
    )


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _json_output(data, quota, budget):
    """Build the full JSON report payload."""
    grand = data.get("grand_total", {})
    models = aggregate_by_model(data)
    providers = aggregate_by_provider(data)

    return {
        "grand_total": {
            "calls": _safe_int(grand.get("calls")),
            "total_tokens": _safe_int(grand.get("total")),
            "prompt_tokens": _safe_int(grand.get("prompt")),
            "completion_tokens": _safe_int(grand.get("completion")),
            "cache_read_tokens": _safe_int(grand.get("cache_read")),
            "cost": _safe_float(grand.get("cost")),
        },
        "per_model": models,
        "per_provider": [
            {k: v for k, v in p.items() if k != "models"}
            for p in providers
        ],
        "quota": budget,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="R.E.Y. Usage Report"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--top", "-n", type=int, default=None,
        help="Show only the top N models"
    )
    parser.add_argument(
        "--daily", action="store_true", default=False,
        help="Focus on daily usage"
    )
    parser.add_argument(
        "--weekly", action="store_true", default=False,
        help="Focus on weekly usage"
    )
    parser.add_argument(
        "--monthly", action="store_true", default=False,
        help="Focus on monthly usage"
    )
    parser.add_argument(
        "--providers", "-p", action="store_true", default=False,
        help="Show per-provider aggregation only"
    )
    args = parser.parse_args()

    data = load_token_tracker()
    quota = load_quota()

    if not data:
        if args.json:
            print(json.dumps({"error": "token-tracker.json not found or empty"}, indent=2))
        else:
            print("R.E.Y. Report: token-tracker.json not found or empty.")
        return 1

    budget = budget_summary(quota, data)

    # --json mode: output valid JSON and exit
    if args.json:
        payload = _json_output(data, quota, budget)
        print(json.dumps(payload, indent=2))
        return 0

    # Human-readable output
    grand = data.get("grand_total", {})
    last_updated = data.get("last_updated", "unknown")

    print(f"\n{'=' * 72}")
    print(f"  R.E.Y. USAGE REPORT  ({last_updated})")
    print(f"{'=' * 72}\n")

    # Grand total header
    gt_calls = _safe_int(grand.get("calls"))
    gt_tokens = _safe_int(grand.get("total"))
    gt_cost = _safe_float(grand.get("cost"))
    print(f"  Grand Total: {gt_calls:,} calls | {_fmt_tokens(gt_tokens)} tokens | ${gt_cost:.4f}")

    # Usage window hint
    if budget:
        usage = None
        label = ""
        if args.daily and budget.get("usage_daily") is not None:
            usage = budget["usage_daily"]
            label = "today"
        elif args.weekly and budget.get("usage_weekly") is not None:
            usage = budget["usage_weekly"]
            label = "this week"
        elif args.monthly and budget.get("usage_monthly") is not None:
            usage = budget["usage_monthly"]
            label = "this month"
        elif budget.get("usage_monthly") and budget["usage_monthly"] > 0:
            usage = budget["usage_monthly"]
            label = "this month (from quota)"

        if usage is not None and usage > 0:
            print(f"  OpenRouter spend {label}: ${usage:.4f}")

    print()

    models = aggregate_by_model(data)
    providers = aggregate_by_provider(data)

    if args.providers:
        print("  Per-Provider Summary")
        print(f"  {'-' * 68}")
        _print_provider_table(providers, args.top)
    else:
        print("  Model Usage (sorted by cost)")
        print(f"  {'-' * 68}")
        _print_table(models, budget, args.top)

    print(f"\n{'=' * 72}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
