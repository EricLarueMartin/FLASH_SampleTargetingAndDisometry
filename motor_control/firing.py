"""Firing the linac: one put of BST:INJ:START per pulse.

Pulse timing is NOT done the repeatPut.sh way (put, then sleep, then put...),
which lets every put's own duration and every sleep's overshoot add up over a
long train. The sequencer fires pulse k at t0 + k*delay on a monotonic clock
that keeps running, so the total time is what was asked for and a late pulse
does not shift the ones after it. This module only has to make one put fast.

Modes
  simulate  - nothing is written; every pulse is logged as "SIM put ...".
  assisted  - nothing is written; at each position the page shows the
              equivalent repeatPut.sh command for an operator and waits.
  live      - this server fires, through the transport:
     ssh    - a control-room host/account (ringop) that the IOC already lets
              write. One SSH session stays open for the whole run; on the far
              end deploy/fire-gateway/flash_fire_gw.py (a forced command, the
              key can do nothing else) keeps the PV connected and does one put
              (no callback, like caput) per line it is sent. A pulse costs a LAN
              round trip plus the put: a few ms.
     ca     - (no gateway host set) this host writes over Channel Access itself;
              only possible if the IOC's access security grants it WRITE.
              pi-06-ioc / test has READ only.
  Access security is the IOC's job and is never worked around here. A refused
  or failed put ends the run and is not retried.

The CA status on the page (connected / value / access) comes from a read-only
caproto client in ca_tool.py, pointed at cr-01-ioc by EPICS_CA_ADDR_LIST.

This software is not a safety system. PSS/MPS/interlocks are independent of it.
"""

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time

import gevent
from gevent.lock import Semaphore

HERE = os.path.dirname(os.path.abspath(__file__))
FIRE_PV = 'BST:INJ:START'          # fixed by design; shown on the page
MODES = ('simulate', 'assisted', 'live')
PROBE_PERIOD_S = 5.0
SSH_CHECK_PERIOD_S = 60.0
SSH_DIR = os.path.expanduser('~/.ssh')
KNOWN_HOSTS = os.path.join(SSH_DIR, 'flash_fire_known_hosts')
CONTROL_PATH = os.path.join(SSH_DIR, 'flash_fire_cm_%C')
_HOST_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.\-]{0,252}$')
_USER_RE = re.compile(r'^[a-z_][a-z0-9_\-]{0,31}$')

DEFAULT_GATEWAY = {
    'user': 'ringop',
    'host': '',
    'port': 22,
    'key': '~/.ssh/flash_fire_ed25519',
    'command_path': '/home/ringop/bin/flash_fire_gw.py',
    'pi_address': '192.168.16.62',
}


# --------------------------------------------------------------------------
# gateway settings (Settings page)
# --------------------------------------------------------------------------
class GatewaySettings:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = dict(DEFAULT_GATEWAY)
        try:
            with open(path) as fh:
                self.data.update(self._validate(json.load(fh).get('gateway', {}), self.data))
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f'settings: cannot read {path}: {exc}', flush=True)

    @staticmethod
    def _validate(new, base):
        out = dict(base)
        if 'user' in new:
            u = str(new['user']).strip()
            if not _USER_RE.match(u):
                raise ValueError(f'bad account name {u!r}')
            out['user'] = u
        if 'host' in new:
            h = str(new['host']).strip()
            if h and not _HOST_RE.match(h):
                raise ValueError(f'bad host name {h!r}')
            out['host'] = h
        if 'port' in new:
            p = int(new['port'])
            if not 1 <= p <= 65535:
                raise ValueError('bad port')
            out['port'] = p
        if 'key' in new:
            k = str(new['key']).strip()
            if not k.startswith('~/.ssh/') or '..' in k or not re.match(r'^[~/A-Za-z0-9_.\-]+$', k):
                raise ValueError('key must be a file under ~/.ssh/')
            out['key'] = k
        if 'command_path' in new:
            c = str(new['command_path']).strip()
            if not re.match(r'^/[A-Za-z0-9_./\-]+$', c):
                raise ValueError('bad gateway script path')
            out['command_path'] = c
        if 'pi_address' in new:
            out['pi_address'] = str(new['pi_address']).strip()[:64]
        return out

    def get(self):
        with self.lock:
            return dict(self.data)

    def update(self, new):
        with self.lock:
            data = self._validate(new, self.data)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w') as fh:
                json.dump({'gateway': data}, fh, indent=1)
            os.replace(tmp, self.path)
            self.data = data
            return dict(data)


