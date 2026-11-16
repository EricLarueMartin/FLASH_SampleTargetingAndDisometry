"""Serial link to the ESP32 stepper controller, plus a parsed copy of its state.

The ESP32 (StepperController sketch) answers one text line per query and pushes
GETPOS/GETSPEED lines about once a second while a motor moves, plus a full
UPDATE every 10 s. There is no "move done" event, so callers that need to know a
move finished poll with UPDATE and compare against the target (see sequencer).

Every received line is passed to `on_line` (the web terminal) and parsed into
`state`. The serial lock is only held while touching the port, never while
calling back into Socket.IO.
"""

import re
import time

import gevent
import serial
from gevent.lock import Semaphore

AXES = (0, 1)
_POS_RE = re.compile(r'^GETPOS\s+(\d+)\s+(-?[\d.]+)([LUH]*)\s*$')
_KV_RE = re.compile(r'^(GETSPEED|GETMAXSPEED|GETACCEL)\s+(\d+)\s+(-?[\d.]+)\s*$')
_EN_RE = re.compile(r'^GETENABLED\s+(\d+)\s+(ENABLED|DISABLED)\s*$')
_ENDIS_RE = re.compile(r'^(ENABLE|DISABLE)\s+(\d+)\s*$')


def _clean(raw):
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('ascii', 'replace')
    return re.sub(r'[^\x20-\x7E]', '', text).strip()


class StepperLink:
    def __init__(self, port, baud=115200, on_line=None, on_state=None):
        self.port = port
        self.baud = baud
        self.ser = None
        self.lock = Semaphore()
        self.on_line = on_line or (lambda line: None)
        self.on_state = on_state or (lambda state: None)
        self.connected = False
        self.last_error = None
        self.last_rx = 0.0
        now = 0.0
        self.state = {
            'pos': {a: None for a in AXES},
            'flags': {a: '' for a in AXES},        # L = low limit, U = high limit, H = home
            'speed': {a: None for a in AXES},
            'enabled': {a: None for a in AXES},    # 'ENABLED' / 'DISABLED'
            'maxspeed': {a: None for a in AXES},
            'accel': {a: None for a in AXES},
        }
        # monotonic time each field was last heard, so a poller can wait for a
        # reply that arrived after its own query
        self.heard = {k: {a: now for a in AXES} for k in self.state}
        self._state_dirty = False

    # ---- port ------------------------------------------------------------
    def _open(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0)
            self.connected = True
            self.last_error = None
            self.on_line(f'[serial] connected to {self.port}')
            gevent.spawn_later(0.5, self.write, 'UPDATE')
            gevent.spawn_later(0.8, self.write, 'GETMAXSPEED 0')
            gevent.spawn_later(0.9, self.write, 'GETMAXSPEED 1')
            gevent.spawn_later(1.0, self.write, 'GETACCEL 0')
            gevent.spawn_later(1.1, self.write, 'GETACCEL 1')
            return True
        except Exception as exc:
            if self.last_error != str(exc):
                self.on_line(f'[serial] cannot open {self.port}: {exc}')
            self.last_error = str(exc)
            self.connected = False
            self.ser = None
            return False

    def _drop(self, exc):
        self.last_error = str(exc)
        self.on_line(f'[serial] lost connection: {exc}')
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.connected = False
        for a in AXES:
            self.state['enabled'][a] = None

    def run(self):
        """Reader loop; spawn as a greenlet."""
        buffer = b''
        gevent.spawn(self._state_pump)
        while True:
            if self.ser is None and not self._open():
                gevent.sleep(2.0)
                continue
            chunk = b''
            with self.lock:
                try:
                    waiting = self.ser.in_waiting
                    if waiting:
                        chunk = self.ser.read(waiting)
                except Exception as exc:
                    self._drop(exc)
                    buffer = b''
            if chunk:
                buffer += chunk
                if b'\n' in buffer:
                    lines = buffer.split(b'\n')
                    buffer = lines.pop()
                    for raw in lines:
                        line = _clean(raw)
                        if line:
                            self.last_rx = time.monotonic()
                            self._parse(line)
                            self.on_line(line)
                if len(buffer) > 65536:       # LIST output without newlines, or noise
                    buffer = b''
            gevent.sleep(0.01)

    def write(self, command):
        command = command.strip()
        if not command:
            return False
        with self.lock:
            if self.ser is None:
                return False
            try:
                self.ser.write((command + '\n').encode())
                self.ser.flush()
            except Exception as exc:
                self._drop(exc)
                return False
        return True

    # ---- parsing ---------------------------------------------------------
    def _set(self, key, axis, value):
        if axis not in AXES:
            return
        self.state[key][axis] = value
        self.heard[key][axis] = time.monotonic()
        self._state_dirty = True

    def _parse(self, line):
        m = _POS_RE.match(line)
        if m:
            axis = int(m.group(1))
            self._set('pos', axis, int(round(float(m.group(2)))))
            self._set('flags', axis, m.group(3))
            return
        m = _KV_RE.match(line)
        if m:
            key = {'GETSPEED': 'speed', 'GETMAXSPEED': 'maxspeed', 'GETACCEL': 'accel'}[m.group(1)]
            self._set(key, int(m.group(2)), float(m.group(3)))
            return
        m = _EN_RE.match(line)
        if m:
            self._set('enabled', int(m.group(1)), m.group(2))
            return
        m = _ENDIS_RE.match(line)
        if m:
            self._set('enabled', int(m.group(2)), 'ENABLED' if m.group(1) == 'ENABLE' else 'DISABLED')

    def _state_pump(self):
        """Push state to browsers at most 5x a second, only when it changed."""
        while True:
            gevent.sleep(0.2)
            if self._state_dirty:
                self._state_dirty = False
                try:
                    self.on_state(self.snapshot())
                except Exception as exc:
                    print(f'state push error: {exc}', flush=True)

    def snapshot(self):
        s = {k: {str(a): v for a, v in d.items()} for k, d in self.state.items()}
        s['connected'] = self.connected
        s['port'] = self.port
        s['last_error'] = self.last_error
        s['last_rx_age_s'] = round(time.monotonic() - self.last_rx, 1) if self.last_rx else None
        return s

    # ---- helpers for the sequencer --------------------------------------
    def fresh_update(self, keys=('pos', 'speed', 'enabled'), timeout=2.0):
        """Send UPDATE and wait until every axis has reported `keys` since the query."""
        t0 = time.monotonic()
        if not self.write('UPDATE'):
            return False
        deadline = t0 + timeout
        while time.monotonic() < deadline:
            if all(self.heard[k][a] > t0 for k in keys for a in AXES):
                return True
            gevent.sleep(0.02)
        return False

    def all_enabled(self):
        return all(self.state['enabled'][a] == 'ENABLED' for a in AXES)
