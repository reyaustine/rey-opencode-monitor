import os
import sys
import json
import time
import sqlite3
from pathlib import Path

def get_db_path():
    user_home = os.path.expanduser('~')
    user_profile = os.environ.get('USERPROFILE', user_home)
    candidates = [
        os.path.join(user_home, '.local', 'share', 'opencode', 'opencode.db'),
        os.path.join(user_home, 'Library', 'Application Support', 'opencode', 'opencode.db'),
        os.path.join(user_profile, '.local', 'share', 'opencode', 'opencode.db'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def extract_model_label(model_raw, default_provider='opencode'):
    if not model_raw:
        return '-'
    try:
        data = json.loads(model_raw)
        provider = data.get('providerID', default_provider)
        mid = data.get('id', '')
        if provider and mid:
            return f"{provider}/{mid}"
        return mid or str(data)
    except Exception:
        return str(model_raw)

import socket

def fmt_tokens(n):
    if n is None:
        return '0'
    n = float(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))

def get_token_tracker_data(conn):
    try:
        query = """
        SELECT 
            coalesce(json_extract(data, '$.providerID'), 'unknown') as provider,
            coalesce(json_extract(data, '$.modelID'), 'unknown') as model,
            sum(coalesce(json_extract(data, '$.tokens.input'), 0)) as inp,
            sum(coalesce(json_extract(data, '$.tokens.output'), 0)) as outp,
            sum(coalesce(json_extract(data, '$.tokens.reasoning'), 0)) as rsn,
            sum(coalesce(json_extract(data, '$.tokens.cache.read'), 0)) as cache_read,
            sum(coalesce(json_extract(data, '$.tokens.cache.write'), 0)) as cache_write,
            sum(coalesce(json_extract(data, '$.tokens.total'), 0)) as total,
            sum(coalesce(json_extract(data, '$.cost'), 0.0)) as total_cost,
            count(*) as calls
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
        GROUP BY provider, model
        ORDER BY total DESC;
        """
        c = conn.cursor()
        c.execute(query)
        rows = c.fetchall()

        inp_total = sum(r[2] for r in rows)
        outp_total = sum(r[3] for r in rows)
        rsn_total = sum(r[4] for r in rows)
        cache_read_total = sum(r[5] for r in rows)
        cache_write_total = sum(r[6] for r in rows)
        grand_total = sum(r[7] for r in rows)
        cost_total = sum(r[8] for r in rows)
        calls_total = sum(r[9] for r in rows)

        models = []
        for r in rows:
            provider, model, inp, outp, rsn, cr, cw, tot, cost, calls = r
            if tot > 0 or inp > 0 or outp > 0:
                models.append({
                    'provider': provider,
                    'model': model,
                    'prompt': inp,
                    'prompt_fmt': fmt_tokens(inp),
                    'completion': outp,
                    'completion_fmt': fmt_tokens(outp),
                    'reasoning': rsn,
                    'reasoning_fmt': fmt_tokens(rsn),
                    'cache_read': cr,
                    'cache_read_fmt': fmt_tokens(cr),
                    'total': tot,
                    'total_fmt': fmt_tokens(tot),
                    'cost': round(cost, 4),
                    'calls': calls
                })

        hostname = socket.gethostname()
        username = os.environ.get('USERNAME', os.environ.get('USER', 'user'))

        tracker_payload = {
            'machine': hostname,
            'user': username,
            'last_updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'grand_total': {
                'total': grand_total,
                'total_fmt': fmt_tokens(grand_total),
                'prompt': inp_total,
                'prompt_fmt': fmt_tokens(inp_total),
                'completion': outp_total,
                'completion_fmt': fmt_tokens(outp_total),
                'reasoning': rsn_total,
                'reasoning_fmt': fmt_tokens(rsn_total),
                'cache_read': cache_read_total,
                'cache_read_fmt': fmt_tokens(cache_read_total),
                'cost': round(cost_total, 4),
                'calls': calls_total
            },
            'models': models
        }

        # Save to local machine config folder (~/.config/opencode/token-tracker.json)
        try:
            conf_dir = os.path.expanduser('~/.config/opencode')
            os.makedirs(conf_dir, exist_ok=True)
            tracker_file = os.path.join(conf_dir, 'token-tracker.json')
            with open(tracker_file, 'w', encoding='utf-8') as f:
                json.dump(tracker_payload, f, indent=2)
        except Exception:
            pass

        return tracker_payload
    except Exception:
        return {
            'machine': socket.gethostname(),
            'grand_total': {
                'total': 0, 'total_fmt': '0', 'prompt': 0, 'prompt_fmt': '0',
                'completion': 0, 'completion_fmt': '0', 'cost': 0.0, 'calls': 0
            },
            'models': []
        }

