# PostgreSQL

PostgreSQL is a full-featured open-source relational database. With the `pgvector` extension it also serves as a vector store for RAG pipelines. `py-dockerdb` uses the official `postgres:16` image.

## Install

```bash
pip install py-dockerdb[postgres]
```

This installs `py-dockerdb` together with `psycopg2-binary` and `pgvector`.

## Minimal example

```python
from docker_db import PostgresConfig, PostgresDB

config = PostgresConfig(
    user="myuser",
    password="mypassword",
    database="mydb",
)

db = PostgresDB(config)
db.start_db()

conn = db.connection           # psycopg2 connection with RealDictCursor
with conn.cursor() as cur:
    cur.execute("SELECT version();")
    print(cur.fetchone()["version"])
conn.close()

db.stop_db()
```

Use as a context manager:

```python
with PostgresDB(config) as db:
    conn = db.connection
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
```

## Connection details

| Item | Value |
|---|---|
| Protocol | TCP |
| Default port | `5432` |
| Connection string | `postgresql://user:password@127.0.0.1:5432/mydb` |
| Python client | `psycopg2.extensions.connection` |

```python
url = db.connection_string()
# "postgresql://myuser:mypassword@127.0.0.1:5432/mydb"

# For Jupyter %sql magic:
url = db.connection_string(sql_magic=True)
# "postgresql://myuser:mypassword@127.0.0.1:5432/mydb"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | required | PostgreSQL username |
| `password` | `str` | required | PostgreSQL password |
| `database` | `str` | required | Database name to create |
| `port` | `int` | `5432` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `init_script` | `Path` | `None` | Path to an SQL init script |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"postgres:16"` | Docker image |

## Notes

- The `connection` property uses `RealDictCursor` by default, so rows are returned as dictionaries.
- If `init_script` is set, the script is mounted into the container's `/docker-entrypoint-initdb.d/` directory and executed on first start. The manager waits for the init objects to appear before returning.
- For pgvector usage, supply a custom `init_script` that runs `CREATE EXTENSION vector;` and point LlamaIndex's `PGVectorStore` at `db.connection_string()`.
