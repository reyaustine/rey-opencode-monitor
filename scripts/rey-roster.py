#!/usr/bin/env python3
"""Generate optimal team roster assignments based on BYOK configuration."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

CONFIG_DIR = Path.home() / '.config' / 'opencode'
BYOK_CONFIG = CONFIG_DIR / 'byok-config.json'

ROSTER_RULES = {
    'openrouter': {
        'coder':     {'model': 'deepseek/deepseek-chat',            'reason': 'Best code generation value'},
        'reviewer':  {'model': 'anthropic/claude-sonnet-4',         'reason': 'Thorough code review'},
        'planner':   {'model': 'anthropic/claude-sonnet-4',         'reason': 'Strong architectural planning'},
        'researcher':{'model': 'google/gemini-2.5-flash',           'reason': 'Fast research with large context'},
        'debugger':  {'model': 'deepseek/deepseek-r1',              'reason': 'Chain-of-thought debugging'},
    },
    'groq': {
        'coder':     {'model': 'llama-3.3-70b-versatile',          'reason': 'Fast code generation'},
        'reviewer':  {'model': 'llama-3.3-70b-versatile',          'reason': 'Quick review cycles'},
        'planner':   {'model': 'llama-3.3-70b-versatile',          'reason': 'Rapid planning iterations'},
        'researcher':{'model': 'llama-3.1-8b-instant',             'reason': 'Blazing fast research'},
        'debugger':  {'model': 'llama-3.3-70b-versatile',          'reason': 'Fast debugging loops'},
    },
    'gemini': {
        'coder':     {'model': 'gemini-2.5-flash',                 'reason': 'Fast, capable coding'},
        'reviewer':  {'model': 'gemini-2.5-pro',                   'reason': 'Deep review with large context'},
        'planner':   {'model': 'gemini-2.5-pro',                   'reason': 'Strong planning with 1M context'},
        'researcher':{'model': 'gemini-2.5-flash',                 'reason': 'Fast research, huge context window'},
        'debugger':  {'model': 'gemini-2.5-flash',                 'reason': 'Quick debug iterations'},
    },
    'claude': {
        'coder':     {'model': 'claude-sonnet-4-20250514',         'reason': 'Best-in-class code generation'},
        'reviewer':  {'model': 'claude-sonnet-4-20250514',         'reason': 'Thorough, nuanced review'},
        'planner':   {'model': 'claude-opus-4-20250514',           'reason': 'Deep architectural thinking'},
        'researcher':{'model': 'claude-sonnet-4-20250514',         'reason': 'Comprehensive research'},
        'debugger':  {'model': 'claude-sonnet-4-20250514',         'reason': 'Systematic root cause analysis'},
    },
    'chatgpt': {
        'coder':     {'model': 'gpt-4.1',                          'reason': 'Strong coding across languages'},
        'reviewer':  {'model': 'o3',                                'reason': 'Reasoning-heavy review'},
        'planner':   {'model': 'o3',                                'reason': 'Strategic planning'},
        'researcher':{'model': 'gpt-4.1-mini',                     'reason': 'Fast, affordable research'},
        'debugger':  {'model': 'o3',                                'reason': 'Deep reasoning for hard bugs'},
    },
    'opencode': {
        'coder':     {'model': 'opencode/auto',                    'reason': 'Self-hosted, zero-latency local inference'},
        'reviewer':  {'model': 'opencode/auto',                    'reason': 'Local code review, no API cost'},
        'planner':   {'model': 'opencode/auto',                    'reason': 'Local planning, data stays on machine'},
        'researcher':{'model': 'opencode/auto',                    'reason': 'Unlimited local research'},
        'debugger':  {'model': 'opencode/auto',                    'reason': 'Local debugging, offline capable'},
    },
    'kilo': {
        'coder':     {'model': 'kilo/auto',                        'reason': 'Free-tier AI coding agent'},
        'reviewer':  {'model': 'kilo/auto',                        'reason': 'Fast review cycles'},
        'planner':   {'model': 'kilo/auto',                        'reason': 'Rapid planning iterations'},
        'researcher':{'model': 'kilo/auto',                        'reason': 'Free research assistant'},
        'debugger':  {'model': 'kilo/auto',                        'reason': 'Free debugging agent'},
    },
}

ROLE_PRIORITY = ['claude', 'chatgpt', 'openrouter', 'gemini', 'groq', 'opencode', 'kilo']


def generate_roster(byok_config):
    """Generate optimal roster assignments based on enabled providers."""
    providers = byok_config.get('providers', {})
    enabled = [
        pid for pid, pval in providers.items()
        if isinstance(pval, dict) and pval.get('enabled', False)
    ]

    if not enabled:
        return {'error': 'No providers enabled', 'roster': {}}

    roles = ['coder', 'reviewer', 'planner', 'researcher', 'debugger']
    roster = {}

    for role in roles:
        assigned = False
        for provider_id in ROLE_PRIORITY:
            if provider_id in enabled and provider_id in ROSTER_RULES:
                if role in ROSTER_RULES[provider_id]:
                    roster[role] = {
                        'provider': provider_id,
                        'model': ROSTER_RULES[provider_id][role]['model'],
                        'reason': ROSTER_RULES[provider_id][role]['reason'],
                    }
                    assigned = True
                    break

        if not assigned:
            # Fallback: use first enabled provider's model for this role
            for provider_id in enabled:
                if provider_id in ROSTER_RULES and role in ROSTER_RULES[provider_id]:
                    roster[role] = {
                        'provider': provider_id,
                        'model': ROSTER_RULES[provider_id][role]['model'],
                        'reason': ROSTER_RULES[provider_id][role]['reason'] + ' (fallback)',
                    }
                    assigned = True
                    break

            if not assigned:
                roster[role] = {'provider': '', 'model': '', 'reason': 'No provider available'}

    return {
        'ok': True,
        'generated_at': datetime.now().isoformat(),
        'enabled_providers': enabled,
        'roster': roster,
    }


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