# --------------------------------------------------------------------------
class Firing:
    def __init__(self, settings, pv=FIRE_PV, on_status=None):
        self.settings = settings
        self.pv = pv
        self.proc = None
        self.lock = Semaphore()
        self.ssh_lock = Semaphore()
        self.session = None
        self._id = 0
        self.busy = False
        self.status = {'pv': pv, 'connected': False, 'access': None, 'value': None,
                       'enum_strings': None, 'host': None, 'error': 'not probed yet',
                       'checked_at': None, 'ssh_ok': None, 'ssh_info': None,
                       'ssh_error': None, 'ssh_checked_at': None}
        self.on_status = on_status or (lambda s: None)

    # ---- transport -------------------------------------------------------
    @property
    def gw(self):
        return self.settings.get()

    @property
    def transport(self):
        return 'ssh' if self.gw['host'] else 'ca'

    def ssh_target(self):
        g = self.gw
        return f'{g["user"]}@{g["host"]}' if g['host'] else None

    def key_path(self):
        return os.path.expanduser(self.gw['key'])

    def ssh_base(self, multiplex=True):
        g = self.gw
        base = ['ssh', '-i', self.key_path(), '-p', str(g['port']),
                '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={KNOWN_HOSTS}',
                '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=10', '-T']
        if multiplex:
            base += ['-o', 'ControlMaster=auto', '-o', f'ControlPath={CONTROL_PATH}',
                     '-o', 'ControlPersist=600']
        return base + [f'{g["user"]}@{g["host"]}']

    def status_view(self):
        s = dict(self.status)
        s.update(transport=self.transport, ssh_target=self.ssh_target(),
                 session_open=self.session is not None)
        return s

    # ---- read-only CA helper process ------------------------------------
    def _start(self):
        self.proc = subprocess.Popen(
            [sys.executable, '-u', os.path.join(HERE, 'ca_tool.py'), self.pv],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=HERE, text=True, bufsize=1)
        gevent.spawn(self._drain_stderr, self.proc, 'ca_tool')

    @staticmethod
    def _drain_stderr(proc, tag):
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                print(f'{tag}: {line}', flush=True)

    def _stop(self):
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass

    def _request(self, payload, timeout=6.0):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            self._id += 1
            payload = dict(payload, id=self._id)
            try:
                self.proc.stdin.write(json.dumps(payload) + '\n')
                self.proc.stdin.flush()
                with gevent.Timeout(timeout):
                    while True:
                        line = self.proc.stdout.readline()
                        if not line:
                            raise RuntimeError('CA helper exited')
                        reply = json.loads(line)
                        if reply.get('id') == self._id:
                            return reply
            except gevent.Timeout:
                self._stop()
                return {'ok': False, 'error': f'CA helper did not answer within {timeout:.0f} s'}
            except Exception as exc:
                self._stop()
                return {'ok': False, 'error': f'CA helper failed: {exc}'}

    def probe(self):
        r = self._request({'op': 'probe'})
        st = {'pv': self.pv, 'checked_at': time.time()}
        if r.get('ok'):
            st.update(connected=r.get('connected', False), access=r.get('access'),
                      value=r.get('value'), enum_strings=r.get('enum_strings'),
                      host=r.get('host'), error=r.get('error') or r.get('read_error'))
        else:
            st.update(connected=False, access=None, value=None, error=r.get('error'))
        self.status.update(st)
        return self.status_view()

    # ---- ssh gateway: setup helpers (Settings page) -----------------------
    def create_key(self):
        key = self.key_path()
        if os.path.exists(key):
            raise ValueError(f'{self.gw["key"]} already exists')
        os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
        r = subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C',
                            f'flash-fire@{socket.gethostname()}', '-f', key],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or 'ssh-keygen failed')
        return self.public_key()

    def public_key(self):
        try:
            with open(self.key_path() + '.pub') as fh:
                return fh.read().strip()
        except FileNotFoundError:
            return None

    def authorized_keys_line(self):
        pub = self.public_key()
        if not pub:
            return None
        g = self.gw
        return f'command="{g["command_path"]}",from="{g["pi_address"]}",restrict {pub}'

    def keyscan(self):
        g = self.gw
        if not g['host']:
            raise ValueError('set the gateway host first')
        r = subprocess.run(['ssh-keyscan', '-T', '5', '-p', str(g['port']), '-t', 'ed25519,ecdsa,rsa', g['host']],
                           capture_output=True, text=True, timeout=20)
        lines = [l for l in r.stdout.splitlines() if l and not l.startswith('#')]
        if not lines:
            raise RuntimeError(f'no host key from {g["host"]}:{g["port"]} ({r.stderr.strip()[-200:]})')
        keys = []
        for line in lines:
            fp = subprocess.run(['ssh-keygen', '-lf', '-'], input=line, capture_output=True, text=True, timeout=10)
            keys.append({'line': line, 'fingerprint': fp.stdout.strip()})
        return keys

    def trust_host_keys(self, lines):
        g = self.gw
        host_tag = g['host'] if g['port'] == 22 else f'[{g["host"]}]:{g["port"]}'
        clean = []
        for line in lines:
            parts = line.split()
            if len(parts) < 3 or parts[0].lstrip('[').split(']')[0] != g['host'] or not parts[1].startswith(('ssh-', 'ecdsa-')):
                raise ValueError('host key line does not match the gateway host')
            clean.append(f'{host_tag} {parts[1]} {parts[2]}')
        os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
        keep = []
        if os.path.exists(KNOWN_HOSTS):
            with open(KNOWN_HOSTS) as fh:
                keep = [l.rstrip('\n') for l in fh if l.split() and l.split()[0] != host_tag]
        with open(KNOWN_HOSTS, 'w') as fh:
            fh.write('\n'.join(keep + clean) + '\n')
        os.chmod(KNOWN_HOSTS, 0o600)
        return len(clean)

    def host_trusted(self):
        g = self.gw
        if not g['host'] or not os.path.exists(KNOWN_HOSTS):
            return False
        host_tag = g['host'] if g['port'] == 22 else f'[{g["host"]}]:{g["port"]}'
        with open(KNOWN_HOSTS) as fh:
            return any(l.split() and l.split()[0] == host_tag for l in fh)

    def check_ssh(self):
        """Read-only check through the gateway ('check' request)."""
        if self.transport != 'ssh':
            return None
        ok, info, err = False, None, None
        if not os.path.exists(self.key_path()):
            err = f'key {self.gw["key"]} missing (Settings > Create key)'
        elif not self.host_trusted():
            err = 'gateway host key not trusted yet (Settings > Get host key)'
        else:
            with self.ssh_lock:
                try:
                    r = subprocess.run(self.ssh_base() + ['check'], capture_output=True, text=True,
                                       timeout=15, stdin=subprocess.DEVNULL)
                    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
                    info = json.loads(lines[-1]) if lines else None
                    if info and info.get('ok'):
                        ok = 'write' in (info.get('access') or '')
                        err = None if ok else f'gateway account has access "{info.get("access")}" on {self.pv}'
                    else:
                        err = (info or {}).get('error') or (r.stderr.strip() or r.stdout.strip())[-300:] \
                            or f'ssh exit {r.returncode}'
                except subprocess.TimeoutExpired:
                    err = 'ssh check timed out'
                except Exception as exc:
                    err = f'ssh check failed: {exc}'
        self.status.update(ssh_ok=ok, ssh_info=info, ssh_error=err, ssh_checked_at=time.time())
        return ok

    # ---- ssh gateway: firing session ---------------------------------------
    def open_session(self):
        """Open the persistent 'serve' session used for a live run."""
        self.close_session()
        proc = subprocess.Popen(self.ssh_base() + ['serve'], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        gevent.spawn(self._drain_stderr, proc, 'fire-gw')
        try:
            with gevent.Timeout(15):
                hello = json.loads(proc.stdout.readline() or '{}')
        except (gevent.Timeout, ValueError):
            hello = {'ok': False, 'error': 'no answer from the gateway'}
        if not hello.get('ok') or 'write' not in (hello.get('access') or ''):
            proc.kill()
            raise RuntimeError(f'gateway session refused: {hello.get("error") or "access " + str(hello.get("access"))}')
        self.session = proc
        return hello

    def close_session(self):
        proc, self.session = self.session, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.write('quit\n')
                proc.stdin.flush()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    def _session_request(self, line, timeout=2.0):
        proc = self.session
        if proc is None or proc.poll() is not None:
            return {'ok': False, 'error': 'gateway session is not open'}
        try:
            proc.stdin.write(line + '\n')
            proc.stdin.flush()
            with gevent.Timeout(timeout):
                text = proc.stdout.readline()
            if not text:
                return {'ok': False, 'error': 'gateway session closed'}
            return json.loads(text)
        except gevent.Timeout:
            return {'ok': False, 'error': f'gateway did not answer within {timeout:.0f} s'}
        except Exception as exc:
            return {'ok': False, 'error': f'gateway session error: {exc}'}

    # ---- public ----------------------------------------------------------
    def full_check(self):
        self.probe()
        self.check_ssh()
        return self.status_view()

    def can_write(self):
        if self.transport == 'ssh':
            return bool(self.status.get('ssh_ok'))
        return bool(self.status.get('connected')) and self.status.get('access') in ('WRITE', 'READ_WRITE')

    def live_route(self):
        if self.transport == 'ssh':
            return f'put via {self.ssh_target()}'
        return 'Channel Access from this host'

    def begin_live(self):
        if self.transport == 'ssh':
            return self.open_session()
        return {'ok': True, 'backend': 'ca'}

    def end_live(self):
        self.close_session()

    def put_once(self, value):
        """One put. Returns {'ok': bool, 'error'?, 'ms'?}; 'rtt_ms' measured here."""
        t0 = time.monotonic()
        if self.transport == 'ssh':
            r = self._session_request(f'put {int(value)}')
        else:
            r = self._request({'op': 'put', 'value': int(value)}, timeout=5.0)
        r['rtt_ms'] = round((time.monotonic() - t0) * 1000, 2)
        return r

    def monitor(self):
        """Background greenlet: keep the status shown on the page fresh."""
        last_ssh = 0.0
        while True:
            if self.busy:            # a pulse train is in progress: don't add load
                gevent.sleep(0.5)
                continue
            try:
                keys = ('connected', 'access', 'value', 'ssh_ok', 'ssh_error')
                before = tuple(self.status.get(k) for k in keys)
                self.probe()
                if self.transport == 'ssh' and time.time() - last_ssh > SSH_CHECK_PERIOD_S:
                    last_ssh = time.time()
                    self.check_ssh()
                if before != tuple(self.status.get(k) for k in keys):
                    self.on_status(self.status_view())
            except Exception as exc:
                print(f'firing monitor: {exc}', flush=True)
            gevent.sleep(PROBE_PERIOD_S)


def value_label(status, value):
    names = status.get('enum_strings') or []
    try:
        return names[int(value)] if 0 <= int(value) < len(names) else None
    except Exception:
        return None


def repeatput_command(pv, value, count, delay):
    """The equivalent shell command, shown in assisted mode."""
    d = float(delay)
    return f'repeatPut.sh {pv} {value} {int(count)} {int(d) if d == int(d) else f"{d:g}"}'

