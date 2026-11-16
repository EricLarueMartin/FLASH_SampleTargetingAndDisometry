# FLASH live firing through an SSH gateway

In Live mode the Run page fires `BST:INJ:START` with one put (no callback, the
same as `caput BST:INJ:START 1`) per pulse. pi-06-ioc has only READ access to
that PV, so each put is made on a control-room host, in the account the IOC
already lets write (ringop), over SSH. The Pi needs no EPICS write access and no
ACF change. `repeatPut.sh` is not used.

## Timing

* One SSH session is opened at the start of a live run and kept for the whole run.
  On the gateway, `flash_fire_gw.py serve` keeps the PV connected and does one put
  per line it receives, so a pulse costs one LAN round trip plus the put (a few ms).
  It uses pyepics if installed, else caproto, else runs `caput` per pulse
  (tens of ms; still on schedule, just a larger send time).
* The schedule is a clock, not a chain of sleeps: at a position, pulse k is sent
  at t0 + k * delay on a monotonic clock that keeps running. A slow send or late
  wake-up does not push the later pulses back, so N pulses span (N-1) * delay.
* Every pulse is logged with its send offset, lateness and round trip, and each
  position ends with a line like
  `S1-A1: 40 pulses, first to last 3.900 s (scheduled 3.900 s, error +0.0 ms); send lateness max 0.1 ms; put round trip mean 2.1 ms, max 4.0 ms`.

## What the key can do

`flash_fire_gw.py` is installed as the forced command for the Pi's key:

| request   | effect |
|-----------|--------|
| `check`   | read only: connect to the PV, print access rights, value, backend |
| `serve`   | session: `put <value>` (value must be in `ALLOWED_VALUES`, default {1}), `ping`, `quit` |

Anything else is refused. Every put and refusal is appended to `~/flash_fire.log`.
The PV name is fixed in the script.

## Set up (once)

Everything on the Pi side is on the **Settings** page (http://pi-06-ioc/settings/):

1. Enter account (`ringop`), gateway host, and the path where the script will live
   on that host. Save.
2. **Create key on this Pi**. The page shows the exact `authorized_keys` line, e.g.

   ```
   command="/home/ringop/bin/flash_fire_gw.py",from="192.168.16.62",restrict ssh-ed25519 AAAA... flash-fire@pi-06-ioc
   ```

3. On the gateway host, as ringop: copy `flash_fire_gw.py` to that path,
   `chmod 755` it, and add the line to `~/.ssh/authorized_keys`. If ringop gets its
   CA settings from `.login`, uncomment the `EPICS_CA_*` lines at the top of the
   script (forced commands do not run a login shell).
4. **Get host key**, compare the fingerprint with the host
   (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`), **Trust**.
5. **Test connection** (read only). It must report `"access": "read, write"`.

The Run page's Live mode is enabled once the test passes, and a live run still
asks you to type the PV name.

## What it does not do

It never retries a failed or refused put (the run stops there), and it is not a
safety system: PSS, MPS and interlocks are independent of it.
