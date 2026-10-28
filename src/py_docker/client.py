"""Owned SDK client with explicit endpoint identity and reusable services."""

import docker
from docker.errors import DockerException

from py_docker.connection.resolver import ConnectionResolver
from py_docker.connection.settings import ConnectionSettings
from py_docker.containers.service import Containers
from py_docker.errors import DockerOperationError


class Client:
    """Close with a context manager. SDK escape hatch retains all Engine APIs."""

    def __init__(self, settings: ConnectionSettings | None = None, *, environment=None):
        self.settings = settings or ConnectionSettings()
        self.connection = ConnectionResolver().resolve(self.settings, environment)
        try:
            self.sdk = docker.DockerClient(base_url=self.connection.endpoint, version="auto", timeout=self.settings.timeout_seconds)
        except DockerException:
            raise DockerOperationError("connect to Docker") from None
        self.containers = Containers(self.sdk)

    def ping(self) -> bool:
        try:
            return self.sdk.ping()
        except DockerException:
            raise DockerOperationError("check Docker readiness") from None

    def close(self) -> None:
        self.sdk.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
