"""Run a disposable owned container once, preserving uncertain cleanup intent."""

import threading
from pathlib import Path

from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import (
    DockerOperationError,
    JobCancelledError,
)
from py_docker.execution.models import CommandResult
from py_docker.execution.service import Execution
from py_docker.jobs.models import ContainerJob
from py_docker.sessions.models import ContainerSession
from py_docker.sessions.service import Sessions


class Jobs:
    """One-shot container creation, unlike Execution.run in an existing container.

    Parameters
    ----------
    containers : Containers
        Container operations sharing the caller's owned Docker client.
    execution : Execution
        Bounded binary attachment on the same client and selected daemon.
    """

    def __init__(self, containers: Containers, execution: Execution) -> None:
        """Reuse existing scoped services without owning another SDK session."""
        self._containers = containers
        self._execution = execution

    def recover(self, receipt_path: Path) -> None:
        """Reconcile a prior job before application policy checks or another dispatch.

        Parameters
        ----------
        receipt_path : Path
            Existing caller-owned private local receipt location.

        Raises
        ------
        CleanupUnconfirmedError
            A pending record cannot be safely cleared.
        ReceiptInUseError
            Another live caller owns the record; no recovery was attempted.
        DockerOperationError
            Local receipt locking is unavailable or unsafe.
        """
        with ReceiptStore(receipt_path) as store:
            store.recover(self._containers)

    def run(
        self,
        job: ContainerJob,
        *,
        cancelled: threading.Event | None = None,
        deadline: float | None = None,
        cleanup_seconds: float | None = None,
    ) -> CommandResult:
        """Collect one job, stopping its exact owned container on cancellation.

        Parameters
        ----------
        job : ContainerJob
            Immutable launch, stream/wait bounds and private durable receipt.
        cancelled : threading.Event or None
            Optional caller-owned stop signal. A pre-set event sends no launch.
        deadline : float or None
            Optional absolute monotonic deadline forwarded to the shared session.
        cleanup_seconds : float or None
            Separate cleanup reserve required with deadline; cancellation is checked first.

        Returns
        -------
        CommandResult
            Confirmed process exit and separate binary output after exact cleanup.

        Raises
        ------
        JobCancelledError
            Stop was requested and cleanup was confirmed. Earlier effects remain.
        CleanupUnconfirmedError
            Exact cleanup is uncertain; its receipt remains and takes precedence.
        DockerOperationError
            Launch, output or exit cannot be confirmed; no automatic retry.

        Notes
        -----
        Jobs and interactive services share the same session journal and lifecycle.
        The cancellation watcher uses thread-safe exact-ID termination; creator-
        thread close owns the receipt and final cleanup. Joining the watcher obeys
        the client's existing per-request timeouts, not a total wall-clock limit.
        """
        if cancelled is not None and cancelled.is_set():
            raise JobCancelledError("cancel container job before dispatch")
        request = ContainerSession(
            spec=job.spec, limits=job.limits, receipt_path=job.receipt_path
        )
        with (
            Sessions(self._containers, self._execution).open(
                request, deadline=deadline, cleanup_seconds=cleanup_seconds
            ) as session,
            session.stop_on(cancelled.is_set if cancelled is not None else None),
        ):
            try:
                stdout, stderr = bytearray(), bytearray()
                while (frame := session.read_frame()) is not None:
                    (stdout if frame.channel == "stdout" else stderr).extend(frame.data)
                if cancelled is not None and cancelled.is_set():
                    raise JobCancelledError("cancel container job")
                status = session.wait(timeout=job.wait_timeout_seconds)
                if cancelled is not None and cancelled.is_set():
                    raise JobCancelledError("cancel container job")
                return CommandResult(
                    exit_code=status, stdout=bytes(stdout), stderr=bytes(stderr)
                )
            except DockerOperationError:
                if cancelled is not None and cancelled.is_set():
                    raise JobCancelledError("cancel container job") from None
                raise
            except Exception:
                raise DockerOperationError("run one-shot container") from None
