import socket
import time
import uuid
from pathlib import Path

import docker
import pytest
import requests

from docker_db.dbs.weaviate_db import WeaviateConfig, WeaviateDB
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
            if container.name.startswith("test-weaviate"):
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
def weaviate_port():
    return _get_free_port()


@pytest.fixture
def clear_weaviate_port(weaviate_port):
    clear_port(weaviate_port, "test-weaviate")


@pytest.fixture
def weaviate_config(weaviate_port) -> WeaviateConfig:
    name = f"test-weaviate-{uuid.uuid4().hex[:8]}"
    weaviate_data = Path(TEST_DIR, "data", "weaviatedata", name)
    weaviate_data.mkdir(parents=True, exist_ok=True)

    return WeaviateConfig(
        project_name="itest",
        volume_path=weaviate_data,
        container_name=name,
        port=weaviate_port,
        database="test_collection",
        retries=40,
        delay=3,
    )


@pytest.fixture
def weaviate_manager(weaviate_config: WeaviateConfig):
    manager = WeaviateDB(weaviate_config)
    yield manager


@pytest.mark.usefixtures("clear_weaviate_port")
def test_create_db_and_connection(weaviate_manager: WeaviateDB):
    weaviate_manager.create_db()
    assert weaviate_manager.database_created

    schema = requests.get(
        f"{weaviate_manager.connection_string()}/v1/schema",
        timeout=3,
    ).json()
    class_names = {item.get("class") for item in schema.get("classes", [])}
    assert "Test_collection" in class_names

    weaviate_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_weaviate_port")
def test_insert_and_fetch_object(weaviate_manager: WeaviateDB):
    weaviate_manager.create_db()
    base_url = weaviate_manager.connection_string()
    object_id = str(uuid.uuid4())

    create_response = requests.post(
        f"{base_url}/v1/objects",
        json={
            "class": "Test_collection",
            "id": object_id,
            "properties": {"text": "hello weaviate"},
        },
        timeout=5,
    )
    create_response.raise_for_status()

    get_response = requests.get(f"{base_url}/v1/objects/{object_id}", timeout=5)
    get_response.raise_for_status()
    payload = get_response.json().get("properties", {})
    assert payload.get("text") == "hello weaviate"

    weaviate_manager.delete_db(running_ok=True)


@pytest.mark.usefixtures("clear_weaviate_port")
def test_stop_and_restart(weaviate_manager: WeaviateDB):
    weaviate_manager.create_db()
    weaviate_manager.stop_db()
    assert weaviate_manager.state() in ("exited", "created")

    time.sleep(1)
    weaviate_manager.start_db()
    assert weaviate_manager.state() == "running"

    weaviate_manager.delete_db(running_ok=True)
