import socket
import time
import uuid
from pathlib import Path

import chromadb
import docker
import pytest

from docker_db.dbs.chroma_db import ChromaConfig, ChromaDB
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
            if container.name.startswith("test-chroma"):
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
def chroma_port():
    return _get_free_port()


@pytest.fixture
def clear_chroma_port(chroma_port):
    clear_port(chroma_port, "test-chroma")


@pytest.fixture
def chroma_config(chroma_port) -> ChromaConfig:
    name = f"test-chroma-{uuid.uuid4().hex[:8]}"
    chroma_data = Path(TEST_DIR, "data", "chromadata", name)
    chroma_data.mkdir(parents=True, exist_ok=True)

    return ChromaConfig(
        project_name="itest",
        volume_path=chroma_data,
        container_name=name,
        port=chroma_port,
        database="test-collection",
        retries=40,
        delay=3,
    )


@pytest.fixture
def chroma_manager(chroma_config: ChromaConfig):
    manager = ChromaDB(chroma_config)
    yield manager


@pytest.mark.usefixtures("clear_chroma_port")
def test_create_db_and_connection(chroma_manager: ChromaDB):
    chroma_manager.create_db()
    assert chroma_manager.database_created

    client = chroma_manager.connection
    collections = client.list_collections()
    names = {item.name for item in collections}
    assert chroma_manager.config.database in names

    chroma_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_chroma_port")
def test_add_and_query_document(chroma_manager: ChromaDB):
    chroma_manager.create_db()

    client: chromadb.HttpClient = chroma_manager.connection
    collection = client.get_collection(name=chroma_manager.config.database)
    vector = [0.1, 0.2, 0.3, 0.4]

    collection.add(
        ids=["doc-1"],
        documents=["hello chroma"],
        embeddings=[vector],
    )

    results = collection.query(query_embeddings=[vector], n_results=1)
    ids = results.get("ids", [[]])[0]
    assert len(ids) >= 1
    assert ids[0] == "doc-1"

    chroma_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_chroma_port")
def test_stop_and_restart(chroma_manager: ChromaDB):
    chroma_manager.create_db()
    chroma_manager.stop_db()
    assert chroma_manager.state() in ("exited", "created")

    time.sleep(1)
    chroma_manager.start_db()
    assert chroma_manager.state() == "running"

    chroma_manager.delete_db(running_ok=True)
