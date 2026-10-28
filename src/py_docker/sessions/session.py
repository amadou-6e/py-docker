"""An owned binary interactive session; detachment never proves termination."""

import threading

from py_docker.containers.models import (
    ContainerIdentity,
    ContainerReservation,
    ContainerState,
)
from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import CleanupUnconfirmedError, DockerOperationError
from py_docker.streams.models import Frame
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
    """

    def __init__(
        self,
        containers: Containers,
        store: ReceiptStore,
        reservation: ContainerReservation,
        identity: ContainerIdentity,
        stream: AttachedStream,
    ) -> None:
        """Retain the open lifecycle without acquiring another Docker session."""
        self._containers = containers
        self._store = store
        self._reservation = reservation
        self.identity = identity
        self._stream = stream
        self._creator = threading.get_ident()
        self._termination_lock = threading.Lock()
        self._closed = False

    def __enter__(self) -> "Session":
        """Return this open session for creator-thread deterministic cleanup."""
        return self

    def __exit__(self, *_: object) -> None:
        """Confirm exact cleanup even when application execution raises."""
        self.close()

    def read_frame(self) -> Frame | None:
        """Read one binary output frame; None means attachment EOF, not success.

        Returns
        -------
        Frame or None
            One stdout/stderr frame; errors retain existing safe stream codes.
        """
        return self._stream.read_frame()

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
        return self._containers.state(self.identity)

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
        return self._containers.wait(self.identity, timeout=timeout)

    def terminate(self) -> None:
        """Remove the exact owned ID from any thread without touching its receipt.

        Raises
        ------
        DockerOperationError
            Ownership, removal or absence cannot be confirmed.
        """
        with self._termination_lock:
            self._containers.remove(self.identity, force=True)

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
            return
        error = None
        try:
            with self._termination_lock:
                self._store.cleanup(self._containers, self._reservation, self.identity)
        except CleanupUnconfirmedError as failure:
            error = failure
        finally:
            try:
                self._stream.close()
            except DockerOperationError as failure:
                error = error or failure
            try:
                self._store.__exit__(type(error) if error else None, error, None)
            except DockerOperationError as failure:
                error = error or failure
            self._closed = True
        if error is not None:
            raise error
