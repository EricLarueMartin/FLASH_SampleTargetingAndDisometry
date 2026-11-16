#!/usr/bin/env python3
"""Channel Access helper for the FLASH run page (runs as a child process).

Kept out of the gevent web server on purpose: caproto's threading client runs
its own threads, and a separate process means a CA problem can never stall the
web server or the motor link.

Protocol: one JSON object per line on stdin, one JSON reply per line on stdout.
  {"op": "probe"}                 -> connection, value, enum strings, access rights
  {"op": "put", "value": 1}       -> one write, the same as `caput PV 1`
                                     (no put-callback, like caput without -c), then
                                     a read-back like caput's "New :" line

The PV name comes from the command line and cannot be changed over the pipe.
A put is refused unless the server grants this host/user WRITE access; access
security is enforced by the IOC and is never worked around here.
"""

import json
import sys
import time

from caproto import AccessRights, ChannelType
from caproto.threading.client import Context

PV_NAME = sys.argv[1] if len(sys.argv) > 1 else 'BST:INJ:START'
CONNECT_TIMEOUT = 2.0

ctx = Context()
pv, = ctx.get_pvs(PV_NAME, timeout=CONNECT_TIMEOUT)


def access_name(rights):
    if rights is None:
        return None
    r = AccessRights(rights)
    if AccessRights.WRITE in r and AccessRights.READ in r:
        return 'READ_WRITE'
    if AccessRights.WRITE in r:
        return 'WRITE'
    if AccessRights.READ in r:
        return 'READ'
    return 'NO_ACCESS'


def connected():
    try:
        pv.wait_for_connection(timeout=CONNECT_TIMEOUT)
        return True
    except Exception:
        return False


def read_value():
    resp = pv.read(data_type=ChannelType.CTRL_ENUM if pv.channel.native_data_type == ChannelType.ENUM
                   else None, timeout=CONNECT_TIMEOUT)
    value = resp.data.tolist()[0] if hasattr(resp.data, 'tolist') else resp.data[0]
    if isinstance(value, bytes):
        value = value.decode('latin-1')
    enum_strings = None
    md = getattr(resp, 'metadata', None)
    if md is not None and hasattr(md, 'enum_strings'):
        enum_strings = [s.decode('latin-1') if isinstance(s, bytes) else s
                        for s in md.enum_strings][:md.no_str]
    return value, enum_strings


def probe():
    if not connected():
        return {'ok': True, 'pv': PV_NAME, 'connected': False, 'access': None,
                'error': f'{PV_NAME} not found / not connected'}
    out = {'ok': True, 'pv': PV_NAME, 'connected': True,
           'access': access_name(pv.access_rights),
           'native_type': pv.channel.native_data_type.name}
    try:
        out['host'] = '%s:%s' % pv.circuit_manager.circuit.address
    except Exception:
        out['host'] = None
    try:
        out['value'], out['enum_strings'] = read_value()
    except Exception as exc:
        out['value'], out['read_error'] = None, str(exc)
    return out


def put(value):
    if not connected():
        return {'ok': False, 'error': f'{PV_NAME} not connected'}
    access = access_name(pv.access_rights)
    if access not in ('WRITE', 'READ_WRITE'):
        return {'ok': False, 'access': access,
                'error': f'write access denied by the IOC ({access}) - not sent'}
    t = time.time()
    pv.write([value], wait=False, notify=False)
    reply = {'ok': True, 'sent_at': t, 'access': access, 'value': value}
    try:
        reply['readback'], _ = read_value()
    except Exception as exc:
        reply['readback_error'] = str(exc)
    return reply


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = {}
        try:
            req = json.loads(line)
            op = req.get('op')
            if op == 'probe':
                reply = probe()
            elif op == 'put':
                reply = put(int(req['value']))
            else:
                reply = {'ok': False, 'error': f'unknown op {op!r}'}
        except Exception as exc:
            reply = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        reply['id'] = req.get('id') if isinstance(req, dict) else None
        sys.stdout.write(json.dumps(reply) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    try:
        main()
    finally:
        try:
            ctx.disconnect()
        except Exception:
            pass
