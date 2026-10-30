"""An owned binary interactive session; detachment never proves termination."""

import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext

from py_docker.connection.deadline import RequestDeadlineScope
from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerState,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import CleanupUnconfirmedError, DockerOperationError
from py_docker.sessions import settings
from py_docker.sessions.models import SessionDeadline
from py_docker.streams.models import Frame, Line
from py_docker.streams.socket import AttachedStream


class Session:
    """Keep one creator-owned receipt and allow one reader plus serialized writes.

    Parameters
    ----------
    containers : Containers
        Existing scoped Docker operations; caller keeps its client open.
    store : ReceiptStore
        Already acquired lifecycle lock, released by close on the creator thread.
    reservation : ContainerReservation
        Canonical ownership intent persisted before creation.
    identity : ContainerIdentity
        Verified immutable ID durably recorded before attachment.
    stream : AttachedStream
        Acquired bounded non-TTY attachment, established before start.
    deadline : SessionDeadline or None
        Optional normal deadline and the one distinct cleanup reserve.
    """

    def __init__(
        self,
        containers: Containers,
        store: ReceiptStore,
        reservation: ContainerReservation,
        identity: ContainerIdentity,
        stream: AttachedStream,
        deadline: SessionDeadline | None = None,
    ) -> None:
        """Retain the open lifecycle without acquiring another Docker session."""
        self._containers = containers
        self._store = store
        self._reservation = reservation
        self.identity = identity
        self._stream = stream
        self._deadline = deadline
        self._creator = threading.get_ident()
        self._termination_lock = threading.Lock()
        self._closed = False
        self._cleanup_confirmed = False
        self._close_error: DockerOperationError | None = None
        self._read_mode = None
        self._eof = False
        self._line_buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self._lines = deque()

    def __enter__(self) -> "Session":
        """Return this open session for creator-thread deterministic cleanup."""
        return self

    def __exit__(self, *_: object) -> None:
        """Confirm exact cleanup even when application execution raises."""
        try:
            self.close()
        except CleanupUnconfirmedError as error:
            if isinstance(_[1], DockerOperationError):
                error.primary = _[1]
            raise

    @property
    def cleanup_confirmed(self) -> bool:
        """Whether creator-thread close confirmed removal, receipt and stream cleanup."""
        return self._cleanup_confirmed

    def read_frame(self) -> Frame | None:
        """Read one binary output frame; None means attachment EOF, not success.

        Returns
        -------
        Frame or None
            One stdout/stderr frame; errors retain existing safe stream codes.
        """
        self._select_reader("frames")
        frame = self._stream.read_frame()
        self._eof = frame is None
        return frame

    def read_line(self) -> Line | None:
        """Read a bounded binary line without decoding or mixing output channels.

        Returns
        -------
        Line or None
            Newline-preserving output, final partial bytes, or confirmed stream
            EOF. EOF does not establish process exit. Use one reader and choose
            either frame or line mode for the session, never both.

        Raises
        ------
        DockerOperationError
            Read modes were mixed or the underlying bounded stream failed.
        """
        self._select_reader("lines")
        while not self._lines and not self._eof:
            frame = self._stream.read_frame()
            if frame is None:
                self._eof = True
                for channel, pending in self._line_buffers.items():
                    if pending:
                        self._lines.append(Line(channel=channel, data=bytes(pending)))
                        pending.clear()
                break
            pending = self._line_buffers[frame.channel]
            pending.extend(frame.data)
            while b"\n" in pending:
                line, _, remaining = pending.partition(b"\n")
                self._line_buffers[frame.channel] = pending = bytearray(remaining)
                self._lines.append(Line(channel=frame.channel, data=line + b"\n"))
        return self._lines.popleft() if self._lines else None

    def exited(self) -> bool:
        """Confirm termination after EOF without equating removal with exit zero.

        Returns
        -------
        bool
            False before EOF or for a nonterminal created state; True for
            confirmed removal or a known exit code. Query state for that code.

        Raises
        ------
        DockerOperationError
            Output ended while the process still runs, or state is uncertain.
        """
        if not self._eof:
            return False
        state = self.state()
        if state.running:
            raise DockerOperationError("confirm container exit after output EOF")
        return state.removed or state.exit_code is not None

    def write(self, data: bytes) -> None:
        """Write complete binary stdin data within the acquired stream budget.

        Parameters
        ----------
        data : bytes
            Request bytes; no automatic encoding or newline insertion.
        """
        self._stream.write(data)

    def state(self) -> ContainerState:
        """Confirm exact process state without treating absence as exit success.

        Returns
        -------
        ContainerState
            Ownership-verified state of the observed immutable ID.
        """
        with self._scope():
            result = self._containers.state(self.identity)
            if self._deadline:
                self._deadline.normal.remaining_seconds(time.monotonic())
            return result

    def wait(self, timeout: float) -> int:
        """Confirm the process exit using a separate bounded wait request.

        Parameters
        ----------
        timeout : float
            Positive finite wait-request timeout in seconds.

        Returns
        -------
        int
            Confirmed exit code; removal alone cannot provide one.
        """
        with self._scope():
            result = self._containers.wait(self.identity, timeout=timeout)
            if self._deadline:
                self._deadline.normal.remaining_seconds(time.monotonic())
            return result

    def terminate(self) -> None:
        """Remove the exact owned ID from any thread without touching its receipt.

        Raises
        ------
        DockerOperationError
            Ownership, removal or absence cannot be confirmed.
        """
        with self._termination_lock:
            with self._scope(cleanup=True):
                self._containers.remove(self.identity, force=True)

    @contextmanager
    def stop_on(self, requested: Callable[[], bool] | None) -> Iterator[None]:
        """Monitor a caller's stop policy without moving receipt ownership.

        Parameters
        ----------
        requested : Callable[[], bool] or None
            Fast nonblocking predicate; None starts no thread. The caller owns
            cancellation/deadline policy and interprets its resulting run status.

        Yields
        ------
        None
            A scope whose monitor terminates only this session's owned ID.

        Raises
        ------
        DockerOperationError
            Monitor startup or predicate evaluation failed. An existing body
            failure is preserved. Creator-thread close remains authoritative
            for receipt/stream cleanup and overrides uncertain termination.
        """
        if threading.get_ident() != self._creator:
            raise DockerOperationError("monitor session on its creator thread")
        if requested is None:
            yield
            return
        stopped = threading.Event()
        failures = []

        def monitor():
            """Observe caller policy and stop only the already verified identity."""
            while not stopped.wait(settings.STOP_POLL_SECONDS):
                try:
                    if not requested():
                        continue
                except Exception:
                    failures.append(
                        DockerOperationError("evaluate container stop condition")
                    )
                try:
                    self.terminate()
                except DockerOperationError:
                    pass  # Creator close verifies cleanup and retains uncertain intent.
                return

        watcher = threading.Thread(target=monitor, daemon=True)
        try:
            watcher.start()
        except Exception:
            raise DockerOperationError("start container stop monitor") from None
        try:
            yield
        finally:
            stopped.set()
            watcher.join()
        if failures:
            raise failures[0]

    def close(self) -> None:
        """Confirm removal and clear the receipt on the lifecycle creator thread.

        Raises
        ------
        CleanupUnconfirmedError
            Cleanup uncertainty retains durable intent and takes precedence.
        DockerOperationError
            Called from another thread or attachment detachment failed.
        """
        if threading.get_ident() != self._creator:
            raise DockerOperationError("close session on its creator thread")
        if self._closed:
            if self._close_error is not None:
                raise self._close_error
            return
        error = None
        try:
            with self._termination_lock:
                with self._scope(cleanup=True):
                    self._store.cleanup(
                        self._containers, self._reservation, self.identity
                    )
        except Exception as failure:
            error = (
                failure
                if isinstance(failure, CleanupUnconfirmedError)
                else CleanupUnconfirmedError(
                    "bind or complete session cleanup", self._reservation
                )
            )
            if isinstance(failure, DockerOperationError) and failure is not error:
                error.primary = failure
        finally:
            try:
                self._stream.close()
            except Exception as failure:
                error = error or (
                    failure
                    if isinstance(failure, DockerOperationError)
                    else DockerOperationError("close session stream")
                )
            try:
                self._store.__exit__(type(error) if error else None, error, None)
            except Exception as failure:
                error = error or (
                    failure
                    if isinstance(failure, DockerOperationError)
                    else DockerOperationError("release session receipt")
                )
            self._closed = True
            self._cleanup_confirmed = error is None
            self._close_error = error
        if error is not None:
            raise error

    def _scope(self, *, cleanup: bool = False):
        """Bind normal admission or the one cleanup reserve on this caller thread."""
        if self._deadline is None:
            return nullcontext()
        budget = (
            self._deadline.cleanup_budget(time.monotonic())
            if cleanup
            else self._deadline.normal
        )
        return RequestDeadlineScope(self._containers.sdk.api, budget)

    def _select_reader(self, mode: str) -> None:
        """Keep buffering canonical by refusing a change of read mode."""
        if self._read_mode not in (None, mode):
            raise DockerOperationError("mix container frame and line readers")
        self._read_mode = mode
