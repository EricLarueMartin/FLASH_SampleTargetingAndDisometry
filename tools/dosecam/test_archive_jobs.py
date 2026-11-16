import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dose_cam'))
from archive_jobs import ArchiveJobs


class ArchiveTests(unittest.TestCase):
    def wait(self, jobs, job):
        deadline = time.monotonic() + 10
        while jobs.status(job)['state'] == 'compressing':
            if time.monotonic() > deadline:
                self.fail('worker timed out')
            time.sleep(.01)
        return jobs.status(job)

    def test_integrity_and_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'sample.raw'
            content = b'1234567890' * 200000
            source.write_bytes(content)
            jobs = ArchiveJobs(root / 'exports')
            job = jobs.start([str(source)], 'test.zip', tmp)
            state = self.wait(jobs, job)
            self.assertEqual(state['state'], 'ready')
            self.assertEqual(state['processed'], len(content))
            self.assertEqual(state['percent'], 100)
            with zipfile.ZipFile(jobs.download_path(job)) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read('sample.raw'), content)

    def test_cancel_cleans_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'sample.raw'
            source.write_bytes(os.urandom(4 * 1024**2))
            jobs = ArchiveJobs(Path(tmp) / 'exports')
            job = jobs.start([str(source)], 'test.zip', tmp)
            jobs.cancel(job)
            self.assertEqual(self.wait(jobs, job)['state'], 'cancelled')
            self.assertFalse(list(jobs.directory.glob('*.partial')))


if __name__ == '__main__':
    unittest.main()
