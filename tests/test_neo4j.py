import uuid
import docker
import pytest
from pathlib import Path
from tests.conftest import *
from docker_db.dbs.neo4j_db import Neo4jConfig, Neo4jDB
from .utils import nuke_dir, clear_port


# =======================================
#                 Fixtures
# =======================================

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
            if container.name.startswith("test-neo4j"):
                try:
                    container.stop()
                    container.remove()
                except Exception:
                    pass

    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def container_name():
    return f"test-neo4j-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def neo4j_config(container_name):
    return Neo4jConfig(
        password="testpassword",
        project_name="test",
        container_name=container_name,
        workdir=TEMP_DIR,
        volume_path=Path(TEMP_DIR, "n4jdata"),
        retries=20,
        delay=3,
    )


@pytest.fixture
def neo4j_manager(neo4j_config):
    return Neo4jDB(neo4j_config)


# =======================================
#                 Tests
# =======================================

@pytest.mark.timeout(180)
def test_create_db(neo4j_manager):
    neo4j_manager.create_db()
    assert neo4j_manager.database_created

    driver = neo4j_manager.connection
    with driver.session(database=neo4j_manager.config.database) as session:
        result = session.run("RETURN 1 AS n")
        record = result.single()
        assert record["n"] == 1
    driver.close()

    neo4j_manager.delete_db(running_ok=True)


@pytest.mark.timeout(180)
def test_connection_string(neo4j_manager):
    assert neo4j_manager.connection_string() == (
        f"bolt://{neo4j_manager.config.host}:{neo4j_manager.config.port}"
    )


@pytest.mark.timeout(180)
def test_write_and_read_node(neo4j_manager):
    neo4j_manager.create_db()

    driver = neo4j_manager.connection
    with driver.session(database=neo4j_manager.config.database) as session:
        session.run("CREATE (n:Person {name: $name, age: $age})", name="Alice", age=30)
        result = session.run("MATCH (n:Person {name: $name}) RETURN n.age AS age", name="Alice")
        record = result.single()
        assert record["age"] == 30
    driver.close()

    neo4j_manager.delete_db(running_ok=True)


@pytest.mark.timeout(180)
def test_relationship_traversal(neo4j_manager):
    neo4j_manager.create_db()

    driver = neo4j_manager.connection
    with driver.session(database=neo4j_manager.config.database) as session:
        session.run(
            "CREATE (a:Person {name: 'Alice'})-[:KNOWS]->(b:Person {name: 'Bob'})"
        )
        result = session.run(
            "MATCH (a:Person {name: 'Alice'})-[:KNOWS]->(b) RETURN b.name AS name"
        )
        record = result.single()
        assert record["name"] == "Bob"
    driver.close()

    neo4j_manager.delete_db(running_ok=True)


@pytest.mark.timeout(60)
def test_stop_and_start(neo4j_manager):
    neo4j_manager.create_db()
    neo4j_manager.stop_db()
    assert neo4j_manager.state()["Status"] == "exited"
    neo4j_manager.start_db()
    assert neo4j_manager.state()["Status"] == "running"
    neo4j_manager.delete_db(running_ok=True)
