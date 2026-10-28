"""Safe library failures; callers own presentation and recovery policy."""


class DockerOperationError(RuntimeError):
    """Docker operation failed; completion is unconfirmed unless stated otherwise."""

    code = "docker_operation_failed"

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"Docker could not complete {operation}; verify the resource state.")


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
    """A total deadline expired; remote work may still be running."""

    code = "docker_deadline_exceeded"
