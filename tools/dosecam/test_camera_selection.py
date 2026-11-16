from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dose_cam"))
# camera_core imports gpiozero at module level; it is not needed for these tests.
sys.modules.setdefault("gpiozero", types.SimpleNamespace(LED=object))
import camera_core
from camera_core import parse_camera_list, select_camera_args

SINGLE = """Available cameras
-----------------
0 : imx296 [1456x1088 10-bit MONO] (/base/axi/pcie@1000120000/rp1/i2c@88000/imx296@1a)
    Modes: 'R10' : 1456x1088 [60.38 fps - (0, 0)/1456x1088 crop]
"""

BOTH = """Available cameras
-----------------
0 : ov5647 [2592x1944 10-bit GBRG] (/base/axi/pcie@1000120000/rp1/i2c@80000/ov5647@36)
    Modes: 'SGBRG10_CSI2P' : 640x480 [58.92 fps - (16, 0)/2560x1920 crop]
                             1296x972 [43.25 fps - (0, 0)/2592x1944 crop]
                             1920x1080 [30.62 fps - (348, 434)/1928x1080 crop]
                             2592x1944 [15.63 fps - (0, 0)/2592x1944 crop]
1 : imx296 [1456x1088 10-bit MONO] (/base/axi/pcie@1000120000/rp1/i2c@88000/imx296@1a)
    Modes: 'R10' : 1456x1088 [60.38 fps - (0, 0)/1456x1088 crop]
"""

ONLY_FLASH = """Available cameras
-----------------
0 : ov5647 [2592x1944 10-bit GBRG] (/base/axi/pcie@1000120000/rp1/i2c@80000/ov5647@36)
    Modes: 'SGBRG10_CSI2P' : 640x480 [58.92 fps - (16, 0)/2560x1920 crop]
"""


class CameraSelectionTests(unittest.TestCase):
    def test_parse_ignores_mode_lines(self):
        self.assertEqual(parse_camera_list(BOTH), [(0, "ov5647"), (1, "imx296")])

    def test_single_imx296_needs_no_argument(self):
        # A single-camera DoseCam Pi runs exactly as before.
        self.assertEqual(select_camera_args(parse_camera_list(SINGLE)), [])

    def test_shared_pi_selects_imx296_by_model(self):
        self.assertEqual(select_camera_args(parse_camera_list(BOTH)), ["--camera", "1"])

    def test_missing_imx296_never_falls_back_to_flash_camera(self):
        with self.assertRaisesRegex(RuntimeError, "imx296 not detected .*ov5647"):
            select_camera_args(parse_camera_list(ONLY_FLASH))

    def test_no_cameras(self):
        with self.assertRaisesRegex(RuntimeError, "not detected"):
            select_camera_args(parse_camera_list("No cameras available!"))

    def test_index_override_skips_listing(self):
        core = camera_core.CameraCore.__new__(camera_core.CameraCore)
        core._camera_args_cache = None
        with patch.object(camera_core, "DOSECAM_CAMERA_INDEX", "1"), \
                patch.object(camera_core.subprocess, "run") as run:
            self.assertEqual(core._camera_args(), ["--camera", "1"])
            run.assert_not_called()

    def test_listing_is_cached(self):
        core = camera_core.CameraCore.__new__(camera_core.CameraCore)
        core._camera_args_cache = None
        result = types.SimpleNamespace(stdout=BOTH, stderr="")
        with patch.object(camera_core, "DOSECAM_CAMERA_INDEX", ""), \
                patch.object(camera_core.subprocess, "run", return_value=result) as run:
            self.assertEqual(core._camera_args(), ["--camera", "1"])
            self.assertEqual(core._camera_args(), ["--camera", "1"])
            run.assert_called_once()

    def test_picamera2_index_by_model(self):
        class FakePicamera2:
            @staticmethod
            def global_camera_info():
                return [{"Model": "ov5647"}, {"Model": "imx296"}]
        self.assertEqual(camera_core.CameraCore._picamera2_index(FakePicamera2), 1)


if __name__ == "__main__":
    unittest.main()
