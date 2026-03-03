"""Weaviate container management module."""
import re
import time

import docker
import requests
from docker.models.containers import Container
from pydantic import Field

from docker_db.docker import ContainerConfig, ContainerManager


def _normalize_class_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not cleaned:
        cleaned = "Documents"
    if not cleaned[0].isalpha():
        cleaned = f"C{cleaned}"
    return cleaned[0].upper() + cleaned[1:]


class WeaviateConfig(ContainerConfig):
    """Configuration for Weaviate container."""

    database: str = Field(default="documents", description="Default Weaviate class name seed")
    port: int = Field(default=8080, description="Weaviate HTTP API port")
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "weaviate"


class WeaviateDB(ContainerManager):
    """Manages lifecycle of a Weaviate container via Docker SDK."""

    def __init__(self, config: WeaviateConfig):
        """
        Initialize Weaviate manager.

        Parameters
        ----------
        config : WeaviateConfig
            Weaviate container and connection configuration.
        """
        self.config: WeaviateConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Create a persistent HTTP session for Weaviate API calls.

        Returns
        -------
        requests.Session
            Session configured with JSON headers for Weaviate HTTP endpoints.
        """
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session

    def connection_string(self, db_name: str = None, sql_magic: bool = False) -> str:
        """
        Get Weaviate base URL.

        Parameters
        ----------
        db_name : str, optional
            Unused for Weaviate. Present for interface compatibility.
        sql_magic : bool, optional
            Unused for Weaviate. Present for interface compatibility.

        Returns
        -------
        str
            Base HTTP URL for the Weaviate endpoint.
        """
        return f"http://{self.config.host}:{self.config.port}"

    def _get_environment_vars(self):
        default_env_vars = {
            "AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED": "true",
            "PERSISTENCE_DATA_PATH": "/var/lib/weaviate",
            "DEFAULT_VECTORIZER_MODULE": "none",
            "ENABLE_MODULES": "",
        }
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/var/lib/weaviate",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"8080/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": [
                "CMD-SHELL",
                "wget -qO- http://localhost:8080/v1/.well-known/ready >/dev/null || exit 1",
            ],
            "Interval": 10_000_000_000,  # 10s
            "Timeout": 5_000_000_000,  # 5s
            "Retries": 20,
        }

    def _create_db(
        self,
        db_name: str | None = None,
        container: Container | None = None,
    ):
        """
        Create default Weaviate class if it does not exist.

        Parameters
        ----------
        db_name : str, optional
            Desired class name. Defaults to configured database name.
        container : docker.models.containers.Container, optional
            Existing container reference. If omitted, fetched by configured name.

        Returns
        -------
        docker.models.containers.Container
            Running container with initialized class.
        """
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        class_name = _normalize_class_name(db_name or self.config.database)
        last_error = None
        for _ in range(self.config.retries):
            try:
                session = self.connection
                base_url = self.connection_string()
                schema_response = session.get(f"{base_url}/v1/schema", timeout=3)
                schema_response.raise_for_status()
                classes = schema_response.json().get("classes", [])
                existing = {entry.get("class") for entry in classes}

                if class_name not in existing:
                    create_response = session.post(
                        f"{base_url}/v1/schema",
                        json={
                            "class": class_name,
                            "vectorizer": "none",
                            "properties": [
                                {"name": "text", "dataType": ["text"]},
                            ],
                        },
                        timeout=3,
                    )
                    create_response.raise_for_status()
                self.database_created = True
                return container
            except Exception as exc:
                last_error = exc
                time.sleep(self.config.delay)

        raise RuntimeError(f"Failed to initialize Weaviate class '{class_name}': {last_error}")

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """
        Wait until Weaviate API is reachable.

        Parameters
        ----------
        container : docker.models.containers.Container, optional
            Existing container reference. If omitted, fetched by configured name.

        Returns
        -------
        bool
            True if ready endpoint responds with HTTP 200 within retry window.
        """
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

                response = requests.get(
                    f"{self.connection_string()}/v1/.well-known/ready",
                    timeout=2,
                )
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(self.config.delay)

        return False

    def test_connection(self):
        """
        Ensure Weaviate API is reachable.

        Returns
        -------
        bool
            True when heartbeat endpoint can be reached.
        """
        if not self._wait_for_db():
            raise ConnectionError("Weaviate API is not reachable.")
        try:
            response = requests.get(f"{self.connection_string()}/v1/meta", timeout=3)
            response.raise_for_status()
            return True
        except Exception as exc:
            raise ConnectionError(f"Weaviate API ping failed: {exc}") from exc
