import os
import sys
import json
import time
import sqlite3
from pathlib import Path

def get_db_path():
    user_profile = os.environ.get('USERPROFILE', '')
    candidates = [
        os.path.join(user_profile, '.local', 'share', 'opencode', 'opencode.db'),
        os.path.expanduser('~/.local/share/opencode/opencode.db'),
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

def get_state():
    db_path = get_db_path()
    result = {
        'ok': True,
        'db_found': bool(db_path),
        'active_threads': 0,
        'overall_activity': 'IDLE',
        'current_workspace': '-',
        'sessions': []
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
        conn.close()
    except Exception as e:
        result['ok'] = False
        result['error'] = str(e)

    return result

if __name__ == '__main__':
    print(json.dumps(get_state()))
