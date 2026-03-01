"""Container data models and defaults."""
import os
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

SHORTHAND_MAP = {
    "postgres": "pg",
    "mysql": "my",
    "mariadb": "my",
    "mssql": "ms",
    "mongodb": "mg",
    "cassandra": "cs",
    "redis": "rd",
}

DEFAULT_IMAGE_MAP = {
    "postgres": "postgres:16",
    "mysql": "mysql:8",
    "mariadb": "mariadb:10",
    "mssql": "mcr.microsoft.com/mssql/server:2022-latest",
    "mongodb": "mongo:6",
    "cassandra": "cassandra:4",
    "redis": "redis:7",
}

class ContainerConfig(BaseModel):
    """Configuration for a Docker container running a database."""
    host: str = Field(
        default="127.0.0.1",
        description="The hostname where the PostgreSQL server will be accessible",
    )
    port: int | None = Field(
        default=None,
        description="The port number where the PostgreSQL server will be accessible",
    )
    project_name: str = Field(
        default="docker_db",
        description="Name of the project, used as a prefix for container and image names",
    )
    image_name: str | None = Field(
        default=None,
        description='Name of the Docker image, defaults to "{project_name}-{db_type}:dev"',
    )
    container_name: str | None = Field(
        default=None,
        description='Name of the Docker container, defaults to "{project_name}-{db_type}"',
    )
    workdir: Path | None = Field(
        default=None,
        description="Working directory for Docker operations, defaults to current directory",
    )
    dockerfile_path: Path | None = Field(
        default=None,
        description='Path to the Dockerfile, defaults to "{workdir}/docker/Dockerfile.pgdb"',
    )
    init_script: Path | None = Field(
        default=None,
        description="Path to initialization script for database setup",
    )
    volume_path: Path | None = Field(
        default=None,
        description='Path to persist PostgreSQL data, defaults to "{workdir}/pgdata"',
    )
    network_mode: str | None = Field(
        default=None,
        description=(
            "Docker network mode: 'host', 'bridge', 'none', or custom network name. "
            "'host' only works on Linux and falls back to bridge elsewhere."
        ),
    )
    extra_hosts: dict[str, str] | None = Field(
        default=None,
        description="Additional host-to-IP mappings for /etc/hosts in container.",
    )
    retries: int = Field(default=10, description="Number of connection retry attempts")
    delay: int = Field(default=3, description="Delay in seconds between retry attempts")
    _type: str | None = None  # internal field, not exposed via schema

    def model_post_init(self, __context__):
        self.workdir = (self.workdir or Path(os.getenv("WORKDIR", os.getcwd()))).resolve()
        self.image_name = self.image_name or DEFAULT_IMAGE_MAP[self._type]
        self.container_name = self.container_name or f"{self.project_name}-{self._type}-{uuid.uuid4().hex[:8]}"
        self.volume_path = self.volume_path or Path(self.workdir,
                                                    f"{SHORTHAND_MAP[self._type]}data")
        self.volume_path.mkdir(parents=True, exist_ok=True)


