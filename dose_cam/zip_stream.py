"""Bounded-memory ZIP generation with backpressure and disconnect cancellation."""
import io
import queue
import threading
import zipfile


def stream_zip(write_entries):
    chunks = queue.Queue(maxsize=16)
    cancelled = threading.Event()
    done = object()

    def put(item):
        while not cancelled.is_set():
            try:
                chunks.put(item, timeout=0.2)
                return
            except queue.Full:
                pass
        raise InterruptedError("ZIP download disconnected")

    class Sink(io.RawIOBase):
        def writable(self):
            return True

        def write(self, data):
            for offset in range(0, len(data), 65536):
                put(bytes(data[offset:offset + 65536]))
            return len(data)

    def produce():
        try:
            with zipfile.ZipFile(Sink(), "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=1, allowZip64=True) as archive:
                write_entries(archive)
            put(done)
        except Exception as exc:
            if not cancelled.is_set():
                try:
                    put(exc)
                except InterruptedError:
                    pass

    worker = threading.Thread(target=produce, name="zip-download", daemon=True)
    worker.start()
    try:
        while True:
            item = chunks.get()
            if item is done:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        cancelled.set()
        worker.join(timeout=1)
