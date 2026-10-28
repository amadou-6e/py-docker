"""Owned SDK client with explicit endpoint identity and reusable services."""

from collections.abc import Mapping

from docker.errors import DockerException
from requests.exceptions import RequestException

from py_docker.connection.resolver import ConnectionResolver
from py_docker.connection.sdk import DirectDockerClient
from py_docker.connection.settings import SDK_API_VERSION, ConnectionSettings
from py_docker.containers.service import Containers
from py_docker.errors import DockerOperationError
from py_docker.execution.service import Execution
from py_docker.images.service import Images
from py_docker.jobs.service import Jobs
from py_docker.sessions.service import Sessions
from py_docker.volumes.service import Volumes


class Client:
    """Close with a context manager. SDK escape hatch retains all Engine APIs.

    Parameters
    ----------
    settings : ConnectionSettings or None
        Validated connection settings, with fixed defaults when omitted.
    environment : Mapping[str, str] or None
        Complete caller environment snapshot; None captures the process environment.
    allow_remote : bool
        Explicit permission for supported remote endpoints; never inferred from environment.
    """

    def __init__(
        self,
        settings: ConnectionSettings | None = None,
        *,
        environment: Mapping[str, str] | None = None,
        allow_remote: bool = False,
    ) -> None:
        """Resolve one endpoint and open the owned SDK session."""
        snapshot = ConnectionSettings.environment_snapshot(environment)
        self.settings = settings or ConnectionSettings.from_environment(snapshot)
        self.connection = ConnectionResolver().resolve(
            self.settings, snapshot, allow_remote=allow_remote
        )
        try:
            self.sdk = DirectDockerClient(
                base_url=self.connection.endpoint,
                version=SDK_API_VERSION,
                timeout=self.settings.timeout_seconds,
            )
        except (DockerException, RequestException):
            raise DockerOperationError("connect to Docker") from None
        self.containers = Containers(self.sdk)
        self.images = Images(self.sdk)
        self.volumes = Volumes(self.sdk)
        self.execution = Execution(self.sdk)
        self.jobs = Jobs(self.containers, self.execution)
        self.sessions = Sessions(self.containers, self.execution)

    def __enter__(self) -> "Client":
        """Return the owned client for a managed lifetime.

        Returns
        -------
        Client
            The same owned context object.
        """
        return self

    def __exit__(self, *_: object) -> None:
        """Close the owned SDK session when the context ends.

        Parameters
        ----------
        _ : tuple
            Context-manager exception information; cleanup must not replace a primary failure.
        """
        self.close()

    def ping(self) -> bool:
        """Check readiness without creating or mutating Docker resources.

        Returns
        -------
        bool
            Whether the selected Docker daemon reports readiness.
        """
        try:
            return self.sdk.ping()
        except (DockerException, RequestException):
            raise DockerOperationError("check Docker readiness") from None

    def close(self) -> None:
        """Release the SDK connection pools owned by this client."""
        self.sdk.close()