def get_state():
    db_path = get_db_path()
    result = {
        'ok': True,
        'db_found': bool(db_path),
        'active_threads': 0,
        'overall_activity': 'IDLE',
        'current_workspace': '-',
        'sessions': [],
        'tokens': None
    }
    
    if not db_path:
        return result

    try:
        uri = f"file:{Path(db_path).as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        now_ms = int(time.time() * 1000)

        rows = conn.execute('''
            SELECT id, title, directory, agent, model, time_updated, cost
            FROM session
            ORDER BY time_updated DESC
            LIMIT 10
        ''').fetchall()

        sessions = []
        active_count = 0

        for r in rows:
            sid = r['id']
            time_updated = r['time_updated'] or 0
            age_s = max(0.0, (now_ms - time_updated) / 1000.0)
            directory = r['directory'] or ''
            ws_name = os.path.basename(directory.rstrip('/\\')) if directory else '-'

            # Parse model & agent
            model_label = extract_model_label(r['model'])
            agent_name = r['agent'] or 'build'

            # Inspect latest message and parts
            state = 'DONE'
            last_msg = conn.execute('''
                SELECT id, time_created, time_updated, data
                FROM message
                WHERE session_id = ?
                ORDER BY time_created DESC
                LIMIT 1
            ''', (sid,)).fetchone()

            if last_msg:
                mdata = {}
                if last_msg['data']:
                    try:
                        mdata = json.loads(last_msg['data'])
                    except Exception:
                        pass

                role = mdata.get('role', 'assistant')
                if mdata.get('agent'):
                    agent_name = mdata.get('agent')
                if mdata.get('model'):
                    model_label = extract_model_label(json.dumps(mdata.get('model')))

                parts = conn.execute('''
                    SELECT id, data
                    FROM part
                    WHERE message_id = ?
                    ORDER BY time_created DESC
                    LIMIT 8
                ''', (last_msg['id'],)).fetchall()

                has_finish = False
                has_running = False

                for p in parts:
                    if not p['data']:
                        continue
                    try:
                        pdata = json.loads(p['data'])
                    except Exception:
                        continue

                    ptype = pdata.get('type')
                    preason = pdata.get('reason')
                    if ptype == 'step-finish' and preason in ('stop', 'complete', 'end_turn', 'tool-calls'):
                        if preason != 'tool-calls':
                            has_finish = True

                    pstate = pdata.get('state')
                    if isinstance(pstate, dict):
                        status = pstate.get('status')
                        if status in ('running', 'pending'):
                            has_running = True

                if role == 'user' and age_s < 120:
                    state = 'WORKING'
                elif has_running and age_s < 180:
                    state = 'WORKING'
                elif not has_finish and age_s < 90:
                    state = 'WORKING'
                else:
                    state = 'DONE'

            if state == 'WORKING':
                active_count += 1

            sessions.append({
                'id': sid,
                'short_id': sid[:14] if len(sid) >= 14 else sid,
                'title': r['title'] or '(untitled)',
                'workspace': ws_name,
                'directory': directory,
                'agent': agent_name,
                'model': model_label,
                'cost': round(float(r['cost'] or 0.0), 4),
                'state': state,
                'age_s': round(age_s, 1),
                'updated_ms': time_updated
            })

        result['active_threads'] = active_count
        result['overall_activity'] = 'THINKING' if active_count > 0 else 'IDLE'
        if sessions:
            result['current_workspace'] = sessions[0]['workspace']
        result['sessions'] = sessions
        result['tokens'] = get_token_tracker_data(conn)

        # Check for active model override lock
        user_home = os.path.expanduser('~')
        override_lock_path = os.path.join(user_home, '.config', 'opencode', 'override-lock.json')
        result['override_model'] = None
        if os.path.exists(override_lock_path):
            try:
                with open(override_lock_path, 'r', encoding='utf-8') as lf:
                    ldata = json.load(lf)
                    ov_model = ldata.get('model')
                    if ov_model and ldata.get('active', True):
                        result['override_model'] = ov_model
                        # Active cleansing: enforce on any session with muse-spark
                        ov_parts = ov_model.split('/', 1)
                        ov_prov = ov_parts[0] if len(ov_parts) == 2 else 'openrouter'
                        ov_id = ov_parts[1] if len(ov_parts) == 2 else ov_model
                        new_m = json.dumps({"id": ov_id, "providerID": ov_prov, "variant": "default"})
                        conn.execute("UPDATE session SET model = ? WHERE model LIKE '%muse-spark%'", (new_m,))
                        conn.commit()
            except Exception:
                pass

        conn.close()
    except Exception as e:
        result['ok'] = False
        result['error'] = str(e)

    return result

if __name__ == '__main__':
    print(json.dumps(get_state()))
