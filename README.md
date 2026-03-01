# py-dockerdb

**Provision Docker databases in Python — one call, zero Docker CLI.**

[![PyPI version](https://img.shields.io/pypi/v/py-dockerdb)](https://pypi.org/project/py-dockerdb/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/py-dockerdb/)

```bash
pip install py-dockerdb
```

`py-dockerdb` manages Docker containers for databases through a single, unified Python API. Call `create_db()` to get a running container with a live connection object. Call `delete_db()` when you are done. No Dockerfiles to write, no ports to remember, no environment variables to juggle.

**Why this exists:** standing up a local Postgres, Neo4j, MongoDB, or MySQL instance for development and testing typically means writing Dockerfiles, debugging init scripts, and wiring connection strings by hand. `py-dockerdb` reduces that to two lines of Python so you can focus on the application logic.

---

## Supported Databases

| Class | Image | Default Port |
|---|---|---|
| `PostgresDB` | `postgres:16` | 5432 |
| `Neo4jDB` | `neo4j:5` | 7687 (Bolt) · 7474 (Browser) |
| `MongoDB` | `mongo:6` | 27017 |
| `MySQLDB` | `mysql:8` | 3306 |
| `MSSQLDB` | `mcr.microsoft.com/mssql/server:2022-latest` | 1433 |

---

## Installation

```bash
# Core
pip install py-dockerdb

# With graph dependencies (Neo4j driver, LlamaIndex / LangChain graph stores)
pip install "py-dockerdb[graph]"
```

---

## Common API

Every manager shares the same lifecycle methods:

```python
db.create_db()          # build image → start container → create database
db.connection           # native driver connection (psycopg2, pymongo, …)
db.connection_string()  # URI for framework integrations
db.stop_db()            # stop the container (data persists on volume)
db.start_db()           # restart a stopped container
db.restart_db()         # stop + start
db.delete_db()          # stop + remove container and image
db.state()              # container state dict
```

---

## Usage

### PostgreSQL

```python
from docker_db import PostgresDB, PostgresConfig

config = PostgresConfig(user="user", password="pass", database="mydb")
db = PostgresDB(config)
db.create_db()

conn = db.connection  # psycopg2 connection with RealDictCursor
```

### MongoDB

```python
from docker_db import MongoDB, MongoDBConfig

config = MongoDBConfig(
    user="user", password="pass", database="mydb",
    root_username="admin", root_password="adminpass",
)
db = MongoDB(config)
db.create_db()

client = db.connection  # pymongo MongoClient
```

### MySQL

```python
from docker_db import MySQLDB, MySQLConfig

config = MySQLConfig(user="user", password="pass", database="mydb", root_password="root")
db = MySQLDB(config)
db.create_db()
```

### MSSQL

```python
from docker_db import MSSQLDB, MSSQLConfig

config = MSSQLConfig(user="sa", password="StrongPass123!", database="mydb")
db = MSSQLDB(config)
db.create_db()
```

### Neo4j (GraphRAG)

Graph retrieval substantially improves answer quality on multi-hop, relationship-heavy
questions that dense-vector search alone cannot follow. `Neo4jDB.connection` returns a
`neo4j.Driver` that plugs directly into LlamaIndex's `Neo4jGraphStore` and LangChain's
`Neo4jGraph`.

```python
from docker_db import Neo4jDB, Neo4jConfig

config = Neo4jConfig(password="strongpass")
db = Neo4jDB(config)
db.create_db()

driver = db.connection          # neo4j.Driver — Bolt at db.connection_string()
# Neo4j Browser UI: http://localhost:7474
```

```python
# LlamaIndex
from llama_index.graph_stores.neo4j import Neo4jGraphStore
graph_store = Neo4jGraphStore(
    username=config.user, password=config.password,
    url=db.connection_string(), database=config.database,
)

# LangChain
from langchain_community.graphs import Neo4jGraph
graph = Neo4jGraph(url=db.connection_string(), username=config.user, password=config.password)
```

See [usage/neo4j_example.ipynb](usage/neo4j_example.ipynb) for the full walkthrough including multi-hop traversal and GraphRAG indexing.

### Initialization Scripts

All managers accept an `init_script` path mounted into the container entrypoint and executed on first startup:

```python
from pathlib import Path

config = PostgresConfig(
    user="user", password="pass", database="mydb",
    init_script=Path("./sql/schema.sql"),
)
```

### Custom Volumes and Network Mode

```python
config = PostgresConfig(
    user="user", password="pass", database="mydb",
    volume_path=Path("./data/pgdata"),
    network_mode="host",   # Linux only; falls back to bridge on Windows/macOS
)
```

---

## Requirements

- Python 3.10+
- Docker Desktop (or Docker Engine on Linux) running
- Platform: Linux, macOS, Windows

---

## License

MIT — see [LICENSE](LICENSE).
