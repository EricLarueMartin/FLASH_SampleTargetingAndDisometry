"""Server-side loadout: what is loaded in each section, the target null adjust,
Y-trim table, access (park) position and the run-page target selections.

Stored as JSON so the Motion and Run pages (and every browser) agree.
"""

import copy
import json
import os
import threading

PLATE_TYPES = ('3x2', '4x3', '6x4', '12x8', 'tubes', 'puptubes', 'l4l5tubes', 'microtubes')

DEFAULT = {
    'sections': {'1': '4x3', '2': '4x3'},
    'targetOffsetMm': {'x': 0.0, 'y': 0.0},
    'yCorrections': [],
    'access': None,                 # {'x': steps, 'y': steps}; holder all the way left and up
    'fire': {'value': 1},
    'run': {'settle_s': 1.0, 'tolerance_steps': 2, 'default_pulses': 1, 'default_delay': 1.0,
            'dosecam': False, 'gate_width_us': 100, 'esp_delay_us': 200},
    'targets': {},                  # id -> {'pulses': n, 'delay': s}; id like "1:B3" (section:well)
    'version': 0,
}


def _num(v, lo=None, hi=None, kind=float):
    v = kind(v)
    if v != v:  # NaN
        raise ValueError('not a number')
    if lo is not None and v < lo or hi is not None and v > hi:
        raise ValueError(f'{v} out of range')
    return v


class Loadout:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = copy.deepcopy(DEFAULT)
        try:
            with open(path) as fh:
                saved = json.load(fh)
            self.data = self._merge(saved)
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f'loadout: could not read {path}: {exc} - using defaults', flush=True)

    def _merge(self, incoming, base=None):
        out = copy.deepcopy(base or self.data)
        if 'sections' in incoming:
            for k in ('1', '2'):
                t = incoming['sections'].get(k, out['sections'][k])
                if t not in PLATE_TYPES:
                    raise ValueError(f'unknown holder type {t!r}')
                out['sections'][k] = t
        if 'targetOffsetMm' in incoming:
            out['targetOffsetMm'] = {a: _num(incoming['targetOffsetMm'].get(a, 0), -100, 100)
                                     for a in ('x', 'y')}
        if 'yCorrections' in incoming:
            out['yCorrections'] = sorted(
                ({'x': _num(c['x']), 'y': _num(c['y'])} for c in incoming['yCorrections']),
                key=lambda c: c['x'])
        if 'access' in incoming:
            a = incoming['access']
            out['access'] = None if a is None else {'x': int(_num(a['x'])), 'y': int(_num(a['y']))}
        if 'fire' in incoming:
            out['fire']['value'] = int(_num(incoming['fire'].get('value', 1), 0, 15, int))
        if 'run' in incoming:
            r = incoming['run']
            spec = {'settle_s': (0, 60, float), 'tolerance_steps': (0, 50, int),
                    'default_pulses': (1, 10000, int), 'default_delay': (0, 3600, float),
                    'gate_width_us': (1, 100000, int), 'esp_delay_us': (0, 1000000, int)}
            for k, (lo, hi, kind) in spec.items():
                if k in r:
                    out['run'][k] = _num(r[k], lo, hi, kind)
            if 'dosecam' in r:
                out['run']['dosecam'] = bool(r['dosecam'])
        if 'targets' in incoming:
            t = {}
            for k, v in (incoming['targets'] or {}).items():
                t[str(k)[:20]] = {'pulses': int(_num(v.get('pulses', 1), 1, 10000, int)),
                                  'delay': _num(v.get('delay', 1.0), 0, 3600)}
            out['targets'] = t
        return out

    def get(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def update(self, incoming):
        with self.lock:
            new = self._merge(incoming)
            new['version'] = self.data.get('version', 0) + 1
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w') as fh:
                json.dump(new, fh, indent=1)
            os.replace(tmp, self.path)
            self.data = new
            return copy.deepcopy(new)
