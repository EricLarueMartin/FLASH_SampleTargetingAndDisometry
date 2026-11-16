"""Offline validation and failed-activation recovery checks; no hardware changes."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dose_cam"))
from wifi_control import WifiControl


class FakeWifi(WifiControl):
    def __init__(self):
        super().__init__()
        self.calls = []

    def exists(self, name):
        return name == "dosecam-hotspot"

    def nm(self, *args):
        self.calls.append(args)
        if "GENERAL.CONNECTION" in args:
            return "dosecam-hotspot"
        if args[:3] == ("connection", "up", "dosecam-client"):
            raise RuntimeError("network unavailable")
        return ""


class WifiTests(unittest.TestCase):
    def test_invalid_requests_do_not_change_network(self):
        for data in ({"mode": "unknown"}, {"mode": "client", "ssid": "", "password": "12345678"},
                     {"mode": "ap", "ssid": "x", "password": "short"},
                     {"mode": "ap", "ssid": "x", "password": "12345678", "ip": "8.8.8.8"},
                     {"mode": "ap", "ssid": "x", "password": "12345678", "ip": "192.168.50.0"}):
            wifi = FakeWifi()
            with self.assertRaises(ValueError):
                wifi.start(data)
            self.assertFalse(wifi.busy)
            self.assertFalse(wifi.calls)

    @patch("wifi_control.time.sleep")
    def test_failed_join_restores_hotspot(self, _):
        wifi = FakeWifi()
        wifi.busy = True
        wifi.apply("client", "missing-network", "test-password", "")
        self.assertIn(("connection", "up", "dosecam-hotspot"), wifi.calls)
        self.assertIn("previous connection restored", wifi.message)
        self.assertFalse(wifi.busy)
        self.assertNotIn("test-password", wifi.message)

    @patch("wifi_control.time.sleep")
    def test_off_preserves_ethernet(self, _):
        wifi = FakeWifi()
        wifi.apply("off", "", "", "")
        self.assertIn(("radio", "wifi", "off"), wifi.calls)
        self.assertFalse(any("eth0" in call for call in wifi.calls))


if __name__ == "__main__":
    unittest.main()
