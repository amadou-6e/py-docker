"""Qdrant container management module."""
import time

import docker
import requests
from docker.models.containers import Container
from pydantic import Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from docker_db.docker import ContainerConfig, ContainerManager


class QdrantConfig(ContainerConfig):
    """Configuration for Qdrant container."""

    database: str = Field(default="documents", description="Default Qdrant collection name")
    port: int = Field(default=6333, description="Qdrant HTTP API port")
    vector_size: int = Field(default=384, description="Default vector size for created collection")
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "qdrant"


class QdrantDB(ContainerManager):
    """Manages lifecycle of a Qdrant container via Docker SDK."""

    def __init__(self, config: QdrantConfig):
        self.config: QdrantConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Establish a new Qdrant client connection.

        Returns
        -------
        QdrantClient
            A client connected to the configured Qdrant endpoint.
        """
        return QdrantClient(
            url=self.connection_string(),
            timeout=5.0,
            check_compatibility=False,
        )

    def connection_string(self, db_name: str = None, sql_magic: bool = False) -> str:
        """
        Get Qdrant base URL.

        Parameters
        ----------
        db_name : str, optional
            Unused for Qdrant. Present for interface compatibility.
        sql_magic : bool, optional
            Unused for Qdrant. Present for interface compatibility.

        Returns
        -------
        str
            Base HTTP URL for the Qdrant endpoint.
        """
        return f"http://{self.config.host}:{self.config.port}"

    def _get_environment_vars(self):
        default_env_vars = {}
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/qdrant/storage",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"6333/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": [
                "CMD-SHELL",
                "curl -sf http://localhost:6333/collections >/dev/null || exit 1",
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
        """Create the default Qdrant collection if it does not exist."""
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        collection_name = db_name or self.config.database
        last_error = None
        for _ in range(self.config.retries):
            try:
                client = self.connection
                collections = client.get_collections().collections
                existing = {collection.name for collection in collections}
                if collection_name not in existing:
                    client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.config.vector_size,
                            distance=Distance.COSINE,
                        ),
                    )
                self.database_created = True
                return container
            except Exception as exc:
                last_error = exc
                time.sleep(self.config.delay)

        raise RuntimeError(f"Failed to initialize Qdrant collection '{collection_name}': {last_error}")

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """Wait until Qdrant API is reachable."""
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
                response = requests.get(f"{self.connection_string()}/collections", timeout=2)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(self.config.delay)

        return False

    def test_connection(self):
        """Ensure Qdrant API is reachable."""
        if not self._wait_for_db():
            raise ConnectionError("Qdrant API is not reachable.")
        try:
            self.connection.get_collections()
            return True
        except Exception as exc:
            raise ConnectionError(f"Qdrant API ping failed: {exc}") from exc
