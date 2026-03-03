"""
Ollama container management module.

This module provides classes to manage Ollama containers using Docker.
It enables developers to easily create, configure, start, stop, and delete Ollama
containers for development and testing purposes.
"""
import time

import docker
import requests
from docker.models.containers import Container
from pydantic import Field
from requests.exceptions import RequestException

from docker_db.docker import ContainerConfig, ContainerManager


class OllamaConfig(ContainerConfig):
    """Configuration for an Ollama container."""

    database: str = Field(
        default="ollama",
        description="Compatibility field required by the base container manager API.",
    )
    model: str | None = Field(
        default=None,
        description="Optional model name to pull after container startup.",
    )
    pull_model_on_create: bool = Field(
        default=False,
        description="If True and model is set, pull the model in create_db().",
    )
    port: int = Field(default=11434, description="Port on which Ollama listens")
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "ollama"


class OllamaDB(ContainerManager):
    """Manages lifecycle of an Ollama container via Docker SDK."""

    def __init__(self, config: OllamaConfig):
        self.config: OllamaConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Establish a new HTTP session to the Ollama API.

        Returns
        -------
        requests.Session
            A new HTTP session object.
        """
        return requests.Session()

    @property
    def base_url(self) -> str:
        """Return Ollama API base URL."""
        return f"http://{self.config.host}:{self.config.port}"

    def connection_string(self, db_name: str = None, sql_magic: bool = False) -> str:
        """
        Get Ollama base URL.

        Parameters
        ----------
        db_name : str, optional
            Unused placeholder for API compatibility with other managers.
        sql_magic : bool, optional
            Unused placeholder for API compatibility with SQL-oriented managers.

        Returns
        -------
        str
            Base URL of the Ollama API endpoint.
        """
        return self.base_url

    def _get_environment_vars(self):
        default_env_vars = {}
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/root/.ollama",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"11434/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": ["CMD", "ollama", "--version"],
            "Interval": 5000000000,  # 5s
            "Timeout": 3000000000,  # 3s
            "Retries": 10,
        }

    def _wait_for_api_ready(self) -> bool:
        for _ in range(self.config.retries):
            try:
                response = requests.get(
                    f"{self.base_url}/api/tags",
                    timeout=5,
                )
                if response.status_code == 200:
                    return True
            except RequestException:
                pass
            time.sleep(self.config.delay)
        return False

    def _create_db(
        self,
        db_name: str | None = None,
        container: Container | None = None,
    ):
        """Validate Ollama API availability and optionally pull a model."""
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        if not self._wait_for_api_ready():
            raise RuntimeError("Ollama API did not become ready in time.")

        if self.config.pull_model_on_create and self.config.model:
            self.pull_model(self.config.model)

        self.database_created = True
        return container

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """Wait until Ollama API is accepting connections and ready."""
        try:
            container = container or self.client.containers.get(self.config.container_name)
            for _ in range(self.config.retries):
                container.reload()
                state = container.attrs.get("State", {})
                if state.get("Running", False):
                    break
                time.sleep(self.config.delay)
        except (docker.errors.NotFound, docker.errors.APIError):
            pass

        return self._wait_for_api_ready()

    def pull_model(self, model: str):
        """
        Pull a model via Ollama API.

        Parameters
        ----------
        model : str
            Model name to download into the local Ollama store.

        Returns
        -------
        dict
            JSON response returned by Ollama pull endpoint.
        """
        response = requests.post(
            f"{self.base_url}/api/pull",
            json={"model": model, "stream": False},
            timeout=600,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Failed to pull model '{model}': {response.text}")
        return response.json()

    def list_models(self) -> list[dict]:
        """List locally available models."""
        response = requests.get(f"{self.base_url}/api/tags", timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to list models: {response.text}")
        payload = response.json()
        return payload.get("models", [])

    def test_connection(self):
        """Ensure Ollama API is reachable."""
        if not self._wait_for_api_ready():
            raise ConnectionError("Ollama API is not reachable.")
