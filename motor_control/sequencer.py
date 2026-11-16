"""Automatic position-and-fire runs.

plan_path()  orders the selected targets: nearest-neighbour then 2-opt, with the
             start fixed at the current position and the end fixed at the access
             (park) position. Cost = move time, i.e. the slower of the two axes,
             each moving with the controller's trapezoid profile.

Sequencer    executes a plan: move -> confirm arrival -> settle -> fire N pulses
             with the delay -> next ... -> back to access. Abort sends STOP ALL
             and ends the run where it is (it does not drive anywhere).

The ESP32 has no "move done" message, so arrival is confirmed by polling UPDATE
until both axes report the target position with zero speed.
"""

import json
import math
import os
import time
import urllib.request
import uuid

import gevent
from gevent.event import Event

from firing import FIRE_PV, MODES, repeatput_command, value_label

DEFAULT_VMAX = 3200.0      # steps/s  (flashed settings, 2026-10-26)
DEFAULT_ACCEL = 1600.0     # steps/s^2
DOSECAM_URL = os.environ.get('FLASH_DOSECAM_URL', 'http://127.0.0.1:8000')
MAX_PULSES = 10000
MAX_DELAY_S = 3600.0
MAX_ABS_STEPS = 5_000_000


# --------------------------------------------------------------------------
# path planning
# --------------------------------------------------------------------------
def axis_time(distance, vmax, accel):
    d = abs(distance)
    if d == 0:
        return 0.0
    if d < vmax * vmax / accel:                 # never reaches full speed
        return 2.0 * math.sqrt(d / accel)
    return d / vmax + vmax / accel


def leg_time(p, q, vmax=DEFAULT_VMAX, accel=DEFAULT_ACCEL):
    return max(axis_time(q[0] - p[0], vmax, accel), axis_time(q[1] - p[1], vmax, accel))


def leg_cost(p, q, vmax=DEFAULT_VMAX, accel=DEFAULT_ACCEL):
    """Planning cost: move time (slower axis), plus a small share of the faster axis
    so that among equally fast routes the geometrically shorter one wins."""
    tx = axis_time(q[0] - p[0], vmax, accel)
    ty = axis_time(q[1] - p[1], vmax, accel)
    return max(tx, ty) + 0.02 * min(tx, ty)


def plan_path(start, stops, end, vmax=DEFAULT_VMAX, accel=DEFAULT_ACCEL):
    """Return stops reordered. start/end are (x, y); stops are dicts with x, y."""
    n = len(stops)
    if n == 0:
        return []
    pts = [(s['x'], s['y']) for s in stops]

    def c(a, b):
        return leg_cost(a, b, vmax, accel)

    # nearest neighbour from the start
    remaining = set(range(n))
    order, cur = [], start
    while remaining:
        nxt = min(remaining, key=lambda i: (c(cur, pts[i]), pts[i][1] * -1, pts[i][0]))
        order.append(nxt)
        remaining.discard(nxt)
        cur = pts[nxt]

    def total(o):
        seq = [start] + [pts[i] for i in o] + [end]
        return sum(c(a, b) for a, b in zip(seq, seq[1:]))

    if n <= 7:                                   # small: exact
        from itertools import permutations
        order = list(min(permutations(range(n)), key=total))
        return [stops[i] for i in order]

    # 2-opt (reverse a stretch) and or-opt (move a run of 1-3 stops), endpoints fixed,
    # until neither improves the route.
    def P(k):
        if k == 0:
            return start
        if k == n + 1:
            return end
        return pts[order[k - 1]]

    for _ in range(50):
        improved = False
        for i in range(1, n):
            for k in range(i + 1, n + 1):
                delta = (c(P(i - 1), P(k)) + c(P(i), P(k + 1))
                         - c(P(i - 1), P(i)) - c(P(k), P(k + 1)))
                if delta < -1e-6:
                    order[i - 1:k] = reversed(order[i - 1:k])
                    improved = True
        # or-opt with incremental cost (cost is symmetric, so a moved run's inside is unchanged)
        for seg in (1, 2, 3):
            i = 0
            while i + seg <= n:
                route = [start] + [pts[o] for o in order] + [end]
                a, f, l, b = route[i], route[i + 1], route[i + seg], route[i + seg + 1]
                gain = c(a, f) + c(l, b) - c(a, b)
                rest = route[:i + 1] + route[i + seg + 1:]
                best_delta, best = -1e-6, None
                for j in range(len(rest) - 1):
                    if j == i:
                        continue
                    p, q = rest[j], rest[j + 1]
                    base = c(p, q)
                    for rev, add in ((False, c(p, f) + c(l, q) - base), (True, c(p, l) + c(f, q) - base)):
                        if add - gain < best_delta:
                            best_delta, best = add - gain, (j, rev)
                if best:
                    j, rev = best
                    piece = order[i:i + seg][::-1] if rev else order[i:i + seg]
                    rest_order = order[:i] + order[i + seg:]
                    order = rest_order[:j] + piece + rest_order[j:]
                    improved = True
                i += 1
        if not improved:
            break
    return [stops[i] for i in order]


