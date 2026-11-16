#!/usr/bin/env python3
"""Emulates the StepperController ESP32 serial protocol on a pty, for local tests.

Prints the pty path, then serves forever. Two axes, trapezoid motion
(vmax 3200, accel 1600), pushes GETPOS/GETSPEED once a second while moving and
a full update every 10 s, like the real firmware. Limit switches: X low at
X <= XLOW, Y high at Y >= YHIGH (stop() = decelerate, like AccelStepper).
"""
import os
import select
import time
import tty

VMAX, ACC = 3200.0, 1600.0
XLOW, YHIGH = int(os.environ.get('EMU_XLOW', '-3000')), int(os.environ.get('EMU_YHIGH', '160000'))

master, slave = os.openpty()
tty.setraw(slave)
print(os.ttyname(slave), flush=True)
link = os.environ.get('EMU_LINK')
if link:
    try:
        os.unlink(link)
    except FileNotFoundError:
        pass
    os.symlink(os.ttyname(slave), link)


class Axis:
    def __init__(self):
        self.pos = 0.0
        self.v = 0.0
        self.target = 0.0
        self.enabled = os.environ.get('EMU_ENABLED', '0') == '1'

    def step(self, dt):
        if not self.enabled:
            self.v = 0.0
            return
        d = self.target - self.pos
        if abs(d) < 0.5 and abs(self.v) < 1:
            self.pos, self.v = round(self.target), 0.0
            return
        stop_dist = self.v * self.v / (2 * ACC)
        direction = 1 if d > 0 else -1
        if self.v * direction > 0 and stop_dist >= abs(d):
            a = -direction * ACC
        else:
            a = direction * ACC
        self.v = max(-VMAX, min(VMAX, self.v + a * dt))
        new = self.pos + self.v * dt
        if (self.target - new) * direction < 0 and abs(self.v) < ACC * dt * 2:
            new, self.v = self.target, 0.0
        self.pos = new

    def stop(self):
        sd = self.v * self.v / (2 * ACC)
        self.target = self.pos + (sd if self.v > 0 else -sd)


ax = [Axis(), Axis()]


def out(s):
    os.write(master, (s + '\n').encode())


def flags(i):
    p = ax[i].pos
    f = ''
    if i == 0 and p <= XLOW:
        f += 'L'
    if i == 1 and p >= YHIGH:
        f += 'U'
    return f


def getpos(i):
    out(f'GETPOS {i} {int(round(ax[i].pos))}{flags(i)}')


def getspeed(i):
    out(f'GETSPEED {i} {ax[i].v if abs(ax[i].v) > 0.01 else 0.0:f}')


def full():
    for i in range(2):
        getpos(i)
        getspeed(i)
        out(f'GETENABLED {i} {"ENABLED" if ax[i].enabled else "DISABLED"}')


out('Initializing 2 steppers.')
buf = b''
last_push = last_full = time.time()
last_pos = [None, None]
t_prev = time.time()
stopping = [False, False]
while True:
    r, _, _ = select.select([master], [], [], 0.01)
    if r:
        buf += os.read(master, 1024)
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            parts = line.decode().strip().split()
            if not parts:
                continue
            cmd = parts[0].upper()
            arg = parts[1:]
            try:
                if cmd == 'UPDATE':
                    full()
                elif cmd == 'MOVEABS':
                    i, v = int(arg[0]), float(arg[1])
                    out(f'MOVEABS {i} {int(v)}')
                    ax[i].target = v
                    stopping[i] = False
                elif cmd == 'MOVE':
                    i, v = int(arg[0]), float(arg[1])
                    ax[i].target = ax[i].pos + v
                    stopping[i] = False
                elif cmd == 'STOP':
                    if arg and arg[0].upper() == 'ALL':
                        for a in ax:
                            a.stop()
                        out('STOP ALL')
                    else:
                        ax[int(arg[0])].stop()
                elif cmd == 'GETPOS':
                    getpos(int(arg[0]))
                elif cmd == 'GETSPEED':
                    getspeed(int(arg[0]))
                elif cmd == 'GETENABLED':
                    i = int(arg[0])
                    out(f'GETENABLED {i} {"ENABLED" if ax[i].enabled else "DISABLED"}')
                elif cmd == 'GETMAXSPEED':
                    out(f'GETMAXSPEED {arg[0]} {VMAX:f}')
                elif cmd == 'GETACCEL':
                    out(f'GETACCEL {arg[0]} {ACC:f}')
                elif cmd in ('ENABLE', 'DISABLE'):
                    i = int(arg[0])
                    ax[i].enabled = cmd == 'ENABLE'
                    out(f'{cmd} {i}')
                elif cmd == 'SETPOS':
                    i = int(arg[0])
                    ax[i].pos = ax[i].target = float(arg[1])
                    out(f'SETPOS {i} {int(float(arg[1]))}')
            except Exception as exc:
                out(f'error {exc}')
    now = time.time()
    dt, t_prev = now - t_prev, now
    for i, a in enumerate(ax):
        a.step(dt)
        if i == 0 and a.pos <= XLOW and a.v < 0 and not stopping[i]:
            a.stop(); stopping[i] = True
        if i == 1 and a.pos >= YHIGH and a.v > 0 and not stopping[i]:
            a.stop(); stopping[i] = True
    if now - last_push >= 1.0:
        last_push = now
        if now - last_full >= 10.0:
            last_full = now
            full()
        else:
            for i in range(2):
                p = int(round(ax[i].pos))
                if p != last_pos[i]:
                    last_pos[i] = p
                    getpos(i)
                    getspeed(i)
