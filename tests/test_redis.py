import time
import uuid
from pathlib import Path

import docker
import pytest
from docker.models.containers import Container

from tests.conftest import *
from docker_db.dbs.redis_db import RedisConfig, RedisDB
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
            if container.name.startswith("test-redis"):
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
def clear_port_6379():
    clear_port(6379, "test-redis")


@pytest.fixture
def redis_config() -> RedisConfig:
    name = f"test-redis-{uuid.uuid4().hex[:8]}"
    redisdata = Path(TEST_DIR, "data", "redisdata", name)
    redisdata.mkdir(parents=True, exist_ok=True)

    return RedisConfig(
        database=1,
        project_name="itest",
        volume_path=redisdata,
        container_name=name,
        retries=20,
        delay=2,
    )


@pytest.fixture
def redis_manager(redis_config: RedisConfig):
    """
    Redis manager.

    Parameters
    ----------
    redis_config : Any
        Configuration fixture.
    """
    manager = RedisDB(redis_config)
    yield manager


@pytest.mark.usefixtures("clear_port_6379")
def test_create_db_and_connection(redis_config: RedisConfig, redis_manager: RedisDB):
    """
    Test create db and connection.

    Parameters
    ----------
    redis_config : Any
        Configuration fixture.
    redis_manager : Any
        Database manager fixture.
    """
    container = redis_manager.create_db()
    assert isinstance(container, Container)

    conn = redis_manager.connection
    conn.set("hello", "world")
    assert conn.get("hello") == "world"
    assert conn.ping() is True


@pytest.mark.usefixtures("clear_port_6379")
def test_stop_db(redis_config: RedisConfig, redis_manager: RedisDB):
    """
    Test stop db.

    Parameters
    ----------
    redis_config : Any
        Configuration fixture.
    redis_manager : Any
        Database manager fixture.
    """
    redis_manager.create_db()
    time.sleep(1)
    redis_manager.stop_db()

    client = docker.from_env()
    conts = client.containers.list(all=True, filters={"name": redis_config.container_name})
    assert len(conts) == 1
    assert conts[0].status in ("exited", "created")


@pytest.mark.usefixtures("clear_port_6379")
def test_delete_db(redis_config: RedisConfig, redis_manager: RedisDB):
    """
    Test delete db.

    Parameters
    ----------
    redis_config : Any
        Configuration fixture.
    redis_manager : Any
        Database manager fixture.
    """
    redis_manager.create_db()
    with pytest.raises(RuntimeError, match="still running"):
        redis_manager.delete_db()

    redis_manager.delete_db(running_ok=True)
    client = docker.from_env()
    conts = client.containers.list(all=True, filters={"name": redis_config.container_name})
    assert len(conts) == 0
