#!/usr/bin/env python3
"""End-to-end API test against stepper_emu.py (no EPICS, no live firing).

Usage: FLASH_SERIAL_PORT=<emu pty> app.py ...; api_test.py BASE_URL [deny sim abort assisted]
"""
import json
import sys
import time
import urllib.request

import socketio

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:18081'
WHICH = sys.argv[2:] or ['deny', 'sim', 'abort', 'assisted']


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


sio = socketio.Client()
events = []
sio.on('run_event', lambda ev: events.append(ev))
sio.connect(BASE, transports=['polling'])
sio.emit('send_command', {'command': 'ENABLE 0'})
sio.emit('send_command', {'command': 'ENABLE 1'})
time.sleep(1.5)
print('access', call('POST', '/run/api/access', {'x': -2000, 'y': 40000}))

lo = call('GET', '/motion/api/loadout')[1]
print('loadout sections', lo['sections'])
# 4x3 plate in S1: wells are 15838 steps apart
stops = [
    {'id': '1:A1', 'label': 'S1-A1', 'x': 0, 'y': 31675, 'pulses': 3, 'delay': 0.5},
    {'id': '1:C4', 'label': 'S1-C4', 'x': 47513, 'y': 0, 'pulses': 2, 'delay': 0.2},
    {'id': '1:B2', 'label': 'S1-B2', 'x': 15838, 'y': 15838, 'pulses': 1, 'delay': 1},
]


def wait_state(states, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = call('GET', '/run/api/status')[1]
        if s['state'] in states:
            return s
        time.sleep(0.5)
    raise SystemExit(f'timeout waiting for {states}; last {s["state"]} {s["run"] and s["run"]["message"]}')


def plan():
    code, r = call('POST', '/run/api/plan', {'stops': stops})
    assert code == 200, r
    p = r['plan']
    print('plan order', [s['id'] for s in p['stops']], 'est', p['est_total_s'], 's')
    return p


if 'deny' in WHICH:
    hs = {'X-Real-IP': '192.168.50.23'}
    print('hotspot plan ->', call('POST', '/run/api/plan', {'stops': stops}, hs))
    print('hotspot abort ->', call('POST', '/run/api/abort', {}, hs))
    print('validation ->', call('POST', '/run/api/plan', {'stops': [dict(stops[0], pulses=0)]}))

if 'sim' in WHICH:
    p = plan()
    print('start sim', call('POST', '/run/api/start', {'plan_id': p['plan_id'], 'mode': 'simulate'})[0])
    print('blocked cmd test'); sio.emit('send_command', {'command': 'MOVE 0 100'})
    s = wait_state(('done', 'failed', 'aborted'))
    print('SIM ->', s['state'], s['run']['message'], s['run']['pulses_done'])
    print('restart old plan ->', call('POST', '/run/api/start', {'plan_id': p['plan_id'], 'mode': 'simulate'}))

if 'abort' in WHICH:
    p = plan()
    call('POST', '/run/api/start', {'plan_id': p['plan_id'], 'mode': 'simulate'})
    time.sleep(2.5)
    print('abort ->', call('POST', '/run/api/abort', {}))
    s = wait_state(('aborted', 'failed', 'done'), 20)
    time.sleep(3)
    st = call('GET', '/motion/api/state')[1]['stepper']
    print('ABORT ->', s['state'], s['run']['message'], 'speed now', st['speed'])

if 'assisted' in WHICH:
    p = plan()
    call('POST', '/run/api/start', {'plan_id': p['plan_id'], 'mode': 'assisted'})
    for action in ('fired', 'skip', 'fired'):
        s = wait_state(('waiting_operator', 'failed', 'aborted'), 120)
        print('  operator sees:', s['run']['operator_command'])
        print('  continue', action, call('POST', '/run/api/continue', {'action': action})[0])
        time.sleep(0.5)
    s = wait_state(('done', 'failed', 'aborted'))
    print('ASSISTED ->', s['state'], s['run']['stop_state'])

sio.disconnect()