def validate_stops(raw):
    stops, seen = [], set()
    if not isinstance(raw, list) or not raw:
        raise ValueError('no target positions selected')
    for item in raw:
        sid = str(item.get('id', '')).strip()[:40]
        if not sid or sid in seen:
            raise ValueError(f'bad or duplicate target id {sid!r}')
        seen.add(sid)
        x, y = int(round(float(item['x']))), int(round(float(item['y'])))
        if abs(x) > MAX_ABS_STEPS or abs(y) > MAX_ABS_STEPS:
            raise ValueError(f'{sid}: position out of range')
        pulses = int(item.get('pulses', 1))
        delay = float(item.get('delay', 1.0))
        if not 1 <= pulses <= MAX_PULSES:
            raise ValueError(f'{sid}: pulses must be 1..{MAX_PULSES}')
        if not 0 <= delay <= MAX_DELAY_S or math.isnan(delay):
            raise ValueError(f'{sid}: delay must be 0..{MAX_DELAY_S:g} s')
        stops.append({'id': sid, 'label': str(item.get('label') or sid)[:40],
                      'x': x, 'y': y, 'pulses': pulses, 'delay': delay})
    return stops


def build_plan(start, stops, access, vmax, accel, settle_s):
    ordered = plan_path(start, stops, access, vmax, accel)
    legs, prev = [], start
    for s in ordered + [{'id': '__access__', 'x': access[0], 'y': access[1]}]:
        legs.append({'to': s['id'], 'from': list(prev), 'dest': [s['x'], s['y']],
                     'time_s': round(leg_time(prev, (s['x'], s['y']), vmax, accel), 2)})
        prev = (s['x'], s['y'])
    move_s = sum(l['time_s'] for l in legs)
    fire_s = sum((s['pulses'] - 1) * s['delay'] + settle_s + 0.1 * s['pulses'] for s in ordered)
    return {
        'plan_id': uuid.uuid4().hex[:12],
        'created': time.time(),
        'start': list(start),
        'access': list(access),
        'stops': ordered,
        'legs': legs,
        'vmax': vmax, 'accel': accel, 'settle_s': settle_s,
        'total_pulses': sum(s['pulses'] for s in ordered),
        'est_move_s': round(move_s, 1),
        'est_total_s': round(move_s + fire_s + 1.5 * len(legs), 1),
    }


