"""Docker multiplexed frames with deadlines including partial reads/writes."""

import struct
import os
import threading
import time

from py_docker.errors import DeadlineError, DockerOperationError, OutputLimitError
from py_docker.streams.models import Frame, StreamLimits


class AttachedStream:
    """Single reader and serialized writer. Closing detaches; it does not stop work.

    SDK 7.2 returns SocketIO on Unix and NpipeSocket on Windows. The small
    adapter uses recv_into because NpipeSocket.recv ignores its timeout.
    """

    def __init__(self, raw, limits: StreamLimits):
        self.raw = raw
        self.socket = getattr(raw, "_sock", raw)
        self.deadline = time.monotonic() + limits.seconds
        self.remaining_bytes = limits.max_bytes
        self._write_lock = threading.Lock()
        self._closed = False

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise DeadlineError("read/write container stream")
        return remaining

    def _read(self, size: int, *, allow_eof: bool = False) -> bytes:
        result = bytearray(size)
        offset = 0
        while offset < size:
            try:
                self.socket.settimeout(self._remaining())
                count = self.socket.recv_into(memoryview(result)[offset:], size - offset)
            except TimeoutError:
                raise DeadlineError("read container stream") from None
            except DockerOperationError:
                raise
            except Exception as error:
                # Docker closes a completed exec stream with ERROR_BROKEN_PIPE
                # on Windows. Only a frame-boundary close is a clean EOF.
                if os.name == "nt" and getattr(error, "winerror", None) == 109 and offset == 0 and allow_eof:
                    return b""
                raise DockerOperationError("read container stream") from None
            if not count:
                if offset == 0 and allow_eof:
                    return b""
                raise DockerOperationError("read complete container frame")
            offset += count
        return bytes(result)

    def read_frame(self) -> Frame | None:
        header = self._read(8, allow_eof=True)
        if not header:
            return None
        channel, size = struct.unpack(">BxxxI", header)
        if channel not in (1, 2) or header[1:4] != b"\0\0\0":
            raise DockerOperationError("decode container framing")
        if size > self.remaining_bytes:
            raise OutputLimitError("read container stream")
        self.remaining_bytes -= size
        return Frame(channel="stdout" if channel == 1 else "stderr", data=self._read(size))

    def write(self, data: bytes) -> None:
        # SDK NpipeSocket.sendall does not loop partial writes; do so explicitly.
        with self._write_lock:
            offset = 0
            while offset < len(data):
                try:
                    self.socket.settimeout(self._remaining())
                    count = self.socket.send(data[offset:])
                except TimeoutError:
                    raise DeadlineError("write container stream") from None
                except DockerOperationError:
                    raise
                except Exception:
                    raise DockerOperationError("write container stream") from None
                if not count:
                    raise DockerOperationError("write complete container request")
                offset += count

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self.raw.close()
            finally:
                response = getattr(self.raw, "_response", None)
                if response is not None:
                    response.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
