"""FLASH experiment web server (motion + automatic position-and-fire).

One site on pi-06-ioc, behind nginx on port 80:
    /            DoseCam (its own Flask app on 127.0.0.1:8000)
    /motion/     positioning camera (OV5647), manual moves, loadout, Y trim, terminal
    /run/        select targets, set pulses x delay, plan path, run / abort
    /socket.io/  live updates for /motion/ and /run/
This process listens on FLASH_HTTP_HOST:FLASH_HTTP_PORT (127.0.0.1:8081 on pi-06-ioc).
"""

# Monkey patch first, before anything imports socket/ssl/threading/subprocess.
from gevent import monkey
monkey.patch_all()

import glob
import io
import ipaddress
import os
import pwd
import signal
import struct
import subprocess
import sys
import time

import gevent
from flask import Flask, Response, jsonify, redirect, render_template, request
from flask_socketio import SocketIO
from gevent.event import Event
from gevent.lock import Semaphore

from firing import FIRE_PV, MODES, Firing, GatewaySettings, value_label
from loadout import Loadout
from sequencer import Sequencer, dosecam
from stepper_link import StepperLink

app = Flask(__name__, static_url_path='/motion/static')
socketio = SocketIO(app, async_mode="gevent")

HOME = os.path.expanduser('~')
LOADOUT_PATH = os.environ.get('FLASH_LOADOUT', os.path.join(HOME, '.config', 'flash', 'loadout.json'))
SETTINGS_PATH = os.environ.get('FLASH_SETTINGS', os.path.join(HOME, '.config', 'flash', 'settings.json'))
RUN_DIR = os.environ.get('FLASH_RUN_DIR', os.path.join(HOME, 'flash_runs'))
# Networks that may watch and abort but not start runs or fire (DoseCam Wi-Fi hotspot).
RUN_DENY_NETS = [ipaddress.ip_network(n.strip()) for n in
                 os.environ.get('FLASH_RUN_DENY_NETS', '192.168.50.0/24').split(',') if n.strip()]
# Commands the terminal/manual controls may still send while a run is active.
RUN_ALLOWED_CMDS = ('STOP', 'UPDATE', 'GETPOS', 'GETSPEED', 'GETENABLED', 'GETMAXSPEED',
                    'GETACCEL', 'GETTARGET', 'LIST', '?')


def serial_line(line):
    socketio.emit('serial_output', {'message': line})


def state_changed(snapshot):
    socketio.emit('state', snapshot)


link = StepperLink(os.environ.get('FLASH_SERIAL_PORT', '/dev/ttyACM0'),
                   on_line=serial_line, on_state=state_changed)
gateway_settings = GatewaySettings(SETTINGS_PATH)
firing = Firing(gateway_settings, FIRE_PV, on_status=lambda s: socketio.emit('pv_status', s))
loadout = Loadout(LOADOUT_PATH)
sequencer = Sequencer(link, firing, lambda name, payload: socketio.emit(name, payload), RUN_DIR)


def client_ip():
    # nginx sets X-Real-IP; this server only listens on 127.0.0.1 behind it.
    return request.headers.get('X-Real-IP') or request.remote_addr or '?'


def run_denied():
    try:
        ip = ipaddress.ip_address(client_ip())
    except ValueError:
        return None
    for net in RUN_DENY_NETS:
        if ip in net:
            return f'not allowed from {net} (DoseCam Wi-Fi hotspot) - watch and abort only'
    return None


# --------------------------------------------------------------------------
# Shared camera
#
# One child process (camera_worker.py) owns the camera and streams JPEGs over
# a pipe. Every browser viewing /video_feed is served from that one stream, so
# any number of people can watch at once without fighting over the camera.
# A watchdog restarts the worker if frames stop, and /camera/reset lets a user
# force that from the web page - including stopping some other program that is
# holding the camera.
# --------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, 'camera_worker.py')
FRAME_SIZE = (640, 480)
STARTUP_GRACE_S = 15    # time allowed for the camera to deliver its first frame
STALL_S = 5             # no frame for this long while streaming = wedged
IDLE_STOP_S = 30        # release the camera this long after the last viewer leaves
BACKOFF_S = (2, 5, 10, 30)
KEEPALIVE_S = 2         # resend the current image this often when no new frames arrive
CAMERA_DEVICE_GLOBS = ('/dev/media*',)
# Command-line substrings of processes the Reset button must never stop. On a Pi
# shared with DoseCam set this to e.g. "rpicam-,dose_cam" in the service environment.
PROTECTED_PROCESSES = tuple(p.strip() for p in os.environ.get('FLASH_PROTECTED_PROCESSES', '').split(',') if p.strip())


