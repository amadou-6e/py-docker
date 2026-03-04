# py-dockerdb

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

[![Build](https://img.shields.io/github/actions/workflow/status/amadou-6e/docker-db/cicd.yml?branch=main&label=tests)](https://github.com/amadou-6e/docker-db/actions/workflows/cicd.yml)
[![PyPI](https://img.shields.io/pypi/v/py-dockerdb)](https://pypi.org/project/py-dockerdb/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://amadou-6e.github.io/py-docker/introduction.html)

```bash
pip install py-dockerdb
```

`py-dockerdb` gives you one Python API to create, connect, and clean up Docker
databases: PostgreSQL, MySQL, MongoDB, MSSQL, Redis, Neo4j, and Ollama. It is built
for people who teach, demo, and prototype with notebooks and need repeatable local
databases in seconds.

Switch from PostgreSQL to MongoDB without changing a line of connection code. Test
a pgvector RAG pipeline, then swap to Neo4j for GraphRAG with one config change.
Or hand every student a pre-seeded database at the start of class without touching
Docker on their machine.

## When to use this

- **Teaching a SQL workshop:** two lines give every learner a working, pre-seeded
  database, identical across Windows/Mac/Linux.
- **Comparing databases for an MVP:** run Postgres, MongoDB, Redis, and Neo4j
  through the same interface and pick based on behaviour, not setup time.
- **Local RAG prototype:** spin up pgvector, validate retrieval, swap to another
  backend in one config change without touching orchestration code.
- **GraphRAG with Neo4j:** `Neo4jDB.connection` returns a `neo4j.Driver` that
  plugs directly into LlamaIndex's `Neo4jGraphStore` and LangChain's `Neo4jGraph`.

## Supported Databases

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/docs/)
[![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)](https://dev.mysql.com/doc/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/docs/)
[![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?logo=microsoftsqlserver&logoColor=white)](https://learn.microsoft.com/en-us/sql/sql-server/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)](https://redis.io/docs/)
[![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?logo=neo4j&logoColor=white)](https://neo4j.com/docs/)
[![Ollama](https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white)](https://ollama.com/library)

## Prerequisites

- Python 3.10+ · Docker running

## Installation

```bash
pip install py-dockerdb                # core
pip install "py-dockerdb[graph]"       # + Neo4j / LlamaIndex / LangChain
pip install "py-dockerdb[rag]"         # + pgvector / LlamaIndex
```

## Usage

Define a config, call `create_db()`, run your workload, tear down with `delete_db()`.

### PostgreSQL

```python
from docker_db.dbs.postgres_db import PostgresConfig, PostgresDB

db = PostgresDB(PostgresConfig(user="u", password="p", database="d", project_name="demo"))
db.create_db()
conn = db.connection          # psycopg2 connection
cur = conn.cursor()
cur.execute("SELECT version();")
print(cur.fetchone())
db.delete_db(running_ok=True)
```


### Neo4j / GraphRAG

```python
from docker_db.dbs.neo4j_db import Neo4jConfig, Neo4jDB

db = Neo4jDB(Neo4jConfig(password="p", project_name="demo"))
db.create_db()
driver = db.connection        # neo4j.Driver -> hand to Neo4jGraphStore or Neo4jGraph
with driver.session() as s:
    s.run("CREATE (n:Person {name: 'Alice'})")
    print(s.run("MATCH (n:Person) RETURN n.name").single()[0])
db.delete_db(running_ok=True)
```

### Ollama

```python
from docker_db.dbs.ollama_db import OllamaConfig, OllamaDB

db = OllamaDB(OllamaConfig(project_name="demo"))
db.create_db()
session = db.connection       # requests.Session
db.pull_model("llama3")
resp = session.post(f"{db.base_url}/api/generate", json={"model": "llama3", "prompt": "Hello", "stream": False})
print(resp.json()["response"])
db.delete_db(running_ok=True)
```

### More examples

Full runnable notebooks are in [`usage/`](./usage/):

[PostgreSQL](./usage/postgres_example.ipynb) · [MySQL](./usage/mysql_example.ipynb)
· [MongoDB](./usage/mongo_example.ipynb) · [MSSQL](./usage/mssql_example.ipynb)
· [Redis](./usage/redis_example.ipynb) · [Neo4j / GraphRAG](./usage/neo4j_example.ipynb)
· [pgvector RAG](./usage/pgvector_rag_example.ipynb) · [Lifecycle](./usage/db_management_example.ipynb)

## Roadmap

- [x] PostgreSQL + `pgvector`
- [x] Neo4j
- [x] Qdrant
- [ ] Chroma
- [ ] Weaviate
- [ ] Milvus

## Development

```bash
git clone https://github.com/amadou-6e/docker-db.git
cd docker-db
pip install -e ".[test]"
```

## Testing

```bash
python -m pytest -vv -s tests/test_manager.py
python -m pytest -vv -s tests/test_postgres.py
python -m pytest -vv -s tests/test_postgres_pgvector.py
python -m pytest -vv -s tests/test_mysql.py
python -m pytest -vv -s tests/test_mongodb.py
python -m pytest -vv -s tests/test_mssql.py
python -m pytest -vv -s tests/test_redis.py
python -m pytest -vv -s tests/test_cassandra.py
python -m pytest -vv -s tests/test_neo4j.py
python -m pytest -vv -s tests/test_opensearch.py
python -m pytest -vv -s tests/test_qdrant.py
python -m pytest -vv -s tests/test_ollama.py
python -m pytest -vv -s tests/test_notebooks.py
```

## Contributing

PRs welcome. Include tests for behaviour changes and keep notebooks runnable.

## License

MIT License. See `LICENSE`.
