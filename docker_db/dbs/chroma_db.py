"""Chroma container management module."""
import time

import chromadb
import docker
import requests
from docker.models.containers import Container
from pydantic import Field

from docker_db.docker import ContainerConfig, ContainerManager


class ChromaConfig(ContainerConfig):
    """Configuration for Chroma container."""

    database: str = Field(default="documents", description="Default Chroma collection name")
    port: int = Field(default=8000, description="Chroma HTTP API port")
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "chroma"


class ChromaDB(ContainerManager):
    """Manages lifecycle of a Chroma container via Docker SDK."""

    def __init__(self, config: ChromaConfig):
        """
        Initialize Chroma manager.

        Parameters
        ----------
        config : ChromaConfig
            Chroma container and connection configuration.
        """
        self.config: ChromaConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Establish a new Chroma HTTP client connection.

        Returns
        -------
        chromadb.HttpClient
            A client connected to the configured Chroma endpoint.
        """
        return chromadb.HttpClient(host=self.config.host, port=self.config.port)

    def connection_string(self, db_name: str = None, sql_magic: bool = False) -> str:
        """
        Get Chroma base URL.

        Parameters
        ----------
        db_name : str, optional
            Unused for Chroma. Present for interface compatibility.
        sql_magic : bool, optional
            Unused for Chroma. Present for interface compatibility.

        Returns
        -------
        str
            Base HTTP URL for the Chroma endpoint.
        """
        return f"http://{self.config.host}:{self.config.port}"

    def _get_environment_vars(self):
        default_env_vars = {
            "IS_PERSISTENT": "TRUE",
            "ANONYMIZED_TELEMETRY": "FALSE",
            "ALLOW_RESET": "TRUE",
        }
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/chroma/chroma",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"8000/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": [
                "CMD-SHELL",
                "curl -sf http://localhost:8000/api/v1/heartbeat >/dev/null || exit 1",
            ],
            "Interval": 10_000_000_000,  # 10s
            "Timeout": 5_000_000_000,  # 5s
            "Retries": 15,
        }

    def _create_db(
        self,
        db_name: str | None = None,
        container: Container | None = None,
    ):
        """Create the default Chroma collection if it does not exist."""
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        collection_name = db_name or self.config.database
        last_error = None
        for _ in range(self.config.retries):
            try:
                client = self.connection
                client.get_or_create_collection(name=collection_name)
                self.database_created = True
                return container
            except Exception as exc:
                last_error = exc
                time.sleep(self.config.delay)

        raise RuntimeError(f"Failed to initialize Chroma collection '{collection_name}': {last_error}")

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """Wait until Chroma API is reachable."""
        try:
            container = container or self.client.containers.get(self.config.container_name)
            for _ in range(self.config.retries):
                container.reload()
                if container.attrs.get("State", {}).get("Running", False):
                    break
                time.sleep(self.config.delay)
        except (docker.errors.NotFound, docker.errors.APIError):
            pass

        for _ in range(self.config.retries):
            try:
                container = container or self.client.containers.get(self.config.container_name)
                container.reload()
                if not container.attrs.get("State", {}).get("Running", False):
                    return False

                base_url = self.connection_string()
                for endpoint in (
                    "/api/v1/heartbeat",
                    "/api/v2/heartbeat",
                    "/api/v1/version",
                    "/api/v1",
                ):
                    response = requests.get(f"{base_url}{endpoint}", timeout=2)
                    if response.status_code == 200:
                        return True
            except Exception:
                pass
            time.sleep(self.config.delay)

        return False

    def test_connection(self):
        """
        Ensure Chroma API is reachable.

        Returns
        -------
        bool
            True when at least one Chroma readiness endpoint is reachable.
        """
        if not self._wait_for_db():
            raise ConnectionError("Chroma API is not reachable.")
        base_url = self.connection_string()
        last_error = None
        for endpoint in (
            "/api/v2/heartbeat",
            "/api/v1/heartbeat",
            "/api/v1/version",
            "/api/v1",
        ):
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=3)
                if response.status_code == 200:
                    return True
                last_error = RuntimeError(response.text)
            except Exception as exc:
                last_error = exc
        raise ConnectionError(f"Chroma API ping failed: {last_error}")
