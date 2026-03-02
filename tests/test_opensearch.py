import socket
import time
import uuid
from pathlib import Path

import docker
import pytest
from opensearchpy import OpenSearch

from docker_db.dbs.opensearch_db import OpenSearchConfig, OpenSearchDB
from tests.conftest import *
from .utils import clear_port, nuke_dir


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(autouse=True)
def cleanup_temp_dir():
    nuke_dir(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    yield
    nuke_dir(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_containers():
    client = docker.from_env()

    def _cleanup():
        for container in client.containers.list(all=True):
            if container.name.startswith("test-opensearch"):
                try:
                    container.stop(timeout=5)
                except docker.errors.APIError:
                    pass
                try:
                    container.remove(force=True)
                except docker.errors.APIError:
                    pass

    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def opensearch_port():
    return _get_free_port()


@pytest.fixture
def clear_opensearch_port(opensearch_port):
    clear_port(opensearch_port, "test-opensearch")


@pytest.fixture
def opensearch_config(opensearch_port) -> OpenSearchConfig:
    name = f"test-opensearch-{uuid.uuid4().hex[:8]}"
    opensearch_data = Path(TEST_DIR, "data", "opensearchdata", name)
    opensearch_data.mkdir(parents=True, exist_ok=True)

    return OpenSearchConfig(
        project_name="itest",
        volume_path=opensearch_data,
        container_name=name,
        port=opensearch_port,
        database="test-index",
        retries=40,
        delay=3,
    )


@pytest.fixture
def opensearch_manager(opensearch_config: OpenSearchConfig):
    manager = OpenSearchDB(opensearch_config)
    yield manager


@pytest.mark.usefixtures("clear_opensearch_port")
def test_create_db_and_connection(opensearch_manager: OpenSearchDB):
    opensearch_manager.create_db()
    assert opensearch_manager.database_created

    client = opensearch_manager.connection
    assert client.ping() is True
    assert client.indices.exists(index=opensearch_manager.config.database)

    opensearch_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_opensearch_port")
def test_index_and_search_document(opensearch_manager: OpenSearchDB):
    opensearch_manager.create_db()

    client: OpenSearch = opensearch_manager.connection
    index_name = opensearch_manager.config.database

    client.index(
        index=index_name,
        id="doc-1",
        body={"title": "OpenSearch test", "content": "hello opensearch"},
        refresh=True,
    )

    response = client.search(
        index=index_name,
        body={"query": {"match": {"content": "hello"}}},
    )
    hits = response.get("hits", {}).get("hits", [])
    assert len(hits) >= 1
    assert hits[0]["_source"]["title"] == "OpenSearch test"

    opensearch_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_opensearch_port")
def test_stop_and_restart(opensearch_manager: OpenSearchDB):
    opensearch_manager.create_db()
    opensearch_manager.stop_db()
    assert opensearch_manager.state() in ("exited", "created")

    time.sleep(1)
    opensearch_manager.start_db()
    assert opensearch_manager.state() == "running"

    opensearch_manager.delete_db(running_ok=True)
