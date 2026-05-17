"""
LAN scanner for discovering Nintendo Switch consoles running sys-botbase.

Scans a given subnet by probing TCP port 6000 in parallel using threads.
"""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from src.protocol import SYSBOT_PORT


def get_local_ip() -> Optional[str]:
    """Detect the local machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def derive_subnet(ip: str) -> str:
    """Return the /24 prefix from an IP, e.g. '192.168.1'."""
    parts = ip.rsplit(".", 1)
    return parts[0]


def probe_host(ip: str, port: int = SYSBOT_PORT, timeout: float = 0.5) -> Optional[str]:
    """Try to TCP-connect to ip:port. Returns the ip on success, None otherwise."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return ip
    except (socket.timeout, OSError):
        return None


def scan_subnet(
    subnet: str,
    port: int = SYSBOT_PORT,
    timeout: float = 0.5,
    max_workers: int = 64,
    on_progress: Optional[Callable[[int, int], None]] = None,
    on_found: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> list[str]:
    """
    Scan subnet.1 – subnet.254 for open TCP port.

    Parameters
    ----------
    subnet : str
        The first three octets, e.g. "192.168.1".
    on_progress : callable(scanned, total)
        Progress callback.
    on_found : callable(ip)
        Called immediately when a host is found.
    cancel_event : threading.Event
        Set to cancel the scan early.

    Returns
    -------
    list of IPs that responded.
    """
    found: list[str] = []
    total = 254
    scanned = 0

    def _probe(host_num: int) -> Optional[str]:
        if cancel_event and cancel_event.is_set():
            return None
        ip = f"{subnet}.{host_num}"
        return probe_host(ip, port, timeout)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_probe, i): i for i in range(1, 255)}
        for future in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                break
            scanned += 1
            result = future.result()
            if result:
                found.append(result)
                if on_found:
                    on_found(result)
            if on_progress:
                on_progress(scanned, total)

    return found