# --------------------------------------------------------------------------
# DoseCam (optional per-position acquisition)
# --------------------------------------------------------------------------
def dosecam(method, path, body=None, timeout=5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(DOSECAM_URL + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode())
        except Exception:
            return {'ok': False, 'error': f'HTTP {exc.code}'}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


class RunAborted(Exception):
    pass


class RunFailed(Exception):
    pass


# --------------------------------------------------------------------------
# executor
# --------------------------------------------------------------------------
class Sequencer:
    def __init__(self, link, firing, emit, run_dir):
        self.link = link
        self.firing = firing
        self.emit = emit                    # emit(event_name, payload)
        self.run_dir = run_dir
        self.plan = None
        self.state = 'idle'                 # idle|running|waiting_operator|aborting|done|aborted|failed
        self.run = None
        self.events = []
        self.greenlet = None
        self.abort_evt = Event()
        self.operator_evt = Event()
        self.operator_action = None
        self._log_fh = None

    # ---- status ----------------------------------------------------------
    @property
    def active(self):
        return self.state in ('running', 'waiting_operator', 'aborting')

    def status(self):
        return {'state': self.state, 'plan': self.plan, 'run': self.run,
                'events': self.events[-200:]}

    def _push(self):
        self.emit('run_status', {'state': self.state, 'run': self.run,
                                 'plan_id': self.plan and self.plan['plan_id']})

    def log(self, kind, msg, **extra):
        ev = {'t': time.time(), 'kind': kind, 'msg': msg}
        ev.update(extra)
        self.events.append(ev)
        del self.events[:-500]
        if self._log_fh:
            try:
                self._log_fh.write(json.dumps(ev) + '\n')
                self._log_fh.flush()
            except Exception:
                pass
        print(f'run: [{kind}] {msg}', flush=True)
        self.emit('run_event', ev)

    # ---- planning --------------------------------------------------------
    def make_plan(self, raw_stops, access, settle_s=1.0):
        if self.active:
            raise ValueError('a run is in progress')
        if access is None:
            raise ValueError('access (park) position is not set')
        pos = self.link.state['pos']
        if pos[0] is None or pos[1] is None:
            raise ValueError('current motor position unknown (no reply from the controller yet)')
        stops = validate_stops(raw_stops)
        vmax = self.link.state['maxspeed'][0] or DEFAULT_VMAX
        vmax = min(vmax, self.link.state['maxspeed'][1] or DEFAULT_VMAX)
        accel = min(self.link.state['accel'][0] or DEFAULT_ACCEL, self.link.state['accel'][1] or DEFAULT_ACCEL)
        self.plan = build_plan((pos[0], pos[1]), stops, (int(access['x']), int(access['y'])),
                               vmax, accel, float(settle_s))
        if self.state in ('done', 'aborted', 'failed'):
            self.state = 'idle'
        self._push()
        return self.plan

    def clear_plan(self):
        if self.active:
            raise ValueError('a run is in progress')
        self.plan = None
        self._push()

    # ---- control ---------------------------------------------------------
    def start(self, plan_id, mode, value, options, client):
        if self.active:
            raise ValueError('a run is already in progress')
        if not self.plan or self.plan['plan_id'] != plan_id:
            raise ValueError('the plan changed - press "Plan path" again')
        if mode not in MODES:
            raise ValueError(f'unknown mode {mode!r}')
        if not self.link.connected:
            raise ValueError('stepper controller not connected')
        if not self.link.fresh_update(timeout=3.0):
            raise ValueError('stepper controller did not answer UPDATE')
        if not self.link.all_enabled():
            raise ValueError('both motors must be ENABLED before a run (Motion page > Motors)')
        pos = self.link.state['pos']
        tol = int(options.get('tolerance_steps', 2))
        if abs(pos[0] - self.plan['start'][0]) > tol or abs(pos[1] - self.plan['start'][1]) > tol:
            raise ValueError('the stage moved since the path was planned - press "Plan path" again')
        if any(abs(self.link.state['speed'][a] or 0) > 0 for a in (0, 1)):
            raise ValueError('a motor is still moving')
        if mode == 'live':
            st = self.firing.full_check()
            if not self.firing.can_write():
                if st.get('transport') == 'ssh':
                    raise ValueError(f'live firing unavailable: ssh gateway check failed '
                                     f'({st.get("ssh_error") or st.get("ssh_access")})')
                raise ValueError(f'live firing unavailable: {FIRE_PV} access is '
                                 f'{st.get("access") or "not connected"} from this host')
        if options.get('dosecam'):
            s = dosecam('GET', '/api/acquisition/status')
            if not s.get('ok'):
                raise ValueError(f'DoseCam not reachable: {s.get("error")}')
            if (s.get('status') or {}).get('running'):
                raise ValueError('DoseCam already has an acquisition running')

        run_id = time.strftime('%Y%m%d_%H%M%S')
        os.makedirs(self.run_dir, exist_ok=True)
        self._log_fh = open(os.path.join(self.run_dir, f'run_{run_id}.jsonl'), 'a')
        self.events = []
        self.abort_evt = Event()
        self.operator_evt = Event()
        self.run = {
            'run_id': run_id, 'mode': mode, 'pv': FIRE_PV, 'value': int(value),
            'value_label': value_label(self.firing.status, value),
            'options': options, 'client': client, 'started': time.time(),
            'index': -1, 'stop_state': {s['id']: 'pending' for s in self.plan['stops']},
            'pulses_done': {s['id']: 0 for s in self.plan['stops']},
            'message': 'starting', 'operator_command': None, 'finished': None,
        }
        self.state = 'running'
        if mode == 'live':
            self.run['route'] = self.firing.live_route()
        self.log('start', f'run {run_id} started in {mode.upper()} mode by {client}: '
                 f'{len(self.plan["stops"])} positions, {self.plan["total_pulses"]} pulses, '
                 f'{FIRE_PV} <- {int(value)}', plan=self.plan, options=options)
        self._push()
        self.greenlet = gevent.spawn(self._execute)
        return self.run

    def abort(self, client, reason='operator abort'):
        sent = self.link.write('STOP ALL')
        if not self.active:
            return {'was_running': False, 'stop_sent': sent}
        self.state = 'aborting'
        self.log('abort', f'ABORT ({reason}) from {client}; STOP ALL sent={sent}')
        self.abort_evt.set()
        self.operator_evt.set()
        self._push()
        return {'was_running': True, 'stop_sent': sent}

    def operator(self, action, client):
        if self.state != 'waiting_operator':
            raise ValueError('not waiting for the operator')
        if action not in ('fired', 'skip'):
            raise ValueError('action must be fired or skip')
        self.operator_action = (action, client)
        self.operator_evt.set()

    # ---- execution -------------------------------------------------------
    def _check_abort(self):
        if self.abort_evt.is_set():
            raise RunAborted()

    def _sleep(self, seconds):
        if self.abort_evt.wait(timeout=max(0.0, seconds)):
            raise RunAborted()

    def _wait_until(self, t_due):
        """Sleep until t_due (monotonic) to ~1 ms: coarse wait, then a short cooperative spin."""
        while True:
            remaining = t_due - time.monotonic()
            if remaining <= 0:
                return
            if remaining > 0.004:
                if self.abort_evt.wait(timeout=remaining - 0.003):
                    raise RunAborted()
            else:
                gevent.sleep(0)
                if self.abort_evt.is_set():
                    raise RunAborted()

    def _move(self, dest, leg_time_s, label, at_access=False):
        tol = int(self.run['options'].get('tolerance_steps', 2))
        x, y = int(dest[0]), int(dest[1])
        self.run['message'] = f'moving to {label} ({x}, {y})'
        self._push()
        self.log('move', f'MOVEABS 0 {x} / MOVEABS 1 {y} -> {label}', dest=[x, y])
        if not (self.link.write(f'MOVEABS 0 {x}') and self.link.write(f'MOVEABS 1 {y}')):
            raise RunFailed('serial write failed')
        t0 = time.monotonic()
        timeout = 1.5 * leg_time_s + 15.0
        stopped_polls = 0
        while True:
            self._sleep(0.3)
            if not self.link.connected:
                raise RunFailed('stepper controller disconnected during a move')
            if not self.link.fresh_update(timeout=2.0):
                if time.monotonic() - t0 > timeout:
                    raise RunFailed('no reply from the stepper controller')
                continue
            st = self.link.state
            if not self.link.all_enabled():
                raise RunFailed('a motor became DISABLED during the move')
            moving = any(abs(st['speed'][a] or 0) > 0 for a in (0, 1))
            err = (st['pos'][0] - x, st['pos'][1] - y)
            if not moving and abs(err[0]) <= tol and abs(err[1]) <= tol:
                self.log('arrive', f'at {label}: pos ({st["pos"][0]}, {st["pos"][1]}) '
                         f'in {time.monotonic() - t0:.1f} s', pos=[st['pos'][0], st['pos'][1]])
                return
            if not moving and time.monotonic() - t0 > 1.0:
                stopped_polls += 1
                if stopped_polls >= 2:
                    flags = f'{st["flags"][0] or "-"}/{st["flags"][1] or "-"}'
                    if at_access and (st['flags'][0] or st['flags'][1]):
                        self.log('arrive', f'access: stopped on limit switch (flags {flags}) at '
                                 f'({st["pos"][0]}, {st["pos"][1]}), target ({x}, {y})')
                        return
                    raise RunFailed(f'motion stopped short of {label}: at ({st["pos"][0]}, '
                                    f'{st["pos"][1]}), target ({x}, {y}), limit flags {flags}')
            else:
                stopped_polls = 0
            if time.monotonic() - t0 > timeout:
                raise RunFailed(f'move to {label} did not finish within {timeout:.0f} s')

    def _assert_on_target(self, stop):
        tol = int(self.run['options'].get('tolerance_steps', 2))
        st = self.link.state
        if not self.link.connected:
            raise RunFailed('stepper controller disconnected')
        if not self.link.all_enabled():
            raise RunFailed('a motor is DISABLED')
        if any(abs(st['speed'][a] or 0) > 0 for a in (0, 1)):
            raise RunFailed('stage is moving')
        if abs(st['pos'][0] - stop['x']) > tol or abs(st['pos'][1] - stop['y']) > tol:
            raise RunFailed(f'stage is not at {stop["label"]} '
                            f'(at {st["pos"][0]}, {st["pos"][1]})')

    def _dosecam_arm(self, stop):
        opts = self.run['options']
        base = f'flash_runs/{self.run["run_id"]}/{stop["label"]}'
        r = dosecam('POST', '/api/acquisition/start', {
            'base': base, 'frames': stop['pulses'], 'capture_mode': 'flash_run',
            'gate_width_us': opts.get('gate_width_us', 100),
            'esp_delay_us': opts.get('esp_delay_us', 200)}, timeout=10.0)
        if not r.get('ok'):
            raise RunFailed(f'DoseCam would not arm: {r.get("error")}')
        t0 = time.monotonic()
        while time.monotonic() - t0 < 15:
            s = (dosecam('GET', '/api/acquisition/status').get('status') or {})
            if s.get('running') and s.get('message') == 'Armed':
                self.log('dosecam', f'DoseCam armed for {stop["pulses"]} frames ({base})')
                return
            if not s.get('running') and time.monotonic() - t0 > 2:
                raise RunFailed(f'DoseCam acquisition ended before arming: {s.get("message")}')
            self._sleep(0.2)
        raise RunFailed('DoseCam did not report Armed within 15 s')

    def _dosecam_finish(self, stop, wait_s=3.0):
        t0 = time.monotonic()
        s = {}
        while time.monotonic() - t0 < wait_s:
            s = (dosecam('GET', '/api/acquisition/status').get('status') or {})
            if not s.get('running') or (s.get('frames_written') or 0) >= stop['pulses']:
                break
            gevent.sleep(0.2)
        if s.get('running'):
            dosecam('POST', '/api/acquisition/stop')
            gevent.sleep(1.0)
            s = (dosecam('GET', '/api/acquisition/status').get('status') or {})
        got = s.get('frames_written')
        kind = 'dosecam' if got == stop['pulses'] else 'warn'
        self.log(kind, f'DoseCam {stop["label"]}: {got}/{stop["pulses"]} frames, '
                 f'files {s.get("files")}', frames_written=got, files=s.get('files'))

    def _fire(self, stop):
        mode, value = self.run['mode'], self.run['value']
        n, delay = stop['pulses'], stop['delay']
        sid = stop['id']
        if mode == 'assisted':
            cmd = repeatput_command(FIRE_PV, value, n, delay)
            self.run['operator_command'] = cmd
            self.run['message'] = f'at {stop["label"]}: run  {cmd}  then press "Fired - continue"'
            self.state = 'waiting_operator'
            self.operator_evt.clear()
            self.log('operator', f'waiting for operator at {stop["label"]}: {cmd}', command=cmd)
            self._push()
            self.operator_evt.wait()
            self._check_abort()
            action, who = self.operator_action
            self.state = 'running'
            self.run['operator_command'] = None
            if action == 'skip':
                self.run['stop_state'][sid] = 'skipped'
                self.log('skip', f'{stop["label"]} skipped by {who}')
            else:
                self.run['pulses_done'][sid] = n
                self.log('fired', f'{stop["label"]}: operator ({who}) reports {n} pulse(s) fired')
            self._push()
            return

        # Pulse k (0-based) is due at t0 + k*delay on a monotonic clock that keeps
        # running: time spent sending a put, or a late wake-up, never shifts the
        # pulses after it, so N pulses take (N-1)*delay however long each put takes.
        self.firing.busy = True
        late_ms, rtt_ms = [], []
        try:
            self._assert_on_target(stop)
            t0 = time.monotonic() + 0.005
            last_push = 0.0
            t_send = t0
            for i in range(1, n + 1):
                t_due = t0 + (i - 1) * delay
                self._assert_on_target(stop)          # checked before the wait, not at the send
                self._wait_until(t_due)
                t_send = time.monotonic()
                late = (t_send - t_due) * 1000.0
                late_ms.append(late)
                if mode == 'live':
                    r = self.firing.put_once(value)
                    if not r.get('ok'):
                        raise RunFailed(f'put {FIRE_PV} {value} failed ({self.firing.live_route()}): '
                                        f'{r.get("error")} (not retried)')
                    rtt_ms.append(r.get('rtt_ms') or 0.0)
                    what = f'put {FIRE_PV} {value}  (+{late:.1f} ms, round trip {r.get("rtt_ms")} ms)'
                else:
                    what = f'SIM put {FIRE_PV} {value}  (+{late:.1f} ms)'
                self.log('pulse', f'{stop["label"]} {i}/{n} @ {t_send - t0:.3f} s: {what}',
                         i=i, n=n, stop=sid, at_s=round(t_send - t0, 4), late_ms=round(late, 2),
                         rtt_ms=rtt_ms[-1] if rtt_ms else None)
                self.run['pulses_done'][sid] = i
                self.run['message'] = f'firing {stop["label"]}: {i}/{n}'
                if time.monotonic() - last_push > 0.5 or i == n:
                    last_push = time.monotonic()
                    self._push()
            expected = (n - 1) * delay
            took = t_send - t0
            msg = (f'{stop["label"]}: {n} pulses, first to last {took:.3f} s (scheduled {expected:.3f} s, '
                   f'error {1000 * (took - expected):+.1f} ms); send lateness max {max(late_ms):.1f} ms')
            if rtt_ms:
                msg += f'; put round trip mean {sum(rtt_ms) / len(rtt_ms):.1f} ms, max {max(rtt_ms):.1f} ms'
            self.log('timing', msg, took_s=took, expected_s=expected, late_max_ms=max(late_ms),
                     rtt_mean_ms=(sum(rtt_ms) / len(rtt_ms)) if rtt_ms else None)
        finally:
            self.firing.busy = False

    def _execute(self):
        plan, opts = self.plan, self.run['options']
        legs = {l['to']: l for l in plan['legs']}
        dosecam_active = False
        current = None
        live = self.run['mode'] == 'live'
        try:
            if live:
                try:
                    hello = self.firing.begin_live()
                except Exception as exc:
                    raise RunFailed(f'could not open the firing route: {exc}')
                self.log('live', f'firing route open: {self.firing.live_route()} '
                         f'(backend {hello.get("backend")}, access {hello.get("access")})')
            for idx, stop in enumerate(plan['stops']):
                current = stop
                self.run['index'] = idx
                self.run['stop_state'][stop['id']] = 'moving'
                self._move((stop['x'], stop['y']), legs[stop['id']]['time_s'], stop['label'])
                self.run['stop_state'][stop['id']] = 'settling'
                self.run['message'] = f'settling at {stop["label"]}'
                self._push()
                self._sleep(float(plan['settle_s']))
                if not self.link.fresh_update(timeout=2.0):
                    raise RunFailed('no reply from the stepper controller before firing')
                self._assert_on_target(stop)
                if opts.get('dosecam'):
                    self._dosecam_arm(stop)
                    dosecam_active = True
                self.run['stop_state'][stop['id']] = 'firing'
                self._push()
                self._fire(stop)
                if dosecam_active:
                    self._dosecam_finish(stop)
                    dosecam_active = False
                if self.run['stop_state'][stop['id']] != 'skipped':
                    self.run['stop_state'][stop['id']] = 'done'
                self._push()
            current = None
            self.run['index'] = len(plan['stops'])
            self._move(plan['access'], legs['__access__']['time_s'], 'access', at_access=True)
            self.state = 'done'
            self.run['message'] = 'finished - parked at access'
            self.log('done', f'run {self.run["run_id"]} finished; '
                     f'{sum(self.run["pulses_done"].values())} pulses')
        except RunAborted:
            self.link.write('STOP ALL')
            self.state = 'aborted'
            self.run['message'] = 'aborted - stage stopped where it is'
            if current:
                self.run['stop_state'][current['id']] = 'aborted'
            self.log('aborted', 'run aborted; motors stopped (not returned to access)')
        except RunFailed as exc:
            self.link.write('STOP ALL')
            self.state = 'failed'
            self.run['message'] = f'stopped: {exc}'
            if current:
                self.run['stop_state'][current['id']] = 'failed'
            self.log('error', f'run stopped: {exc}; STOP ALL sent')
        except Exception as exc:   # bug guard: never leave the stage moving silently
            self.link.write('STOP ALL')
            self.state = 'failed'
            self.run['message'] = f'internal error: {exc}'
            self.log('error', f'internal error: {type(exc).__name__}: {exc}; STOP ALL sent')
        finally:
            if live:
                try:
                    self.firing.end_live()
                except Exception:
                    pass
            if dosecam_active:
                dosecam('POST', '/api/acquisition/stop')
                self.log('dosecam', 'DoseCam acquisition stopped')
            self.firing.busy = False
            self.run['finished'] = time.time()
            self.run['operator_command'] = None
            if self._log_fh:
                try:
                    self._log_fh.write(json.dumps({'t': time.time(), 'kind': 'summary',
                                                   'run': self.run}) + '\n')
                    self._log_fh.close()
                except Exception:
                    pass
                self._log_fh = None
            self._push()
