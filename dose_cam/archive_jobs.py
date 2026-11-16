"""Disk-backed ZIP preparation, with byte progress and one worker at a time."""
import os
from pathlib import Path
import shutil
import threading
import time
import uuid
import zipfile


class ArchiveJobs:
    def __init__(self, directory="/var/tmp/dosecam-exports"):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.jobs = {}

    def start(self, paths, name, root, png_writer=None):
        with self.lock:
            if any(j["state"] == "compressing" for j in self.jobs.values()):
                raise ValueError("Another archive is being prepared. Wait or cancel it first.")
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Only our UUID-named temporary archives, retained for 24 hours.
            for path in self.directory.iterdir():
                if len(path.stem) == 32 and all(c in "0123456789abcdef" for c in path.stem) and path.suffix in (".zip", ".partial"):
                    if time.time() - path.stat().st_mtime > 86400:
                        path.unlink()
            items = [(p, os.path.getsize(p)) for p in paths]
            total = sum(size for _, size in items)
            if shutil.disk_usage(self.directory).free < total * 1.02 + 256 * 1024**2:
                raise ValueError("Not enough temporary disk space to prepare this archive")
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = dict(id=job_id, state="compressing", name=name, processed=0,
                total=total, file="", files_done=0, files_total=len(items), started=time.time(),
                size=0, error="", cancel=False)
            threading.Thread(target=self._build, args=(job_id, items, root, png_writer), daemon=True).start()
            return job_id

    def status(self, job_id):
        with self.lock:
            job = dict(self.jobs[job_id])
        job.pop("cancel")
        job["percent"] = min(100, round(100 * job["processed"] / max(1, job["total"]), 1))
        job["elapsed_s"] = round(job.get("finished", time.time()) - job["started"], 1)
        return job

    def cancel(self, job_id):
        with self.lock:
            self.jobs[job_id]["cancel"] = True

    def _progress(self, job_id, count):
        with self.lock:
            job = self.jobs[job_id]
            if job["cancel"]:
                raise InterruptedError("Compression cancelled")
            job["processed"] += count

    def _build(self, job_id, items, root, png_writer):
        partial = self.directory / (job_id + ".partial")
        try:
            with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6, allowZip64=True) as archive:
                for path, size in items:
                    self._progress(job_id, 0)
                    with self.lock:
                        self.jobs[job_id]["file"] = os.path.relpath(path, root).replace("\\", "/")
                    if png_writer:
                        png_writer(archive, path, lambda count: self._progress(job_id, count))
                    else:
                        info = zipfile.ZipInfo.from_file(path, os.path.relpath(path, root))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info._compresslevel = 6
                        with open(path, "rb") as source, archive.open(info, "w", force_zip64=True) as target:
                            remaining = size
                            while remaining:
                                chunk = source.read(min(1024**2, remaining))
                                if not chunk:
                                    raise IOError("Source file changed during compression")
                                target.write(chunk)
                                remaining -= len(chunk)
                                self._progress(job_id, len(chunk))
                    with self.lock:
                        self.jobs[job_id]["files_done"] += 1
            self._progress(job_id, 0)
            final = self.directory / (job_id + ".zip")
            partial.replace(final)
            with self.lock:
                self.jobs[job_id].update(state="ready", size=final.stat().st_size,
                    processed=self.jobs[job_id]["total"], finished=time.time())
        except Exception as exc:
            partial.unlink(missing_ok=True)
            with self.lock:
                self.jobs[job_id].update(state="cancelled" if isinstance(exc, InterruptedError) else "error",
                                         error=str(exc), finished=time.time())

    def download_path(self, job_id):
        if self.status(job_id)["state"] != "ready":
            raise ValueError("Archive is not ready")
        return self.directory / (job_id + ".zip")
