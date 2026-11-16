import io
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dose_cam"))
from zip_stream import stream_zip


class ZipStreamTests(unittest.TestCase):
    def test_zip64_round_trip(self):
        content = os.urandom(200000)
        def write(zf):
            zf.writestr("nested/run.raw", content)
            zf.writestr("nested/run.json", '{"delay_us":200}')
        with patch.object(zipfile, "ZIP64_LIMIT", 1000):
            downloaded = b"".join(stream_zip(write))
        with zipfile.ZipFile(io.BytesIO(downloaded)) as zf:
            self.assertIsNone(zf.testzip())
            self.assertEqual(zf.read("nested/run.raw"), content)
            self.assertEqual(len(zf.namelist()), 2)

    def test_disconnect_cancels_producer(self):
        finished = threading.Event()
        def write(zf):
            try:
                with zf.open("large.raw", "w", force_zip64=True) as out:
                    while True:
                        out.write(os.urandom(65536))
            finally:
                finished.set()
        download = stream_zip(write)
        self.assertTrue(next(download).startswith(b"PK"))
        download.close()
        self.assertTrue(finished.wait(2))

    def test_generation_error_is_not_silently_successful(self):
        def write(zf):
            raise OSError("read failed")
        with self.assertRaisesRegex(OSError, "read failed"):
            b"".join(stream_zip(write))


if __name__ == "__main__":
    unittest.main()
