import time
import uuid
from pathlib import Path

import docker
import pytest
import requests
from docker.models.containers import Container

from docker_db.dbs.ollama_db import OllamaConfig, OllamaDB
from tests.conftest import *
from .utils import clear_port, nuke_dir


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
            if container.name.startswith("test-ollama"):
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
def clear_port_11434():
    clear_port(11434, "test-ollama")


@pytest.fixture
def ollama_config() -> OllamaConfig:
    name = f"test-ollama-{uuid.uuid4().hex[:8]}"
    ollama_data = Path(TEST_DIR, "data", "ollamadata", name)
    ollama_data.mkdir(parents=True, exist_ok=True)

    return OllamaConfig(
        project_name="itest",
        volume_path=ollama_data,
        container_name=name,
        retries=30,
        delay=2,
    )


@pytest.fixture
def ollama_manager(ollama_config: OllamaConfig):
    manager = OllamaDB(ollama_config)
    yield manager


@pytest.mark.usefixtures("clear_port_11434")
def test_create_db_and_connection(ollama_manager: OllamaDB):
    container = ollama_manager.create_db()
    assert isinstance(container, Container)

    response = requests.get(f"{ollama_manager.base_url}/api/tags", timeout=10)
    assert response.status_code == 200
    assert "models" in response.json()


@pytest.mark.usefixtures("clear_port_11434")
def test_stop_db(ollama_config: OllamaConfig, ollama_manager: OllamaDB):
    ollama_manager.create_db()
    time.sleep(1)
    ollama_manager.stop_db()

    client = docker.from_env()
    containers = client.containers.list(all=True, filters={"name": ollama_config.container_name})
    assert len(containers) == 1
    assert containers[0].status in ("exited", "created")


@pytest.mark.usefixtures("clear_port_11434")
def test_delete_db(ollama_config: OllamaConfig, ollama_manager: OllamaDB):
    ollama_manager.create_db()
    with pytest.raises(RuntimeError, match="still running"):
        ollama_manager.delete_db()

    ollama_manager.delete_db(running_ok=True)
    client = docker.from_env()
    containers = client.containers.list(all=True, filters={"name": ollama_config.container_name})
    assert len(containers) == 0
