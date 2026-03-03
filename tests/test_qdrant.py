import socket
import time
import uuid
from pathlib import Path

import docker
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from docker_db.dbs.qdrant_db import QdrantConfig, QdrantDB
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
            if container.name.startswith("test-qdrant"):
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
def qdrant_port():
    return _get_free_port()


@pytest.fixture
def clear_qdrant_port(qdrant_port):
    clear_port(qdrant_port, "test-qdrant")


@pytest.fixture
def qdrant_config(qdrant_port) -> QdrantConfig:
    name = f"test-qdrant-{uuid.uuid4().hex[:8]}"
    qdrant_data = Path(TEST_DIR, "data", "qdrantdata", name)
    qdrant_data.mkdir(parents=True, exist_ok=True)

    return QdrantConfig(
        project_name="itest",
        volume_path=qdrant_data,
        container_name=name,
        port=qdrant_port,
        database="test-collection",
        vector_size=8,
        retries=40,
        delay=3,
    )


@pytest.fixture
def qdrant_manager(qdrant_config: QdrantConfig):
    manager = QdrantDB(qdrant_config)
    yield manager


@pytest.mark.usefixtures("clear_qdrant_port")
def test_create_db_and_connection(qdrant_manager: QdrantDB):
    qdrant_manager.create_db()
    assert qdrant_manager.database_created

    client = qdrant_manager.connection
    collections = client.get_collections().collections
    names = {collection.name for collection in collections}
    assert qdrant_manager.config.database in names

    qdrant_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_qdrant_port")
def test_upsert_and_search_point(qdrant_manager: QdrantDB):
    qdrant_manager.create_db()

    client: QdrantClient = qdrant_manager.connection
    collection_name = qdrant_manager.config.database
    vector = [0.1] * qdrant_manager.config.vector_size
    point = PointStruct(id=1, vector=vector, payload={"text": "hello qdrant"})

    client.upsert(collection_name=collection_name, points=[point], wait=True)
    results = client.search(
        collection_name=collection_name,
        query_vector=vector,
        limit=1,
    )
    assert len(results) >= 1
    assert results[0].payload.get("text") == "hello qdrant"

    qdrant_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_qdrant_port")
def test_stop_and_restart(qdrant_manager: QdrantDB):
    qdrant_manager.create_db()
    qdrant_manager.stop_db()
    assert qdrant_manager.state() in ("exited", "created")

    time.sleep(1)
    qdrant_manager.start_db()
    assert qdrant_manager.state() == "running"

    qdrant_manager.delete_db(running_ok=True)
