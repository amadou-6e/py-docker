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
        self, operation: str, receipt: ContainerReservation | VolumeIdentity
    ) -> None:
        """Retain the private receipt needed to reconcile uncertain creation."""
        self.receipt = receipt
        super().__init__(operation)
