"""Run a disposable owned container once, preserving uncertain cleanup intent."""

from pathlib import Path

from py_docker.containers.receipts import ReceiptStore
from py_docker.containers.service import Containers
from py_docker.errors import CleanupUnconfirmedError, DockerOperationError
from py_docker.execution.models import CommandResult
from py_docker.execution.service import Execution
from py_docker.jobs.models import ContainerJob


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
            A pending record cannot be safely cleared, including a live lock owner.
        DockerOperationError
            Local receipt locking is unavailable or unsafe.
        """
        with ReceiptStore(receipt_path) as store:
            store.recover(self._containers)

    def run(self, job: ContainerJob) -> CommandResult:
        """Create, attach, start, collect and remove one immutable-image container.

        Parameters
        ----------
        job : ContainerJob
            Validated launch, stream/wait limits and private receipt location.

        Returns
        -------
        CommandResult
            Confirmed exit code and separate binary output after exact cleanup.
            A nonzero process exit is returned, not raised.

        Raises
        ------
        CleanupUnconfirmedError
            Cleanup overrides a safe primary failure, retained in its primary
            attribute. The private receipt remains for explicit recovery.
        DockerOperationError
            Create, stream or wait cannot be confirmed. No automatic create retry.

        Notes
        -----
        Each API request, the acquired stream and the exit wait have separate
        limits. This is not a total wall-clock deadline. The lifecycle lock is
        held through recovery, creation and cleanup; another caller cannot steal
        a live job by recovering its receipt. Caller directories must be private.
        """
        with ReceiptStore(job.receipt_path) as store:
            store.recover(self._containers)
            receipt = self._containers.reserve(job.spec)
            store.save(receipt)
            identity = None
            primary = None
            try:
                identity = self._containers.create(job.spec, receipt)
                stdout, stderr = bytearray(), bytearray()
                with self._execution.attach(identity, job.limits) as stream:
                    self._containers.start(identity)
                    while frame := stream.read_frame():
                        (stdout if frame.channel == "stdout" else stderr).extend(
                            frame.data
                        )
                status = self._containers.wait(
                    identity, timeout=job.wait_timeout_seconds
                )
                return CommandResult(
                    exit_code=status, stdout=bytes(stdout), stderr=bytes(stderr)
                )
            except DockerOperationError as error:
                primary = error
                raise
            except Exception:
                primary = DockerOperationError("run one-shot container")
                raise primary from None
            finally:
                try:
                    store.cleanup(self._containers, receipt, identity)
                except CleanupUnconfirmedError as error:
                    error.primary = primary
                    raise error from None