def log(message):
    print(f"camera: {message}", flush=True)


class CameraHub:
    def __init__(self):
        self.proc = None
        self.frame = None
        self.frame_id = 0
        self.frame_time = 0.0
        self.new_frame = Event()
        self.viewers = 0
        self.last_viewer_time = 0.0
        self.state = 'idle'          # idle | starting | streaming | stalled | error | stopped
        self.last_error = None
        self.started_at = 0.0
        self.restarts = 0
        self.failures = 0
        self.next_try = 0.0
        self.fps = 0.0
        self._fps_count = 0
        self._fps_t0 = time.time()
        self.lock = Semaphore()
        # /proc/locks keys ("maj:min:inode") of the media devices our worker locks
        # while streaming. Learned at runtime, so on a Pi with two cameras the Reset
        # button only ever acts on this app's camera. Valid until reboot.
        self.our_devices = set()

    # ---- worker lifecycle ------------------------------------------------
    def _spawn(self):
        cmd = [sys.executable, '-u', WORKER, str(FRAME_SIZE[0]), str(FRAME_SIZE[1])]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL, cwd=HERE)
        self.state = 'starting'
        self.started_at = time.time()
        self.frame_time = 0.0
        self.restarts += 1
        log(f"started worker pid {self.proc.pid}")
        gevent.spawn(self._read_frames, self.proc)
        gevent.spawn(self._read_stderr, self.proc)

    def _read_frames(self, proc):
        out = proc.stdout
        try:
            while True:
                header = out.read(4)
                if len(header) < 4:
                    break
                (size,) = struct.unpack('>I', header)
                data = out.read(size)
                if len(data) < size:
                    break
                if proc is not self.proc:
                    break
                self.frame = data
                self.frame_id += 1
                self.frame_time = time.time()
                self.state = 'streaming'
                self.failures = 0
                self.last_error = None
                self._fps_count += 1
                event, self.new_frame = self.new_frame, Event()
                event.set()
        except Exception as exc:
            log(f"frame reader error: {exc}")
        code = proc.wait()
        if proc is self.proc:
            self.proc = None
            if self.state != 'stopped':
                self.state = 'error'
                if not self.last_error:
                    self.last_error = f'camera worker exited (code {code})'
                self._schedule_retry()
            log(f"worker pid {proc.pid} exited with code {code}")

    def _read_stderr(self, proc):
        for raw in proc.stderr:
            line = raw.decode('utf-8', 'replace').rstrip()
            if not line:
                continue
            print(line, flush=True)
            if 'ERROR' in line and proc is self.proc:
                self.last_error = line.split('ERROR', 1)[1].strip()

    def _kill(self, proc, grace=3.0):
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        except Exception:
            pass

    def _stop_worker(self, new_state):
        proc, self.proc = self.proc, None
        self.state = new_state
        self._kill(proc)

    def _schedule_retry(self):
        delay = BACKOFF_S[min(self.failures, len(BACKOFF_S) - 1)]
        self.failures += 1
        self.next_try = time.time() + delay

    # ---- watchdog --------------------------------------------------------
    def watchdog(self):
        while True:
            gevent.sleep(1)
            try:
                self._tick()
            except Exception as exc:
                log(f"watchdog error: {exc}")

    def _tick(self):
        now = time.time()
        if now - self._fps_t0 >= 2:
            self.fps = self._fps_count / (now - self._fps_t0)
            self._fps_count = 0
            self._fps_t0 = now
        if self.state == 'streaming' and self.proc is not None and not self.our_devices:
            keys = media_locks()[0].get(self.proc.pid)
            if keys:
                self.our_devices = set(keys)
                log(f"camera devices for this app: {sorted(media_locks()[1].get(k, k) for k in keys)}")
        with self.lock:
            running = self.proc is not None and self.proc.poll() is None
            if self.viewers > 0 and not running and now >= self.next_try:
                self._spawn()
            elif running and self.state == 'starting' and now - self.started_at > STARTUP_GRACE_S:
                self.last_error = f'no frame within {STARTUP_GRACE_S}s of starting the camera'
                log(self.last_error)
                self._stop_worker('stalled')
                self._schedule_retry()
            elif running and self.state == 'streaming' and now - self.frame_time > STALL_S:
                self.last_error = f'frames stopped for more than {STALL_S}s - restarted camera'
                log(self.last_error)
                self._stop_worker('stalled')
                self._schedule_retry()
            elif running and self.viewers == 0 and now - self.last_viewer_time > IDLE_STOP_S:
                log('no viewers - releasing camera')
                self._stop_worker('idle')

    # ---- viewers ---------------------------------------------------------
    def add_viewer(self):
        self.viewers += 1
        self.last_viewer_time = time.time()
        if self.proc is None and self.state in ('idle', 'stopped'):
            self.next_try = 0.0

    def remove_viewer(self):
        self.viewers = max(0, self.viewers - 1)
        self.last_viewer_time = time.time()

    # ---- reset -----------------------------------------------------------
    def reset(self, stop_others=False):
        report = {'stopped_worker': None, 'stopped_others': [], 'could_not_stop': []}
        with self.lock:
            if self.proc is not None:
                report['stopped_worker'] = self.proc.pid
            self._stop_worker('stopped')
            if stop_others:
                for holder in camera_holders(exclude_pids={os.getpid()}):
                    if not holder['stoppable']:
                        report['could_not_stop'].append(dict(holder, result=holder['note']))
                        continue
                    ok, why = terminate_pid(holder['pid'])
                    entry = dict(holder, result=why)
                    (report['stopped_others'] if ok else report['could_not_stop']).append(entry)
            self.failures = 0
            self.last_error = None
            self.next_try = 0.0
            self.state = 'idle'
        log(f"reset requested: {report}")
        report['other_holders'] = camera_holders(exclude_pids={os.getpid()})
        return report

    def status(self):
        now = time.time()
        return {
            'state': self.state,
            'viewers': self.viewers,
            'fps': round(self.fps, 1),
            'last_frame_age_s': round(now - self.frame_time, 1) if self.frame_time else None,
            'worker_pid': self.proc.pid if self.proc is not None else None,
            'last_error': self.last_error,
            'restarts': self.restarts,
            'retry_in_s': round(max(0.0, self.next_try - now), 1) if self.proc is None and self.viewers else None,
        }


