"""
Neo4j container management module.

Neo4j is the primary graph database used in GraphRAG pipelines (Microsoft Research,
2024). Storing entities and relationships as a graph lets a retriever traverse
multi-hop connections that dense-vector search alone cannot follow, substantially
improving answer quality on complex, relationship-heavy questions.

LlamaIndex and LangChain both ship Neo4j integrations out of the box:
- ``llama_index.graph_stores.neo4j.Neo4jGraphStore``
- ``langchain_community.graphs.Neo4jGraph``

Use ``Neo4jDB`` to provision a local Neo4j instance for GraphRAG experimentation
without any manual Docker configuration.

Ports
-----
- **7687** (Bolt protocol) — used by the Python drivers and LlamaIndex/LangChain
- **7474** (HTTP) — Neo4j Browser UI
"""
import time

import docker
from docker.models.containers import Container
from pydantic import Field

from docker_db.docker import ContainerConfig, ContainerManager


class Neo4jConfig(ContainerConfig):
    """Configuration for a Neo4j container."""
    user: str = Field(default="neo4j", description="Neo4j username")
    password: str = Field(description="Neo4j password (minimum 8 characters)")
    database: str = Field(default="neo4j", description="Name of the Neo4j database")
    port: int = Field(default=7687, description="Bolt protocol port")
    http_port: int = Field(default=7474, description="HTTP / Neo4j Browser port")
    env_vars: dict = Field(
        default_factory=dict,
        description="Extra environment variables to pass to the container",
    )
    _type: str = "neo4j"


class Neo4jDB(ContainerManager):
    """
    Manages lifecycle of a Neo4j container via Docker SDK.

    The ``connection`` property returns a ``neo4j.Driver`` using the Bolt protocol.
    Pass it directly to ``Neo4jGraphStore`` (LlamaIndex) or ``Neo4jGraph``
    (LangChain) for GraphRAG pipelines.

    Parameters
    ----------
    config : Neo4jConfig
        Configuration for the Neo4j container.
    """

    def __init__(self, config: Neo4jConfig):
        self.config: Neo4jConfig = config
        assert self._is_docker_running()
        self.client = docker.from_env()

    @property
    def connection(self):
        """
        Return a ``neo4j.Driver`` connected via Bolt.

        The ``neo4j`` package must be installed (``pip install neo4j``).

        Returns
        -------
        neo4j.Driver
            An authenticated driver ready for session creation.
        """
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise ImportError(
                "Install the neo4j driver: pip install neo4j"
            ) from exc

        return GraphDatabase.driver(
            self.connection_string(),
            auth=(self.config.user, self.config.password),
        )

    def connection_string(self, db_name: str | None = None) -> str:
        """Return a Bolt URI for the configured host and port."""
        return f"bolt://{self.config.host}:{self.config.port}"

    def _get_environment_vars(self):
        env = {
            "NEO4J_AUTH": f"{self.config.user}/{self.config.password}",
            "NEO4J_dbms_connector_bolt_listen__address": f"0.0.0.0:{self.config.port}",
            "NEO4J_dbms_connector_http_listen__address": f"0.0.0.0:{self.config.http_port}",
            "NEO4J_dbms_connector_https_enabled": "false",
            "NEO4J_dbms_security_auth__minimum__password__length": "8",
        }
        env.update(self.config.env_vars)
        return env

    def _get_volume_mounts(self):
        return [
            docker.types.Mount(
                target="/data",
                source=str(self.config.volume_path),
                type="bind",
            )
        ]

    def _get_port_mappings(self):
        return {
            f"{self.config.port}/tcp": self.config.port,
            f"{self.config.http_port}/tcp": self.config.http_port,
        }

    def _get_healthcheck(self):
        return {
            "Test": [
                "CMD-SHELL",
                f"wget -qO- http://localhost:{self.config.http_port}/browser/ || exit 1",
            ],
            "Interval": 10_000_000_000,  # 10 s — Neo4j starts slowly
            "Timeout": 5_000_000_000,    # 5 s
            "Retries": 12,
        }

    def _create_db(
        self,
        db_name: str | None = None,
        container: Container | None = None,
    ):
        """Verify Neo4j is reachable via Bolt and accepts authentication."""
        container = container or self.client.containers.get(self.config.container_name)
        container.reload()
        if not container.attrs.get("State", {}).get("Running", False):
            raise RuntimeError(f"Container {container.name} is not running.")

        driver = self.connection
        with driver.session(database=self.config.database) as session:
            session.run("RETURN 1")
        driver.close()

        self.database_created = True
        return container

    def _wait_for_db(self, container: Container | None = None) -> bool:
        """Wait until Neo4j accepts Bolt connections."""
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
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(
                    self.connection_string(),
                    auth=(self.config.user, self.config.password),
                )
                with driver.session(database=self.config.database) as session:
                    session.run("RETURN 1")
                driver.close()
                return True
            except ImportError as exc:
                raise ImportError("Install the neo4j driver: pip install neo4j") from exc
            except Exception:
                time.sleep(self.config.delay)

        return False
