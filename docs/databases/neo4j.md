# Neo4j

Neo4j is a native graph database. It stores data as nodes, relationships, and properties, making it the preferred backend for GraphRAG pipelines where multi-hop traversals across entity relationships matter. LlamaIndex and LangChain both ship first-class Neo4j integrations.

## Install

```bash
pip install py-dockerdb[neo4j]
```

This installs `py-dockerdb` together with the `neo4j` Python driver.

## Minimal example

```python
from docker_db import Neo4jConfig, Neo4jDB

config = Neo4jConfig(
    password="password123",
)

db = Neo4jDB(config)
db.start_db()

driver = db.connection          # neo4j.Driver via Bolt
with driver.session() as session:
    session.run("CREATE (n:Person {name: 'Alice'})")
driver.close()

db.stop_db()
```

Use as a context manager to guarantee cleanup:

```python
with Neo4jDB(config) as db:
    driver = db.connection
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        print(result.single()["total"])
```

## Connection details

| Item | Value |
|---|---|
| Protocol | Bolt |
| Default Bolt port | `7687` |
| Default HTTP port | `7474` (Neo4j Browser) |
| Connection string | `bolt://127.0.0.1:7687` |
| Python client | `neo4j.Driver` |

```python
url = db.connection_string()   # "bolt://127.0.0.1:7687"
```

The HTTP port serves the Neo4j Browser UI. The Bolt port is the one used by all Python drivers and LlamaIndex/LangChain connectors.

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | `"neo4j"` | Neo4j username |
| `password` | `str` | required | Neo4j password (minimum 8 characters) |
| `database` | `str` | `"neo4j"` | Database name |
| `port` | `int` | `7687` | Bolt protocol port |
| `http_port` | `int` | `7474` | HTTP / Neo4j Browser port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"neo4j:5"` | Docker image |

## Notes

- Neo4j starts slowly. The default `retries=10` / `delay=3` gives a 30-second window; increase if your machine is slow.
- The password must be at least 8 characters.
- For LlamaIndex GraphRAG, pass `db.connection_string()` as the `url` argument and `config.user`/`config.password` as credentials to `Neo4jGraphStore`.
