#!/usr/bin/env python3
"""
R.E.Y. // Team Roster Generator
Assigns optimal models to agent roles based on live-discovered models.
Reads live-models.json (from rey-models.py) and picks the best model per role.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

CONFIG_DIR = Path.home() / '.config' / 'opencode'
BYOK_CONFIG = CONFIG_DIR / 'byok-config.json'
LIVE_MODELS = CONFIG_DIR / 'live-models.json'

# ── Role scoring rules ──────────────────────────────────────────────────────
# Keywords that indicate a model is good for a specific role.
# Score: higher = better fit. 0 = not a match.

ROLE_KEYWORDS = {
    'coder': {
        'high': ['deepseek-chat', 'deepseek-coder', 'codestral', 'gpt-4.1', 'claude-sonnet', 'gemini-3.6-flash', 'llama-3.3-70b'],
        'medium': ['gemini-3.1-flash-lite', 'gpt-4o', 'claude-haiku', 'llama-3.1-8b'],
        'low': ['kilo', 'opencode'],
    },
    'reviewer': {
        'high': ['claude-sonnet', 'o3', 'gemini-3.6-flash', 'deepseek-r1'],
        'medium': ['gpt-4.1', 'llama-3.3-70b', 'gemini-3.1-flash-lite'],
        'low': ['kilo', 'opencode'],
    },
    'planner': {
        'high': ['claude-opus', 'o3', 'gemini-3.6-flash'],
        'medium': ['claude-sonnet', 'gpt-4.1', 'deepseek-chat'],
        'low': ['kilo', 'opencode'],
    },
    'researcher': {
        'high': ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gpt-4.1-mini', 'llama-3.1-8b-instant'],
        'medium': ['gemini-3.1-flash-lite', 'claude-sonnet', 'deepseek-chat'],
        'low': ['kilo', 'opencode'],
    },
    'debugger': {
        'high': ['deepseek-r1', 'o3', 'claude-sonnet'],
        'medium': ['gpt-4.1', 'gemini-3.6-flash', 'llama-3.3-70b'],
        'low': ['kilo', 'opencode'],
    },
}

# Provider priority (when multiple providers have equally good models)
PROVIDER_PRIORITY = ['claude', 'chatgpt', 'openrouter', 'gemini', 'groq', 'opencode', 'kilo']

ROLES = ['coder', 'reviewer', 'planner', 'researcher', 'debugger']


def score_model_for_role(model_id, role):
    """Score a model for a given role based on keyword matching."""
    model_lower = model_id.lower()
    keywords = ROLE_KEYWORDS.get(role, {})

    for kw in keywords.get('high', []):
        if kw in model_lower:
            return 100
    for kw in keywords.get('medium', []):
        if kw in model_lower:
            return 50
    for kw in keywords.get('low', []):
        if kw in model_lower:
            return 10

    # Default: larger context = slightly better
    return 5


def load_circuit_breaker():
    """Load current quarantined models and providers."""
    cb_path = CONFIG_DIR / 'circuit-breaker.json'
    if cb_path.exists():
        try:
            with open(cb_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'models': set(data.get('quarantined_models', {}).keys()),
                    'providers': set(data.get('quarantined_providers', {}).keys())
                }
        except Exception:
            pass
    return {'models': set(), 'providers': set()}


def generate_roster_from_live(live_models_data):
    """Generate roster from live-discovered models, excluding quarantined models and providers."""
    cb = load_circuit_breaker()
    quarantined_models = cb['models']
    quarantined_providers = cb['providers']

    providers = live_models_data.get('providers', {})
    
    # Filter enabled providers: exclude any provider in quarantined_providers
    enabled = [
        pid for pid, p in providers.items() 
        if p.get('ok', False) 
        and pid.lower() not in quarantined_providers
        and len(p.get('models', [])) > 0
    ]

    if not enabled:
        return {'error': 'No healthy providers available (all unconfigured or quarantined)', 'roster': {}}

    roster = {}

    for role in ROLES:
        best_score = -1
        best_model = None
        best_provider = None

        # Scan all enabled providers for the best model
        for provider_id in PROVIDER_PRIORITY:
            if provider_id not in enabled or provider_id.lower() in quarantined_providers:
                continue

            prov_models = providers[provider_id].get('models', [])
            for m in prov_models:
                mid = m.get('id', '')
                full_mid = f"{provider_id}/{mid}" if "/" not in mid else mid
                
                # Exclude quarantined models!
                # (User rule: exclude the model, but provider remains if other models work)
                if mid in quarantined_models or full_mid in quarantined_models:
                    continue

                score = score_model_for_role(mid, role)

                # Apply provider priority as tiebreaker
                prov_idx = PROVIDER_PRIORITY.index(provider_id) if provider_id in PROVIDER_PRIORITY else 99
                score += (10 - prov_idx)  # Higher priority provider gets small bonus

                if score > best_score:
                    best_score = score
                    best_model = m
                    best_provider = provider_id

        if best_model:
            # Determine why this model was chosen
            reason = _get_role_reason(role, best_provider, best_model)
            roster[role] = {
                'provider': best_provider,
                'model': best_model['id'],
                'model_name': best_model.get('name', best_model['id']),
                'context_length': best_model.get('context_length', 0),
                'pricing': best_model.get('pricing', 'unknown'),
                'reason': reason,
            }
        else:
            roster[role] = {'provider': '', 'model': '', 'reason': 'No healthy model available for role'}

    return {
        'ok': True,
        'generated_at': datetime.now().isoformat(),
        'enabled_providers': enabled,
        'quarantined_models': list(quarantined_models),
        'quarantined_providers': list(quarantined_providers),
        'roster': roster,
        'tier': live_models_data.get('tier', 'unknown'),
    }


def _get_role_reason(role, provider, model):
    """Generate a human-readable reason for the assignment."""
    mid = model.get('id', '')
    pricing = model.get('pricing', 'unknown')

    reasons = {
        'coder':      f'Best code generation fit from {provider}',
        'reviewer':   f'Strong reasoning for code review from {provider}',
        'planner':    f'Deep thinking for architecture from {provider}',
        'researcher': f'Fast research capability from {provider}',
        'debugger':   f'Systematic debugging from {provider}',
    }
    base = reasons.get(role, f'Optimal for {role}')
    if pricing == 'free':
        base += ' (free)'
    return base


def generate_roster(byok_config):
    """Generate optimal roster assignments — tries live models first, falls back to static."""
    # Try live models first
    if LIVE_MODELS.exists():
        try:
            with open(LIVE_MODELS, 'r', encoding='utf-8') as f:
                live_data = json.load(f)
            if live_data.get('ok'):
                return generate_roster_from_live(live_data)
        except Exception:
            pass

    # Fallback: use BYOK config directly (no live models available)
    providers = byok_config.get('providers', {})
    enabled = [pid for pid, pval in providers.items() if isinstance(pval, dict) and pval.get('enabled', False)]

    if not enabled:
        return {'error': 'No providers enabled', 'roster': {}}

    return {'error': 'No live models available — run model discovery first', 'roster': {}}


if __name__ == '__main__':
    try:
        if not BYOK_CONFIG.exists():
            print(json.dumps({'error': 'byok-config.json not found'}))
            sys.exit(1)

        with open(BYOK_CONFIG, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)

        result = generate_roster(config)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
