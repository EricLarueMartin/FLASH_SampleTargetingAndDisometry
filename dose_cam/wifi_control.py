"""Manage only DoseCam's Wi-Fi profiles; never modify Ethernet profiles."""
import ipaddress
import os
import subprocess
import threading
import time

PROFILES = {"ap": "dosecam-hotspot", "client": "dosecam-client"}


class WifiControl:
    def __init__(self):
        self.lock = threading.Lock()
        self.busy = False
        self.message = ""

    def nm(self, *args):
        result = subprocess.run(
            ["sudo", "-n", "nmcli", "--wait", "25", *args],
            capture_output=True, text=True, timeout=35,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode:
            # Do not include the command or password in errors.
            raise RuntimeError(result.stderr.strip() or "Wi-Fi command failed")
        return result.stdout.strip()

    def exists(self, name):
        return name in self.nm("-g", "NAME", "connection", "show").splitlines()

    def value(self, name, prop):
        return self.nm("-g", prop, "connection", "show", name)

    def status(self):
        active = self.nm("-g", "GENERAL.CONNECTION", "device", "show", "wlan0")
        profiles = {}
        for mode, name in PROFILES.items():
            profiles[mode] = {"ssid": "DoseCam" if mode == "ap" else "", "ip": "192.168.50.1", "saved": False}
            if self.exists(name):
                profiles[mode].update(saved=True, ssid=self.value(name, "802-11-wireless.ssid"))
                if mode == "ap":
                    profiles[mode]["ip"] = self.value(name, "ipv4.addresses").split("/")[0]
        return dict(profiles=profiles, mode=next((m for m, n in PROFILES.items() if n == active), "off"),
                    active_connection=active, address=self.nm("-g", "IP4.ADDRESS", "device", "show", "wlan0"),
                    busy=self.busy, message=self.message)

    def start(self, data):
        mode = data.get("mode")
        if mode not in ("off", "ap", "client"):
            raise ValueError("Choose hotspot, join Wi-Fi, or off")
        ssid = str(data.get("ssid", ""))
        password = str(data.get("password", ""))
        address = str(data.get("ip", "192.168.50.1"))
        if mode != "off":
            if not 1 <= len(ssid.encode("utf-8")) <= 32 or any(ord(c) < 32 for c in ssid):
                raise ValueError("Wi-Fi name must be 1–32 bytes with no control characters")
            if password and (not 8 <= len(password) <= 63 or not all(32 <= ord(c) <= 126 for c in password)):
                raise ValueError("Password must contain 8–63 printable ASCII characters")
            if not password and (not self.exists(PROFILES[mode]) or self.value(PROFILES[mode], "802-11-wireless.ssid") != ssid):
                raise ValueError("Enter a password for a new Wi-Fi network")
        if mode == "ap":
            ip = ipaddress.IPv4Address(address)
            private = any(ip in ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
            net = ipaddress.ip_network(address + "/24", strict=False)
            if not private or ip in (net.network_address, net.broadcast_address):
                raise ValueError("Use a private IPv4 host address, e.g. 192.168.50.1 (a /24 network is used)")
            # Avoid overlapping any existing non-Wi-Fi interface network.
            import json
            result = subprocess.run(["ip", "-j", "-4", "address"], capture_output=True, text=True, check=True)
            for interface in json.loads(result.stdout):
                if interface["ifname"] == "wlan0":
                    continue
                for addr in interface.get("addr_info", []):
                    other = ipaddress.ip_network(f"{addr['local']}/{addr['prefixlen']}", strict=False)
                    if net.overlaps(other):
                        raise ValueError("Hotspot subnet overlaps another Pi interface; choose a different address")
        with self.lock:
            if self.busy:
                raise ValueError("A Wi-Fi change is already running")
            self.busy = True
            self.message = "Applying Wi-Fi settings…"
        threading.Thread(target=self.apply, args=(mode, ssid, password, address), daemon=True).start()

    def apply(self, mode, ssid, password, address):
        previous = None
        backup = None
        name = PROFILES.get(mode)
        try:
            time.sleep(1)  # Let the HTTP response reach a phone before its Wi-Fi changes.
            previous = self.nm("-g", "GENERAL.CONNECTION", "device", "show", "wlan0")
            if mode == "off":
                for name in PROFILES.values():
                    if self.exists(name):
                        self.nm("connection", "modify", name, "connection.autoconnect", "no")
                self.nm("radio", "wifi", "off")
                self.message = "Wi-Fi off"
                return
            name = PROFILES[mode]
            if self.exists(name):
                fields = ["802-11-wireless.ssid", "802-11-wireless.mode", "802-11-wireless-security.key-mgmt", "802-11-wireless-security.psk",
                          "ipv4.method", "ipv4.addresses", "ipv4.never-default", "connection.autoconnect"]
                backup = []
                for field in fields:
                    value = self.nm("--show-secrets", "-g", field, "connection", "show", name)
                    backup.extend([field, value])
            if not self.exists(name):
                self.nm("connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", name,
                        "ssid", ssid, "connection.autoconnect", "no")
            settings = ["802-11-wireless.ssid", ssid, "802-11-wireless.mode", "ap" if mode == "ap" else "infrastructure",
                        "wifi-sec.key-mgmt", "wpa-psk", "ipv6.method", "disabled", "connection.autoconnect", "no",
                        "ipv4.method", "shared" if mode == "ap" else "auto", "ipv4.never-default", "yes" if mode == "ap" else "no",
                        "ipv4.route-metric", "600", "ipv4.addresses", address + "/24" if mode == "ap" else ""]
            if mode == "ap":
                settings += ["802-11-wireless.band", "bg", "802-11-wireless.channel", "6", "wifi-sec.proto", "rsn"]
            if password:
                settings += ["wifi-sec.psk", password]
            self.nm("connection", "modify", name, *settings)
            self.nm("radio", "wifi", "on")
            time.sleep(2)
            self.nm("connection", "up", name, "ifname", "wlan0")
            for profile in PROFILES.values():
                if self.exists(profile):
                    self.nm("connection", "modify", profile, "connection.autoconnect", "yes" if profile == name else "no",
                            "connection.autoconnect-priority", "100")
            self.message = "Hotspot ready" if mode == "ap" else "Connected to Wi-Fi"
        except Exception as exc:
            detail = str(exc)
            if password:
                detail = detail.replace(password, "[password]")
            self.message = "Wi-Fi change failed: " + detail
            if backup:
                try:
                    self.nm("connection", "modify", name, *backup)
                except Exception:
                    self.message += "; could not restore saved settings"
            if previous in PROFILES.values():
                try:
                    self.nm("connection", "up", previous)
                    self.message += "; previous connection restored"
                except Exception:
                    self.message += "; reconnect through Ethernet"
        finally:
            self.busy = False
