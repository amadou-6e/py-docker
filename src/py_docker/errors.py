"""Safe library failures; callers own presentation and recovery policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_docker.containers.models import ContainerReservation
    from py_docker.volumes.models import VolumeIdentity


class DockerOperationError(RuntimeError):
    """Docker operation failed; completion is unconfirmed unless stated otherwise.

    Parameters
    ----------
    operation : str
        Safe diagnostic phase written by library code, never raw external error text.
    """

    code = "docker_operation_failed"

    def __init__(self, operation: str) -> None:
        """Retain safe diagnostic context without exposing external response text."""
        self.operation = operation
        super().__init__(
            f"Docker could not complete {operation}; verify the resource state."
        )


class ConnectionConfigurationError(DockerOperationError):
    """Endpoint configuration is unsupported; no container operation was sent."""

    code = "docker_connection_configuration_invalid"


class OwnershipConflictError(DockerOperationError):
    """Resource identity differs; no destructive request was sent."""

    code = "docker_resource_ownership_conflict"


class OutputLimitError(DockerOperationError):
    """A read exceeded its limit; remote work may still be running."""

    code = "docker_output_limit_exceeded"


class DeadlineError(DockerOperationError):
    """A stream deadline expired; remote work may still be running."""

    code = "docker_deadline_exceeded"


class JobCancelledError(DockerOperationError):
    """The caller cancelled a job; successful cleanup is required before it escapes.

    Cleanup uncertainty takes precedence as CleanupUnconfirmedError, retaining
    this safe cancellation as its primary failure. Cancellation never reports a
    process exit code or implies that earlier workspace effects were undone.
    """

    code = "docker_job_cancelled"


class CreationUnconfirmedError(DockerOperationError):
    """Creation may have happened; receipt supports exact ownership reconciliation.

    Parameters
    ----------
    operation : str
        Safe diagnostic phase written by library code, never raw external error text.
    receipt : ContainerReservation or VolumeIdentity
        Private ownership intent retained across an uncertain create result.
    """

    code = "docker_creation_unconfirmed"

    def __init__(
        self,
        operation: str,
        receipt: ContainerReservation | VolumeIdentity,
    ) -> None:
        """Retain the private receipt needed to reconcile uncertain creation."""
        self.receipt = receipt
        super().__init__(operation)


class CreationRejectedError(DockerOperationError):
    """The create endpoint definitively rejected the request without creating it.

    Parameters
    ----------
    operation : str
        Safe create phase, never raw daemon response text.
    receipt : ContainerReservation
        Private intent belonging to this rejected request, not any conflicting resource.
    """

    code = "docker_creation_rejected"

    def __init__(self, operation: str, receipt: ContainerReservation) -> None:
        """Retain rejected intent without presenting it as an uncertain creation."""
        self.receipt = receipt
        super().__init__(operation)


class CleanupUnconfirmedError(DockerOperationError):
    """An owned job may remain active; its private receipt must be retained.

    Parameters
    ----------
    operation : str
        Safe library phase, never external response text or a private file path.
    receipt : ContainerReservation or None
        Canonical ownership intent when readable; None for a corrupt private record.
    primary : DockerOperationError or None
        Safe original library failure overridden by cleanup uncertainty. A nonzero
        process exit is a result, not a primary exception.
    """

    code = "docker_cleanup_unconfirmed"

    def __init__(
        self,
        operation: str,
        receipt: ContainerReservation | None = None,
        primary: DockerOperationError | None = None,
    ) -> None:
        """Retain recovery intent and the safe original failure without printing secrets."""
        self.receipt = receipt
        self.primary = primary
        super().__init__(operation)


class PendingReceiptError(CleanupUnconfirmedError):
    """A pending private receipt cannot be replaced; no new create request was sent."""

    code = "docker_receipt_pending"


class ReceiptInUseError(DockerOperationError):
    """Another caller holds the receipt lock; this attempt sent no cleanup or create."""

    code = "docker_receipt_in_use"
