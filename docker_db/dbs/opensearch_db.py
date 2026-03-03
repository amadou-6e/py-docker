"""OpenSearch container management module."""
import time

import docker
import requests
from docker.models.containers import Container
from opensearchpy import OpenSearch
from pydantic import Field

from docker_db.docker import ContainerConfig, ContainerManager


class OpenSearchConfig(ContainerConfig):
    """Configuration for OpenSearch container."""

    database: str = Field(default="documents", description="Default OpenSearch index name")
    port: int = Field(default=9200, description="OpenSearch HTTP API port")
    use_bind_mount: bool = Field(
        default=False,
        description=(
            "If True, bind-mount volume_path to /usr/share/opensearch/data. "
            "Disabled by default to avoid permission issues in CI."
        ),
    )
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "opensearch"


class OpenSearchDB(ContainerManager):
    """Manages lifecycle of an OpenSearch container via Docker SDK."""

    def __init__(self, config: OpenSearchConfig):
        """
        Initialize OpenSearch manager.

        Parameters
        ----------
        config : OpenSearchConfig
            OpenSearch container and connection configuration.
        """
        self.config: OpenSearchConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Establish a new OpenSearch client connection.

        Returns
        -------
        OpenSearch
            A client connected to the configured OpenSearch endpoint.
        """
        return OpenSearch(
            hosts=[{"host": self.config.host, "port": self.config.port}],
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            timeout=5,
            max_retries=0,
            retry_on_timeout=False,
        )

    def connection_string(self, db_name: str = None, sql_magic: bool = False) -> str:
        """
        Get OpenSearch base URL.

        Parameters
        ----------
        db_name : str, optional
            Unused for OpenSearch. Present for interface compatibility.
        sql_magic : bool, optional
            Unused for OpenSearch. Present for interface compatibility.

        Returns
        -------
        str
            Base HTTP URL for the OpenSearch endpoint.
        """
        return f"http://{self.config.host}:{self.config.port}"

    def _get_environment_vars(self):
        default_env_vars = {
            "discovery.type": "single-node",
            "DISABLE_SECURITY_PLUGIN": "true",
            "DISABLE_INSTALL_DEMO_CONFIG": "true",
            "OPENSEARCH_JAVA_OPTS": "-Xms512m -Xmx512m",
        }
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        if not self.config.use_bind_mount:
            return []
        if self.config.volume_path is None:
            return []
        return [
            docker.types.Mount(
                target="/usr/share/opensearch/data",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"9200/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": [
                "CMD-SHELL",
                "curl -sf http://localhost:9200 >/dev/null || exit 1",
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
        """Create the default OpenSearch index if it does not exist."""
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        index_name = db_name or self.config.database
        last_error = None
        for _ in range(self.config.retries):
            try:
                client = self.connection
                if not client.indices.exists(index=index_name):
                    client.indices.create(index=index_name)
                self.database_created = True
                return container
            except Exception as exc:
                last_error = exc
                time.sleep(self.config.delay)

        raise RuntimeError(f"Failed to initialize OpenSearch index '{index_name}': {last_error}")

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """Wait until OpenSearch API is reachable."""
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
                response = requests.get(base_url, timeout=2)
                if response.status_code != 200:
                    time.sleep(self.config.delay)
                    continue
                health = requests.get(
                    f"{base_url}/_cluster/health",
                    params={"wait_for_status": "yellow", "timeout": "1s"},
                    timeout=2,
                )
                if health.status_code == 200:
                    status = health.json().get("status")
                    if status in ("yellow", "green"):
                        return True
            except Exception:
                pass
            time.sleep(self.config.delay)

        return False

    def test_connection(self):
        """Ensure OpenSearch API is reachable."""
        if not self._wait_for_db():
            raise ConnectionError("OpenSearch API is not reachable.")
        try:
            client = self.connection
            if client.ping():
                    return True
        except Exception as exc:
            raise ConnectionError(f"OpenSearch API ping failed: {exc}") from exc
