#!/usr/bin/env python3
"""FLASH firing gateway: forced command for the pi-06-ioc SSH key.

Install in the account that already fires the linac (ringop) on a control-room
host, and pin the Pi's key to it in ~/.ssh/authorized_keys:

  command="/home/ringop/bin/flash_fire_gw.py",from="192.168.16.62",restrict ssh-ed25519 AAAA... flash-fire@pi-06-ioc

The key can then do only this (SSH_ORIGINAL_COMMAND):
  check   read only: connect to the PV, print one JSON line (access, value, backend)
  serve   keep the PV connected and answer one JSON line per request line:
            "put <value>"  -> one put, no callback (what `caput PV value` does)
            "ping"         -> liveness
            "quit"
          The session ends when the Pi closes the connection.
Anything else is refused. Every put and refusal is appended to LOG.

The PV is fixed and values are whitelisted; access security on the IOC still
decides whether a put is allowed. Uses pyepics if installed, else caproto, else
runs EPICS base `caput` once per put (slower: tens of ms).
"""

import json
import os
import shutil
import subprocess
import sys
import time

PV_NAME = 'BST:INJ:START'
ALLOWED_VALUES = {1}
LOG = os.path.expanduser(os.environ.get('FLASH_FIRE_LOG', '~/flash_fire.log'))
CONNECT_TIMEOUT = 3.0
# Forced commands do not run a login shell. If this account gets its CA settings
# from .login, set them here, e.g.:
# os.environ.setdefault('EPICS_CA_AUTO_ADDR_LIST', 'NO')
# os.environ.setdefault('EPICS_CA_ADDR_LIST', '192.168.16.41')
# Where EPICS base caput/cainfo live, for the fallback backend:
EPICS_BIN = os.environ.get('FLASH_EPICS_BIN', '')

CLIENT = (os.environ.get('SSH_CLIENT') or '?').split()[0]


