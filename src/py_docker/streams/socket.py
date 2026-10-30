"""Docker multiplexed frames with deadlines including partial reads/writes."""

import os
import struct
import threading
import time
from typing import Any

from py_docker.errors import DeadlineError, DockerOperationError
from py_docker.streams import settings
from py_docker.streams.models import Frame, StreamBudget, StreamLimits


class AttachedStream:
    """Single reader and serialized writer. Closing detaches; it does not stop work.

    SDK 7.2 returns SocketIO on Unix and NpipeSocket on Windows. The small
    adapter uses recv_into because NpipeSocket.recv ignores its timeout.

    Parameters
    ----------
    raw : Any
        SDK-specific acquired Unix SocketIO or Windows named-pipe handle; no ownership transfer beyond close.
    limits : StreamLimits
        Validated combined output-byte limit and acquired-stream lifetime.
    deadline : float or None
        Optional absolute monotonic cap, never extended by stream acquisition.
    """

    def __init__(
        self, raw: Any, limits: StreamLimits, *, deadline: float | None = None
    ) -> None:
        """Acquire the socket adapter and initialize its private stream budget."""
        self._raw = raw
        self._socket = getattr(raw, "_sock", raw)
        self._budget = StreamBudget.from_limits(
            limits, time.monotonic(), deadline=deadline
        )
        self._write_lock = threading.Lock()
        self._closed = False

    def __enter__(self) -> "AttachedStream":
        """Return the acquired stream for deterministic context cleanup.

        Returns
        -------
        AttachedStream
            The same owned context object.
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Detach while preserving any exception already raised in the context.

        Parameters
        ----------
        _ : tuple
            Context-manager exception information; cleanup must not replace a primary failure.

        Raises
        ------
        DockerOperationError
            Detachment failed and there is no primary context exception to preserve.
        """
        try:
            self.close()
        except DockerOperationError:
            if _[0] is None:
                raise

    def read_frame(self) -> Frame | None:
        """Read one validated Docker frame without decoding its payload.

        Returns
        -------
        Frame | None
            One binary output frame, or None for a clean frame-boundary EOF.

        Raises
        ------
        DeadlineError
            The original stream deadline expired while reading; remote work may still be active.
        OutputLimitError
            The declared payload exceeds the remaining combined output allowance.
        DockerOperationError
            Framing is invalid, the frame is truncated, or the transport read failed.
        """
        header = self._read(settings.HEADER_SIZE, allow_eof=True)
        if not header:
            return None
        channel, size = struct.unpack(settings.HEADER_FORMAT, header)
        if (
            channel not in (settings.STDOUT_CHANNEL, settings.STDERR_CHANNEL)
            or header[1:4] != b"\0\0\0"
        ):
            raise DockerOperationError("decode container framing")
        self._budget.consume(size)
        return Frame(
            channel="stdout" if channel == settings.STDOUT_CHANNEL else "stderr",
            data=self._read(size),
        )

    def write(self, data: bytes) -> None:
        """Write all request bytes using the original stream deadline.

        Parameters
        ----------
        data : bytes
            Undecoded request bytes written completely unless the stream fails or expires.

        Raises
        ------
        DeadlineError
            The original stream deadline expired before all bytes were written.
        DockerOperationError
            The transport write failed or stopped before all request bytes were sent.
        """
        # SDK NpipeSocket.sendall does not loop partial writes; do so explicitly.
        with self._write_lock:
            offset = 0
            while offset < len(data):
                try:
                    self._socket.settimeout(self.remaining_seconds())
                    count = self._socket.send(data[offset:])
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
        """Detach once, closing the response before its underlying socket.

        Raises
        ------
        DockerOperationError
            The response or underlying socket failed to close; this does not stop remote work.
        """
        if not self._closed:
            self._closed = True
            failures = []
            try:
                response = getattr(self._raw, "_response", None)
                if response is not None:
                    response.close()
            except Exception as error:
                failures.append(error)
            finally:
                try:
                    self._raw.close()
                except Exception as error:
                    failures.append(error)
            if failures:
                raise DockerOperationError("close container stream") from None

    def remaining_seconds(self) -> float:
        """Return positive remaining stream lifetime using the monotonic clock.

        Returns
        -------
        float
            Seconds left on the acquired stream's original deadline.

        Raises
        ------
        DeadlineError
            The stream has expired; remote execution may still be active.
        """
        return self._budget.remaining_seconds(time.monotonic())

    def _read(self, size: int, *, allow_eof: bool = False) -> bytes:
        """Read an exact byte count with bounded partial reads and EOF checks.

        Parameters
        ----------
        size : int
            Exact byte count decoded from validated framing; never an unbounded read.
        allow_eof : bool
            Whether a clean close before any byte is a valid frame-boundary EOF.

        Returns
        -------
        bytes
            Exactly the requested bytes, or empty bytes when allowed EOF occurs.

        Raises
        ------
        DeadlineError
            The original stream deadline expired before the requested bytes arrived.
        DockerOperationError
            The transport failed or closed before the required frame bytes arrived.
        """
        result = bytearray(size)
        offset = 0
        while offset < size:
            try:
                self._socket.settimeout(self.remaining_seconds())
                count = self._socket.recv_into(
                    memoryview(result)[offset:], size - offset
                )
            except TimeoutError:
                raise DeadlineError("read container stream") from None
            except DockerOperationError:
                raise
            except Exception as error:
                # Docker closes a completed exec stream with ERROR_BROKEN_PIPE
                # on Windows. Only a frame-boundary close is a clean EOF.
                if (
                    os.name == "nt"
                    and getattr(error, "winerror", None) == settings.WINDOWS_BROKEN_PIPE
                    and offset == 0
                    and allow_eof
                ):
                    return b""
                raise DockerOperationError("read container stream") from None
            if not count:
                if offset == 0 and allow_eof:
                    return b""
                raise DockerOperationError("read complete container frame")
            offset += count
        return bytes(result)