camera = CameraHub()


def media_locks():
    """({pid: {lock keys}}, {lock key: /dev/mediaN}) for POSIX locks on camera media devices.

    libcamera claims a camera by taking a POSIX lock (lockf) on its /dev/media*
    nodes, so /proc/locks names exactly who is blocking a camera - including
    processes owned by other accounts. Programs that merely keep the device open
    (PipeWire/WirePlumber do this all the time) hold no lock and do not appear.
    """
    nodes = {}
    for pattern in CAMERA_DEVICE_GLOBS:
        for path in glob.glob(pattern):
            try:
                st = os.stat(path)
            except OSError:
                continue
            nodes[f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"] = path
    locked = {}
    try:
        with open('/proc/locks') as fh:
            for line in fh:
                fields = line.split()
                if len(fields) < 6 or '->' in fields:
                    continue  # malformed, or a process waiting on a lock rather than holding it
                pid_s, key = fields[4], fields[5]
                if key in nodes and pid_s.isdigit():
                    locked.setdefault(int(pid_s), set()).add(key)
    except OSError as exc:
        log(f"cannot read /proc/locks: {exc}")
    return locked, nodes


def camera_holders(exclude_pids=()):
    """Processes holding a lock on THIS app's camera, with whether Reset may stop them.

    Once our worker has streamed, only processes locking one of its media devices
    are listed, so another app's camera on the same Pi (DoseCam) is never touched.
    Before that is known, every lock holder is listed but processes matching
    FLASH_PROTECTED_PROCESSES are never offered for stopping.
    """
    locked, nodes = media_locks()
    ours = camera.our_devices
    holders = []
    for pid, keys in sorted(locked.items()):
        if pid in exclude_pids:
            continue
        if ours and not (keys & ours):
            continue  # some other camera on this Pi
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as fh:
                cmdline = fh.read().replace(b'\0', b' ').decode('utf-8', 'replace').strip()
            user = pwd.getpwuid(os.stat(f'/proc/{pid}').st_uid).pw_name
        except Exception:
            cmdline, user = '?', '?'
        is_ours = camera.proc is not None and pid == camera.proc.pid
        protected = any(p in cmdline for p in PROTECTED_PROCESSES)
        if is_ours:
            stoppable, note = True, "this app's camera worker"
        elif protected:
            stoppable, note = False, 'protected process (FLASH_PROTECTED_PROCESSES) - not stopped'
        else:
            stoppable, note = True, ('holds this camera' if ours else 'holds a camera lock')
        holders.append({
            'pid': pid,
            'user': user,
            'command': cmdline[:200],
            'devices': sorted(nodes.get(k, k) for k in keys),
            'is_our_worker': is_ours,
            'stoppable': stoppable,
            'note': note,
        })
    return holders


def _pid_alive(pid):
    """True if the process exists and has not already exited (zombies count as gone)."""
    try:
        with open(f'/proc/{pid}/stat') as fh:
            return fh.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return False


def terminate_pid(pid, grace=3.0):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, 'already gone'
    except PermissionError:
        return False, 'permission denied (owned by another account)'
    deadline = time.time() + grace
    while time.time() < deadline:
        gevent.sleep(0.2)
        if not _pid_alive(pid):
            return True, 'stopped'
    try:
        os.kill(pid, signal.SIGKILL)
        gevent.sleep(0.5)
        return True, 'killed'
    except ProcessLookupError:
        return True, 'stopped'
    except PermissionError:
        return False, 'permission denied (owned by another account)'


_placeholder_cache = {}


def placeholder_jpeg(title, detail=''):
    """Explanatory frame shown in the video while the camera is unavailable (PIL; no OpenCV)."""
    key = (title, detail)
    if key not in _placeholder_cache:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', FRAME_SIZE, (23, 26, 28))
        draw = ImageDraw.Draw(img)
        try:
            big = ImageFont.truetype('DejaVuSans-Bold.ttf', 30)
            small = ImageFont.truetype('DejaVuSans.ttf', 16)
        except OSError:
            big = small = ImageFont.load_default()
        draw.text((24, 190), title, fill=(235, 235, 235), font=big)
        y = 240
        for chunk in [detail[i:i + 60] for i in range(0, len(detail), 60)][:5]:
            draw.text((24, y), chunk, fill=(200, 190, 170), font=small)
            y += 24
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        if len(_placeholder_cache) > 32:
            _placeholder_cache.clear()
        _placeholder_cache[key] = buf.getvalue()
    return _placeholder_cache[key]


def _part(jpeg):
    return (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
            + str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')


def gen_frames():
    camera.add_viewer()
    try:
        last_id = -1
        while True:
            event = camera.new_frame
            if camera.frame_id == last_id:
                event.wait(timeout=KEEPALIVE_S)
            if camera.frame_id != last_id and camera.state == 'streaming':
                last_id = camera.frame_id
                yield _part(camera.frame)
            elif camera.state != 'streaming':
                # Keep the connection alive with an explanatory image; the real
                # feed resumes in this same connection once the camera is back.
                if camera.state in ('idle', 'starting'):
                    jpeg = placeholder_jpeg('Starting camera...')
                else:
                    jpeg = placeholder_jpeg('CAMERA OFFLINE', camera.last_error or camera.state)
                yield _part(jpeg)
                last_id = camera.frame_id
            else:
                # streaming but no new frame within KEEPALIVE_S: resend the last one
                yield _part(camera.frame)
    finally:
        camera.remove_viewer()




# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
@app.route('/')
def root():
    return redirect('/motion/')


@app.route('/motion')
@app.route('/run')
def no_slash():
    return redirect(request.path + '/')


@app.route('/motion/')
def motion_page():
    return render_template('index.html')


@app.route('/run/')
def run_page():
    return render_template('run.html', fire_pv=FIRE_PV)


@app.route('/settings')
def settings_no_slash():
    return redirect('/settings/')


@app.route('/settings/')
def settings_page():
    return render_template('settings.html', fire_pv=FIRE_PV)


# --------------------------------------------------------------------------
# camera (OV5647 positioning camera)
# --------------------------------------------------------------------------
@app.route('/motion/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


@app.route('/motion/camera/status')
def camera_status():
    return jsonify(camera.status())


@app.route('/motion/camera/holders')
def camera_holders_route():
    return jsonify(camera_holders(exclude_pids={os.getpid()}))


@app.route('/motion/camera/reset', methods=['POST'])
def camera_reset():
    body = request.get_json(silent=True) or {}
    return jsonify(camera.reset(stop_others=bool(body.get('stop_others'))))


# --------------------------------------------------------------------------
# shared state
# --------------------------------------------------------------------------
@app.route('/motion/api/state')
def api_state():
    return jsonify({'stepper': link.snapshot(), 'run_state': sequencer.state})


@app.route('/motion/api/loadout', methods=['GET', 'PUT'])
def api_loadout():
    if request.method == 'GET':
        return jsonify(loadout.get())
    if sequencer.active:
        return jsonify({'ok': False, 'error': 'a run is in progress - loadout is locked'}), 409
    try:
        data = loadout.update(request.get_json(force=True) or {})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    socketio.emit('loadout', data)
    return jsonify(data)


# --------------------------------------------------------------------------
# run (automatic positioning and firing)
# --------------------------------------------------------------------------
def _err(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


@app.route('/run/api/status')
def run_status():
    s = sequencer.status()
    s.update(ok=True, stepper=link.snapshot(), pv=firing.status_view(), modes=MODES,
             run_allowed_here=run_denied() is None, client=client_ip())
    return jsonify(s)


@app.route('/run/api/pv')
def run_pv():
    st = firing.full_check() if request.args.get('refresh') else firing.status_view()
    value = loadout.get()['fire']['value']
    st.update(ok=True, fire_value=value, fire_value_label=value_label(st, value),
              live_available=firing.can_write(), live_route=firing.live_route())
    return jsonify(st)


@app.route('/run/api/preflight')
def run_preflight():
    """Checks shown before a run. Nothing here changes hardware state."""
    lo = loadout.get()
    checks = []

    def add(name, ok, detail, level='error'):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail, 'level': 'ok' if ok else level})

    fresh = link.fresh_update(timeout=2.0) if link.connected else False
    add('Stepper controller', link.connected and fresh,
        f'{link.port}' + ('' if fresh else ' - no reply to UPDATE'))
    en = link.state['enabled']
    add('Motors enabled', link.all_enabled(), f'motor 0 {en[0]}, motor 1 {en[1]} (enable on Motion > Motors)')
    add('Access position', lo['access'] is not None,
        f'{lo["access"]}' if lo['access'] else 'not set - move the holder left/up and press "Set access = current"')
    pv = firing.full_check()
    add(f'{FIRE_PV} readable (CA status)', pv.get('connected'),
        f'{pv.get("host") or pv.get("error")}, value {pv.get("value")}', 'warn')
    if pv.get('transport') == 'ssh':
        add('Live firing via ssh gateway', firing.can_write(),
            f'{pv.get("ssh_target")}: access {(pv.get("ssh_info") or {}).get("access")}'
            + ('' if firing.can_write() else f' - {pv.get("ssh_error")} - Simulate and Assisted only'), 'warn')
    else:
        add('Live firing allowed', firing.can_write(),
            f'CA access {pv.get("access")} from this host'
            + ('' if firing.can_write() else ' - no ssh gateway configured - Simulate and Assisted only'), 'warn')
    if lo['run'].get('dosecam'):
        s = dosecam('GET', '/api/acquisition/status')
        add('DoseCam reachable', s.get('ok'), s.get('error') or (s.get('status') or {}).get('message', ''))
    e = dosecam('GET', '/api/esp_status')
    level = ((e.get('status') or {}).get('input_active_level')) if e.get('ok') else None
    add('ESP8266 input polarity', level == 'LOW',
        f'input_active_level={level}' + ('' if level == 'LOW' else
                                         ' - the opto-isolated trigger needs LOW (it resets to HIGH at boot)'),
        'warn')
    return jsonify({'ok': True, 'checks': checks, 'esp_input_level': level})


@app.route('/run/api/esp_active_low', methods=['POST'])
def run_esp_active_low():
    if (why := run_denied()):
        return _err(why, 403)
    if sequencer.active:
        return _err('a run is in progress', 409)
    r = dosecam('POST', '/api/esp_active_level', {'level': 0})
    return jsonify(r), (200 if r.get('ok') else 502)


@app.route('/run/api/plan', methods=['POST', 'DELETE'])
def run_plan():
    if (why := run_denied()):
        return _err(why, 403)
    try:
        if request.method == 'DELETE':
            sequencer.clear_plan()
            return jsonify({'ok': True})
        body = request.get_json(force=True) or {}
        lo = loadout.get()
        plan = sequencer.make_plan(body.get('stops'), lo['access'], lo['run']['settle_s'])
        return jsonify({'ok': True, 'plan': plan})
    except Exception as exc:
        return _err(str(exc))


@app.route('/run/api/start', methods=['POST'])
def run_start():
    if (why := run_denied()):
        return _err(why, 403)
    body = request.get_json(force=True) or {}
    mode = body.get('mode', 'simulate')
    if mode == 'live' and body.get('confirm') != FIRE_PV:
        return _err(f'live mode needs confirm="{FIRE_PV}"')
    lo = loadout.get()
    options = dict(lo['run'])
    try:
        run = sequencer.start(body.get('plan_id'), mode, lo['fire']['value'], options, client_ip())
    except Exception as exc:
        return _err(str(exc), 409)
    return jsonify({'ok': True, 'run': run})


@app.route('/run/api/abort', methods=['POST'])
def run_abort():
    # Allowed from everywhere, including the hotspot.
    return jsonify({'ok': True, **sequencer.abort(client_ip())})


@app.route('/run/api/continue', methods=['POST'])
def run_continue():
    if (why := run_denied()):
        return _err(why, 403)
    body = request.get_json(force=True) or {}
    try:
        sequencer.operator(body.get('action', 'fired'), client_ip())
    except Exception as exc:
        return _err(str(exc), 409)
    return jsonify({'ok': True})


@app.route('/run/api/access', methods=['POST'])
def run_access():
    if (why := run_denied()):
        return _err(why, 403)
    if sequencer.active:
        return _err('a run is in progress', 409)
    body = request.get_json(force=True) or {}
    if body.get('from_current'):
        if not link.fresh_update(timeout=2.0):
            return _err('no reply from the stepper controller')
        x, y = link.state['pos'][0], link.state['pos'][1]
    else:
        x, y = body.get('x'), body.get('y')
    try:
        data = loadout.update({'access': {'x': x, 'y': y}})
    except Exception as exc:
        return _err(str(exc))
    socketio.emit('loadout', data)
    return jsonify({'ok': True, 'access': data['access']})


@app.route('/run/api/goto_access', methods=['POST'])
def run_goto_access():
    if (why := run_denied()):
        return _err(why, 403)
    if sequencer.active:
        return _err('a run is in progress', 409)
    acc = loadout.get()['access']
    if acc is None:
        return _err('access position not set')
    if not link.all_enabled():
        return _err('both motors must be ENABLED')
    ok = link.write(f'MOVEABS 0 {acc["x"]}') and link.write(f'MOVEABS 1 {acc["y"]}')
    serial_line(f'[run page] move to access ({acc["x"]}, {acc["y"]}) from {client_ip()}')
    return jsonify({'ok': ok})


# --------------------------------------------------------------------------
# settings (firing gateway account/host/key, PV value, run defaults)
# --------------------------------------------------------------------------
def _settings_view():
    return {'ok': True, 'gateway': gateway_settings.get(), 'public_key': firing.public_key(),
            'key_exists': os.path.exists(firing.key_path()),
            'authorized_keys_line': firing.authorized_keys_line(),
            'host_trusted': firing.host_trusted(), 'pv': firing.status_view(),
            'loadout': loadout.get(), 'edit_allowed_here': run_denied() is None, 'client': client_ip()}


def _settings_guard():
    if (why := run_denied()):
        return _err(why, 403)
    if sequencer.active:
        return _err('a run is in progress', 409)
    return None


@app.route('/settings/api')
def settings_get():
    return jsonify(_settings_view())


@app.route('/settings/api/gateway', methods=['PUT'])
def settings_gateway():
    if (bad := _settings_guard()):
        return bad
    try:
        gateway_settings.update(request.get_json(force=True) or {})
    except Exception as exc:
        return _err(str(exc))
    firing.close_session()
    firing.status.update(ssh_ok=None, ssh_info=None, ssh_error='settings changed - not checked yet')
    socketio.emit('pv_status', firing.status_view())
    return jsonify(_settings_view())


@app.route('/settings/api/create_key', methods=['POST'])
def settings_create_key():
    if (bad := _settings_guard()):
        return bad
    try:
        firing.create_key()
    except Exception as exc:
        return _err(str(exc))
    return jsonify(_settings_view())


@app.route('/settings/api/keyscan', methods=['POST'])
def settings_keyscan():
    if (bad := _settings_guard()):
        return bad
    try:
        return jsonify({'ok': True, 'keys': firing.keyscan()})
    except Exception as exc:
        return _err(str(exc), 502)


@app.route('/settings/api/trust', methods=['POST'])
def settings_trust():
    if (bad := _settings_guard()):
        return bad
    try:
        n = firing.trust_host_keys((request.get_json(force=True) or {}).get('lines') or [])
    except Exception as exc:
        return _err(str(exc))
    return jsonify(dict(_settings_view(), trusted=n))


@app.route('/settings/api/check', methods=['POST'])
def settings_check():
    if (bad := _settings_guard()):
        return bad
    st = firing.full_check()
    socketio.emit('pv_status', st)
    return jsonify(_settings_view())


# --------------------------------------------------------------------------
# Socket.IO
# --------------------------------------------------------------------------
@socketio.on('connect')
def on_connect():
    socketio.emit('state', link.snapshot(), to=request.sid)
    socketio.emit('run_status', {'state': sequencer.state, 'run': sequencer.run,
                                 'plan_id': sequencer.plan and sequencer.plan['plan_id']}, to=request.sid)


@socketio.on('send_command')
def handle_command(data):
    command = str((data or {}).get('command', '')).strip()[:200]
    if not command:
        return
    if sequencer.active and not command.upper().startswith(RUN_ALLOWED_CMDS):
        socketio.emit('serial_output', {'message': f'Blocked during run: {command} (use ABORT on the Run page)'},
                      to=request.sid)
        return
    if link.write(command):
        socketio.emit('serial_output', {'message': f'Sent: {command}'})
    else:
        socketio.emit('serial_output', {'message': f'NOT sent (controller not connected): {command}'},
                      to=request.sid)


if __name__ == '__main__':
    gevent.spawn(link.run)
    gevent.spawn(camera.watchdog)
    gevent.spawn(firing.monitor)
    socketio.run(app, host=os.environ.get('FLASH_HTTP_HOST', '0.0.0.0'),
                 port=int(os.environ.get('FLASH_HTTP_PORT', '80')))
