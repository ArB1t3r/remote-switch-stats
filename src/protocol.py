"""
sys-botbase TCP protocol client.

Wraps the raw TCP socket communication with the sys-botbase sysmodule
running on a Nintendo Switch (CFW). The module listens on port 6000
and accepts ASCII text commands terminated by \\r\\n.
"""

import socket
import threading
import time
from typing import Optional, Callable


SYSBOT_PORT = 6000
SOCKET_TIMEOUT = 5.0
RECV_BUFFER = 1048576  # 1 MB — large enough for pixelPeek JPG payloads

BUTTONS = [
    "A", "B", "X", "Y",
    "L", "R", "ZL", "ZR",
    "LSTICK", "RSTICK",
    "PLUS", "MINUS",
    "DUP", "DDOWN", "DLEFT", "DRIGHT",
    "HOME", "CAPTURE",
]

STICK_MIN = -0x8000
STICK_MAX = 0x7FFF

CONFIGURE_KEYS = [
    "mainLoopSleepTime",
    "buttonClickSleepTime",
    "echoCommands",
    "printDebugResultCodes",
    "keySleepTime",
    "fingerDiameter",
    "pollRate",
    "freezeRate",
    "controllerType",
]


class SwitchConnection:
    """Persistent TCP connection to a sys-botbase instance."""

    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_DELAY = 1.5  # seconds between retries

    def __init__(self) -> None:
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._ip: Optional[str] = None
        self._port: int = SYSBOT_PORT
        self._connected = False
        self._on_status_change: Optional[Callable[[bool], None]] = None
        self._auto_reconnect = True
        self._reconnecting = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def ip(self) -> Optional[str]:
        return self._ip

    @property
    def auto_reconnect(self) -> bool:
        return self._auto_reconnect

    @auto_reconnect.setter
    def auto_reconnect(self, value: bool) -> None:
        self._auto_reconnect = value

    def set_status_callback(self, cb: Callable[[bool], None]) -> None:
        self._on_status_change = cb

    def _notify(self, status: bool) -> None:
        self._connected = status
        if self._on_status_change:
            self._on_status_change(status)

    # ── Connection lifecycle ────────────────────────────────────────

    def connect(self, ip: str, port: int = SYSBOT_PORT, timeout: float = SOCKET_TIMEOUT) -> str:
        """Connect to the Switch. Returns status message."""
        self.disconnect()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, port))
            self._sock = s
            self._ip = ip
            self._port = port
            self._notify(True)
            return f"已连接到 {ip}:{port}"
        except socket.timeout:
            return f"连接超时: {ip}:{port}"
        except OSError as e:
            return f"连接失败: {e}"

    def disconnect(self) -> None:
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            self._notify(False)

    def reconnect(self) -> str:
        if self._ip is None:
            return "没有可用的 IP 地址"
        return self.connect(self._ip, self._port)

    def _try_reconnect(self) -> bool:
        """Attempt to re-establish the connection. Must be called WITHOUT holding _lock."""
        if not self._auto_reconnect or not self._ip:
            return False
        if self._reconnecting:
            return False

        self._reconnecting = True
        try:
            for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
                time.sleep(self.RECONNECT_DELAY)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(SOCKET_TIMEOUT)
                    s.connect((self._ip, self._port))
                    with self._lock:
                        if self._sock:
                            try:
                                self._sock.close()
                            except OSError:
                                pass
                        self._sock = s
                    self._notify(True)
                    return True
                except (socket.timeout, OSError):
                    continue
            return False
        finally:
            self._reconnecting = False

    # ── Low-level send / receive ────────────────────────────────────

    def send_command(self, cmd: str, wait_response: bool = True) -> str:
        """Send an ASCII command, return the response line (stripped)."""
        with self._lock:
            if not self._sock:
                return "[未连接]"
            try:
                payload = (cmd.strip() + "\r\n").encode("ascii")
                self._sock.sendall(payload)
                if not wait_response:
                    return ""
                return self._recv_line()
            except (socket.timeout, OSError) as e:
                self._notify(False)
                # Release the lock before reconnecting
                pass

        # Auto-reconnect outside the lock
        if self._auto_reconnect and self._ip:
            if self._try_reconnect():
                return self.send_command(cmd, wait_response)
        return "[通信错误] 连接已断开，重连失败"

    def send_command_raw(self, cmd: str) -> bytes:
        """Send command and return raw bytes (for pixelPeek)."""
        with self._lock:
            if not self._sock:
                return b""
            try:
                self._sock.sendall((cmd.strip() + "\r\n").encode("ascii"))
                return self._recv_raw()
            except (socket.timeout, OSError):
                self._notify(False)
                pass

        # Auto-reconnect outside the lock
        if self._auto_reconnect and self._ip:
            if self._try_reconnect():
                return self.send_command_raw(cmd)
        return b""

    def _recv_line(self) -> str:
        buf = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break
        return buf.strip().decode("utf-8", errors="replace")

    def _recv_raw(self) -> bytes:
        """Receive until the socket goes quiet (for binary-ish payloads)."""
        self._sock.settimeout(2.0)
        chunks: list[bytes] = []
        try:
            while True:
                chunk = self._sock.recv(RECV_BUFFER)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
        finally:
            self._sock.settimeout(SOCKET_TIMEOUT)
        return b"".join(chunks)

    # ── Controller commands ─────────────────────────────────────────

    def click(self, button: str) -> str:
        return self.send_command(f"click {button}")

    def press(self, button: str) -> str:
        return self.send_command(f"press {button}")

    def release(self, button: str) -> str:
        return self.send_command(f"release {button}")

    def set_stick(self, stick: str, x: int, y: int) -> str:
        x = max(STICK_MIN, min(STICK_MAX, x))
        y = max(STICK_MIN, min(STICK_MAX, y))
        return self.send_command(f"setStick {stick} {x} {y}")

    def detach_controller(self) -> str:
        return self.send_command("detachController")

    # ── Touch commands ──────────────────────────────────────────────

    def touch(self, x: int, y: int) -> str:
        return self.send_command(f"touch {x} {y}")

    def touch_hold(self, x: int, y: int, ms: int) -> str:
        return self.send_command(f"touchHold {x} {y} {ms}")

    def touch_draw(self, points: list[tuple[int, int]]) -> str:
        flat = " ".join(f"{x} {y}" for x, y in points)
        return self.send_command(f"touchDraw {flat}")

    def touch_cancel(self) -> str:
        return self.send_command("touchCancel")

    # ── Click sequence ──────────────────────────────────────────────

    def click_seq(self, sequence: str) -> str:
        return self.send_command(f"clickSeq {sequence}")

    def click_cancel(self) -> str:
        return self.send_command("clickCancel")

    # ── Memory commands ─────────────────────────────────────────────

    def peek(self, address: str, size: int) -> str:
        return self.send_command(f"peek {address} {size}")

    def peek_absolute(self, address: str, size: int) -> str:
        return self.send_command(f"peekAbsolute {address} {size}")

    def peek_main(self, address: str, size: int) -> str:
        return self.send_command(f"peekMain {address} {size}")

    def poke(self, address: str, data: str) -> str:
        return self.send_command(f"poke {address} {data}")

    def poke_absolute(self, address: str, data: str) -> str:
        return self.send_command(f"pokeAbsolute {address} {data}")

    def poke_main(self, address: str, data: str) -> str:
        return self.send_command(f"pokeMain {address} {data}")

    def pointer_peek(self, size: int, jumps: list[str]) -> str:
        j = " ".join(jumps)
        return self.send_command(f"pointerPeek {size} {j}")

    def pointer_poke(self, data: str, jumps: list[str]) -> str:
        j = " ".join(jumps)
        return self.send_command(f"pointerPoke {data} {j}")

    # ── Freeze commands ─────────────────────────────────────────────

    def freeze(self, address: str, value: str) -> str:
        return self.send_command(f"freeze {address} {value}")

    def unfreeze(self, address: str) -> str:
        return self.send_command(f"unFreeze {address}")

    def freeze_count(self) -> str:
        return self.send_command("freezeCount")

    def freeze_clear(self) -> str:
        return self.send_command("freezeClear")

    def freeze_pause(self) -> str:
        return self.send_command("freezePause")

    def freeze_unpause(self) -> str:
        return self.send_command("freezeUnpause")

    # ── Screen commands ─────────────────────────────────────────────

    def pixel_peek(self) -> bytes:
        """Capture screen, returns raw JPG bytes (hex-encoded from the Switch)."""
        return self.send_command_raw("pixelPeek")

    def screen_off(self) -> str:
        return self.send_command("screenOff")

    def screen_on(self) -> str:
        return self.send_command("screenOn")

    # ── Utility commands ────────────────────────────────────────────

    def get_title_id(self) -> str:
        return self.send_command("getTitleID")

    def get_title_version(self) -> str:
        return self.send_command("getTitleVersion")

    def get_system_language(self) -> str:
        return self.send_command("getSystemLanguage")

    def get_build_id(self) -> str:
        return self.send_command("getBuildID")

    def get_heap_base(self) -> str:
        return self.send_command("getHeapBase")

    def get_main_nso_base(self) -> str:
        return self.send_command("getMainNsoBase")

    def is_program_running(self, program_id: str) -> str:
        return self.send_command(f"isProgramRunning {program_id}")

    def game_info(self, field: str) -> str:
        return self.send_command(f"game {field}")

    def get_version(self) -> str:
        return self.send_command("getVersion")

    def get_charge(self) -> str:
        return self.send_command("charge")

    # ── Configure commands ──────────────────────────────────────────

    def configure(self, key: str, value: str) -> str:
        return self.send_command(f"configure {key} {value}")
