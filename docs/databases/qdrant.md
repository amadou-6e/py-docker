# Qdrant

Qdrant is a high-performance vector database written in Rust. It is commonly used as the retrieval backend in RAG pipelines. `py-dockerdb` uses the official `qdrant/qdrant:v1.9.5` image and creates a default collection on startup.

## Install

```bash
pip install py-dockerdb[qdrant]
```

This installs `py-dockerdb` together with `qdrant-client`.

## Minimal example

```python
from docker_db import QdrantConfig, QdrantDB

config = QdrantConfig(
    database="my_collection",
    vector_size=1536,           # match your embedding model's output size
)

db = QdrantDB(config)
db.start_db()

client = db.connection         # qdrant_client.QdrantClient
print(client.get_collections())

db.stop_db()
```

Use as a context manager:

```python
with QdrantDB(config) as db:
    client = db.connection
    collections = client.get_collections().collections
    print([c.name for c in collections])
```

## Connection details

| Item | Value |
|---|---|
| Protocol | HTTP REST |
| Default port | `6333` |
| Connection string | `http://127.0.0.1:6333` |
| Python client | `qdrant_client.QdrantClient` |

```python
url = db.connection_string()   # "http://127.0.0.1:6333"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `database` | `str` | `"documents"` | Default collection name |
| `port` | `int` | `6333` | HTTP API port |
| `vector_size` | `int` | `384` | Vector size for the default collection |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"qdrant/qdrant:v1.9.5"` | Docker image |

## Notes

- The `database` field names the Qdrant collection that is created automatically when `start_db()` runs. If the collection already exists, it is left unchanged.
- Set `vector_size` to match your embedding model. Common values: `384` (all-MiniLM-L6-v2), `768` (mpnet), `1536` (OpenAI text-embedding-ada-002), `3072` (text-embedding-3-large).
- Distance metric is fixed to `COSINE` by default.