def log(msg):
    try:
        with open(LOG, 'a') as fh:
            fh.write(f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {CLIENT} {msg}\n')
    except OSError:
        pass


def out(obj):
    sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


# --------------------------------------------------------------------------
# backends
# --------------------------------------------------------------------------
class PyEpics:
    name = 'pyepics'

    def __init__(self):
        import epics
        self.pv = epics.PV(PV_NAME, connection_timeout=CONNECT_TIMEOUT)
        self.pv.wait_for_connection(timeout=CONNECT_TIMEOUT)

    def info(self):
        pv = self.pv
        if not pv.connected:
            return {'connected': False}
        acc = ', '.join(a for a, ok in (('read', pv.read_access), ('write', pv.write_access)) if ok) or 'none'
        return {'connected': True, 'access': acc, 'host': pv.host,
                'value': pv.get(as_string=True, timeout=CONNECT_TIMEOUT)}

    def put(self, value):
        if not self.pv.connected:
            raise RuntimeError('PV not connected')
        if not self.pv.write_access:
            raise RuntimeError('write access denied')
        self.pv.put(value, wait=False)          # ca_put, no callback - like caput


class Caproto:
    name = 'caproto'

    def __init__(self):
        from caproto.threading.client import Context
        self.ctx = Context()
        self.pv, = self.ctx.get_pvs(PV_NAME, timeout=CONNECT_TIMEOUT)
        try:
            self.pv.wait_for_connection(timeout=CONNECT_TIMEOUT)
        except Exception:
            pass

    def _access(self):
        from caproto import AccessRights
        r = self.pv.access_rights
        if r is None:
            return None
        r = AccessRights(r)
        return ', '.join(a for a, f in (('read', AccessRights.READ), ('write', AccessRights.WRITE)) if f in r) or 'none'

    def info(self):
        if not self.pv.connected:
            return {'connected': False}
        try:
            host = '%s:%s' % self.pv.circuit_manager.circuit.address
        except Exception:
            host = None
        v = self.pv.read(timeout=CONNECT_TIMEOUT).data
        return {'connected': True, 'access': self._access(), 'host': host,
                'value': v.tolist()[0] if hasattr(v, 'tolist') else v[0]}

    def put(self, value):
        if not self.pv.connected:
            raise RuntimeError('PV not connected')
        if 'write' not in (self._access() or ''):
            raise RuntimeError('write access denied')
        self.pv.write([value], wait=False, notify=False)


class CaputExe:
    name = 'caput'

    def __init__(self):
        self.caput = os.path.join(EPICS_BIN, 'caput') if EPICS_BIN else shutil.which('caput')
        self.cainfo = os.path.join(EPICS_BIN, 'cainfo') if EPICS_BIN else shutil.which('cainfo')
        if not self.caput:
            raise RuntimeError('no pyepics, no caproto, and caput not found (set FLASH_EPICS_BIN)')

    def info(self):
        r = subprocess.run([self.cainfo, PV_NAME], capture_output=True, text=True, timeout=10)
        txt = r.stdout
        get = lambda key: next((l.split(':', 1)[1].strip() for l in txt.splitlines()
                                if l.strip().startswith(key)), None)
        return {'connected': get('State') == 'connected', 'access': get('Access'), 'host': get('Host'),
                'value': None}

    def put(self, value):
        r = subprocess.run([self.caput, PV_NAME, str(value)], capture_output=True, text=True, timeout=10)
        text = r.stdout + r.stderr
        if r.returncode != 0 or 'rror' in text or 'denied' in text:
            raise RuntimeError(text.strip()[-200:] or f'caput exit {r.returncode}')


def backend():
    errors = []
    for cls in (PyEpics, Caproto, CaputExe):
        try:
            return cls()
        except Exception as exc:
            errors.append(f'{cls.name}: {exc}')
    raise RuntimeError('; '.join(errors))


# --------------------------------------------------------------------------
def check():
    try:
        b = backend()
        info = b.info()
        out(dict(info, ok=True, backend=b.name, pv=PV_NAME, allowed_values=sorted(ALLOWED_VALUES)))
        log(f'check {info.get("access")}')
        return 0
    except Exception as exc:
        out({'ok': False, 'error': str(exc), 'pv': PV_NAME})
        return 1


def serve():
    try:
        b = backend()
        info = b.info()
    except Exception as exc:
        out({'ok': False, 'hello': True, 'error': str(exc)})
        return 1
    out(dict(info, ok=True, hello=True, backend=b.name, pv=PV_NAME))
    log(f'serve start backend={b.name} access={info.get("access")}')
    n = 0
    for line in sys.stdin:
        words = line.split()
        if not words:
            continue
        if words[0] == 'quit':
            break
        if words[0] == 'ping' and len(words) == 1:
            out({'ok': True, 'pong': True, 't': time.time()})
            continue
        if words[0] == 'put' and len(words) == 2 and words[1].lstrip('-').isdigit():
            value = int(words[1])
            if value not in ALLOWED_VALUES:
                log(f'REFUSED value {value}')
                out({'ok': False, 'error': f'value {value} not allowed'})
                continue
            t0 = time.monotonic()
            try:
                b.put(value)
                n += 1
                ms = (time.monotonic() - t0) * 1000
                log(f'put {PV_NAME} {value} ({ms:.1f} ms)')
                out({'ok': True, 'ms': round(ms, 2), 'n': n})
            except Exception as exc:
                log(f'put {PV_NAME} {value} FAILED: {exc}')
                out({'ok': False, 'error': str(exc)})
            continue
        log(f'REFUSED request {line.strip()[:80]!r}')
        out({'ok': False, 'error': 'refused'})
    log(f'serve end after {n} puts')
    return 0


def main():
    words = (os.environ.get('SSH_ORIGINAL_COMMAND') or '').split()
    if words == ['check']:
        return check()
    if words == ['serve']:
        return serve()
    log(f'REFUSED command {" ".join(words)[:80]!r}')
    print('refused: only "check" or "serve"')
    return 2


if __name__ == '__main__':
    sys.exit(main())
