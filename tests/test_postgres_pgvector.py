import uuid
from pathlib import Path

import docker
import pytest

from tests.conftest import CONFIG_DIR, TEST_DIR
from .utils import clear_port, nuke_dir
from docker_db.dbs.postgres_db import PostgresConfig, PostgresDB


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_pgvector_containers():
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker is not running; skipping pgvector integration tests.")
    pgdata_root = Path(TEST_DIR, "data", "pgvector")

    def _cleanup():
        for container in client.containers.list(all=True):
            if container.name.startswith("test-pgvector"):
                try:
                    container.stop(timeout=5)
                except docker.errors.APIError:
                    pass
                try:
                    container.remove(force=True)
                except docker.errors.APIError:
                    pass
        nuke_dir(pgdata_root)
        pgdata_root.mkdir(parents=True, exist_ok=True)

    _cleanup()
    yield
    _cleanup()


@pytest.fixture(scope="module")
def pgvector_manager() -> PostgresDB:
    clear_port(5432, "test-pgvector")

    name = f"test-pgvector-{uuid.uuid4().hex[:8]}"
    pgdata = Path(TEST_DIR, "data", "pgvector", name)
    pgdata.mkdir(parents=True, exist_ok=True)

    config = PostgresConfig(
        user="testuser",
        password="testpass",
        database="vector_db",
        project_name="itest",
        image_name=f"test-pgvector-image-{uuid.uuid4().hex[:8]}:latest",
        workdir=Path(CONFIG_DIR, "postgres"),
        volume_path=pgdata,
        dockerfile_path=Path(CONFIG_DIR, "postgres", "Dockerfile.pgvector"),
        init_script=Path(CONFIG_DIR, "postgres", "initdb_pgvector.sh"),
        container_name=name,
        retries=20,
        delay=3,
    )
    manager = PostgresDB(config=config)
    manager.create_db()
    yield manager
    try:
        manager.delete_db(running_ok=True)
    except Exception:
        pass


def test_pgvector_extension_is_available(pgvector_manager: PostgresDB):
    conn = pgvector_manager.connection
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            row = cur.fetchone()
            assert row is not None, "pgvector extension is not installed"
    finally:
        conn.close()


def test_pgvector_can_run_vector_similarity_query(pgvector_manager: PostgresDB):
    conn = pgvector_manager.connection
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_embeddings (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector(3) NOT NULL
                );
                """
            )
            cur.execute("TRUNCATE TABLE rag_embeddings;")
            cur.execute(
                """
                INSERT INTO rag_embeddings (content, embedding) VALUES
                    ('close_to_origin', '[0.05, 0.02, 0.00]'),
                    ('far_point', '[10.0, 10.0, 10.0]');
                """
            )
            cur.execute(
                """
                SELECT content
                FROM rag_embeddings
                ORDER BY embedding <-> '[0,0,0]'::vector
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            assert row is not None
            assert row["content"] == "close_to_origin"
    finally:
        conn.close()


def test_llamaindex_pgvector_store_from_params(pgvector_manager: PostgresDB):
    llama_postgres = pytest.importorskip("llama_index.vector_stores.postgres")
    PGVectorStore = llama_postgres.PGVectorStore

    vector_store = PGVectorStore.from_params(
        database=pgvector_manager.config.database,
        host=pgvector_manager.config.host,
        password=pgvector_manager.config.password,
        port=pgvector_manager.config.port,
        user=pgvector_manager.config.user,
        table_name="physics_docs",
        embed_dim=384,
        hybrid_search=True,
    )

    assert vector_store is not None
