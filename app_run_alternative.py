#!/usr/bin/env python3

"""
Alternative app runner with a simple restart loop for the queue worker.

This corresponds to the \"Option 1\" approach:
- Start gunicorn once to serve the Flask app.
- Run queue_worker.py in a loop with basic restart/backoff.

It is not wired into the Dockerfile by default; the container
currently uses supervisord instead (see supervisord.conf).
Switch the Docker CMD to use this script if you prefer this style.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

_processes: list[subprocess.Popen] = []
_stop = False


def _log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"{ts} {msg}", flush=True)


def start_gunicorn() -> subprocess.Popen:
    port = os.environ.get("PORT", "8080")
    cmd = [
        "gunicorn",
        "--bind",
        f"0.0.0.0:{port}",
        "app:app",
        "--workers",
        "1",
        "--max-requests",
        "1000",
        "--max-requests-jitter",
        "20",
        "--timeout",
        "300",
        "--graceful-timeout",
        "60",
        "--keep-alive",
        "10",
        "--preload",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "--log-level",
        "info",
    ]
    _log("[web] starting gunicorn")
    proc = subprocess.Popen(cmd)
    _processes.append(proc)
    return proc


def worker_loop() -> None:
    global _stop
    while not _stop:
        _log("[worker] starting queue_worker.py")
        proc = subprocess.Popen(["python3", "queue_worker.py"])
        _processes.append(proc)
        rc = proc.wait()
        _processes.remove(proc)
        if _stop:
            _log(f"[worker] exiting with code {rc}")
            break
        _log(f"[worker] exited with code {rc}, restarting in 5s")
        time.sleep(5)


def _handle_signal(signum, frame) -> None:  # type: ignore[override]
    global _stop
    _stop = True
    _log(f"[runner] received signal {signum}, terminating children")
    for proc in list(_processes):
        try:
            proc.terminate()
        except Exception:
            pass
    # Give children a moment to exit gracefully
    time.sleep(2)
    for proc in list(_processes):
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
    sys.exit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    gunicorn_proc = start_gunicorn()

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()

    rc = gunicorn_proc.wait()
    _log(f"[web] gunicorn exited with code {rc}, shutting down")
    _handle_signal(signal.SIGTERM, None)  # type: ignore[arg-type]
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

