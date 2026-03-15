import time
import threading
import signal
import sys
from datetime import datetime
from pathlib import Path

from app.config import settings


class FileCleanupScheduler:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._interval = settings.cleanup_interval_hours * 3600
        self._retention = settings.file_retention_hours * 3600

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._cleanup()
            except Exception:
                pass
            self._stop_event.wait(timeout=self._interval)

    def _cleanup(self):
        now = datetime.utcnow()
        cleaned = 0

        for directory in [settings.upload_path, settings.output_path]:
            if not directory.exists():
                continue
            for file_path in directory.iterdir():
                if not file_path.is_file():
                    continue
                try:
                    mtime = datetime.utcfromtimestamp(file_path.stat().st_mtime)
                    age_seconds = (now - mtime).total_seconds()
                    if age_seconds > self._retention:
                        file_path.unlink(missing_ok=True)
                        cleaned += 1
                except (OSError, PermissionError):
                    continue

        return cleaned

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


cleanup_scheduler = FileCleanupScheduler()


def run_standalone_scheduler():
    scheduler = FileCleanupScheduler()
    stop_event = threading.Event()

    def signal_handler(signum, frame):
        scheduler.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    scheduler.start()

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1)
    except KeyboardInterrupt:
        scheduler.stop()
        sys.exit(0)


if __name__ == "__main__":
    run_standalone_scheduler()
