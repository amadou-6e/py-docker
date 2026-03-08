# OpenSearch

OpenSearch is an open-source distributed search and analytics engine (Apache Lucene-based, forked from Elasticsearch). It supports full-text search, vector search (k-NN), and hybrid retrieval. `py-dockerdb` uses `opensearchproject/opensearch:2.13.0` with security disabled for local development.

## Install

```bash
pip install py-dockerdb[opensearch]
```

This installs `py-dockerdb` together with `opensearch-py`.

## Minimal example

```python
from docker_db import OpenSearchConfig, OpenSearchDB

config = OpenSearchConfig(
    database="my_index",
)

db = OpenSearchDB(config)
db.start_db()

client = db.connection         # opensearchpy.OpenSearch
print(client.info())

db.stop_db()
```

Use as a context manager:

```python
with OpenSearchDB(config) as db:
    client = db.connection
    if not client.indices.exists(index="my_index"):
        client.indices.create(index="my_index")
```

## Connection details

| Item | Value |
|---|---|
| Protocol | HTTP |
| Default port | `9200` |
| Connection string | `http://127.0.0.1:9200` |
| Python client | `opensearchpy.OpenSearch` |

```python
url = db.connection_string()   # "http://127.0.0.1:9200"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `database` | `str` | `"documents"` | Default index name |
| `port` | `int` | `9200` | HTTP API port |
| `use_bind_mount` | `bool` | `False` | Mount `volume_path` to persist index data |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"opensearchproject/opensearch:2.13.0"` | Docker image |

## Notes

- **`use_bind_mount=False` by default.** OpenSearch runs as a non-root user and the bind-mounted directory requires matching host permissions. Disable the bind mount (default) for CI or ephemeral local sessions; enable it only when you need data to survive container restarts.
- The container starts with security disabled (`DISABLE_SECURITY_PLUGIN=true`) and no authentication. Do not use this configuration in production.
- The image is approximately 1 GB. First pull will take time on a slow connection.
- The `start_db()` call waits for cluster health to reach at least `yellow` before returning.
