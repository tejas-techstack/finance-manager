"""Offline enforcement.

Everything in this project is meant to run with the machine disconnected from
all networks. This module refuses to let the process continue if it can reach
the internet, both once at startup and continuously on a background thread.

Detection is heuristic: we try to open a TCP connection to a few well-known
public DNS resolvers on port 53. If ANY of them answers, we are online.
"""

import os
import socket
import sys
import threading
import time

# (host, port) pairs we probe. Port 53 = DNS; these resolvers are near-always up.
_PROBE_HOSTS = [
    ("1.1.1.1", 53),   # Cloudflare
    ("8.8.8.8", 53),   # Google
    ("9.9.9.9", 53),   # Quad9
]
_TIMEOUT = 1.0


def is_online() -> bool:
    """Return True if any probe host is reachable."""
    for host, port in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=_TIMEOUT):
                return True
        except OSError:
            continue
    return False


def _abort(reason: str, cleanup=None) -> None:
    sys.stderr.write(
        f"\n[guard] {reason} — ABORTING.\n"
        f"[guard] Disconnect from all networks (Wi-Fi + ethernet) and run again.\n\n"
    )
    sys.stderr.flush()
    if cleanup is not None:
        try:
            cleanup()
        except Exception:
            pass
    os._exit(2)


def assert_offline() -> None:
    """Abort immediately if we are online. Call this before doing anything."""
    if is_online():
        _abort("connectivity DETECTED at startup")


def arm(interval: float = 3.0, cleanup=None) -> None:
    """Start the background kill-switch.

    Every `interval` seconds we re-check connectivity; if the network comes
    back mid-run, we run `cleanup` (e.g. to stop child servers) and hard-exit.
    """

    def _loop():
        while True:
            time.sleep(interval)
            if is_online():
                _abort("connectivity DETECTED mid-run", cleanup)

    threading.Thread(target=_loop, daemon=True, name="offline-guard").start()
