"""
Redis container management module.

This module provides classes to manage Redis containers using Docker.
It enables developers to easily create, configure, start, stop, and delete Redis
containers for development and testing purposes.
"""
import time

import docker
import redis
from docker.models.containers import Container
from pydantic import Field
from redis.exceptions import ConnectionError as RedisConnectionError

from docker_db.docker import ContainerConfig, ContainerManager


class RedisConfig(ContainerConfig):
    """Configuration for Redis container."""
    database: int = Field(default=0, description="Redis logical database index")
    port: int = Field(default=6379, description="Port on which Redis listens")
    env_vars: dict = Field(
        default_factory=dict,
        description="A dictionary of environment variables to set in the container",
    )
    _type: str = "redis"


class RedisDB(ContainerManager):
    """Manages lifecycle of a Redis container via Docker SDK."""

    def __init__(self, config: RedisConfig):
        self.config: RedisConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Establish a new redis-py connection.

        Returns
        -------
        redis.Redis
            A Redis client connected to the configured host/port/db.
        """
        return redis.Redis(
            host=self.config.host,
            port=self.config.port,
            db=self.config.database,
            decode_responses=True,
        )

    def connection_string(self, db_name: int | None = None) -> str:
        """Get Redis connection string."""
        database = self.config.database if db_name is None else db_name
        return f"redis://{self.config.host}:{self.config.port}/{database}"

    def _get_environment_vars(self):
        default_env_vars = {}
        default_env_vars.update(self.config.env_vars)
        return default_env_vars

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/data",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {"6379/tcp": self.config.port}

    def _get_healthcheck(self):
        return {
            "Test": ["CMD", "redis-cli", "ping"],
            "Interval": 5000000000,  # 5s
            "Timeout": 3000000000,  # 3s
            "Retries": 10,
        }

    def _create_db(
        self,
        db_name: str | None = None,
        container: Container | None = None,
    ):
        """
        Validate Redis availability.

        Redis databases are logical indexes and do not require explicit creation.
        """
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        conn = self.connection
        conn.ping()
        self.database_created = True
        return container

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """
        Wait until Redis is accepting connections and ready.

        Returns
        -------
        bool
            True if Redis is ready, False otherwise.
        """
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

        for _ in range(self.config.retries):
            try:
                conn = self.connection
                conn.ping()
                return True
            except RedisConnectionError:
                time.sleep(self.config.delay)

        return False
