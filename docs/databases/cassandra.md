# Cassandra

Apache Cassandra is a distributed wide-column NoSQL database designed for high availability and linear horizontal scalability. It is a good fit for time-series data, event logs, and write-heavy workloads. `py-dockerdb` uses the official `cassandra:4` image.

## Install

```bash
pip install py-dockerdb[cassandra]
```

This installs `py-dockerdb` together with `cassandra-driver`.

> **Note:** `CassandraConfig` and `Cassandra` are not yet part of the top-level `docker_db` namespace. Import them directly from the submodule:
> ```python
> from docker_db.dbs.cassandra_db import CassandraConfig, Cassandra
> ```

## Minimal example

```python
from docker_db.dbs.cassandra_db import CassandraConfig, Cassandra

config = CassandraConfig(
    user="myuser",
    password="mypassword",
    keyspace="mykeyspace",
    root_username="cassandra",
    root_password="cassandra",
    port=9042,
)

db = Cassandra(config)
db.start_db()

cluster = db.connection        # cassandra.cluster.Cluster
session = cluster.connect("mykeyspace")
session.execute("CREATE TABLE IF NOT EXISTS events (id UUID PRIMARY KEY, name TEXT)")
cluster.shutdown()

db.stop_db()
```

## Connection details

| Item | Value |
|---|---|
| Protocol | CQL (native transport) |
| Default port | `9042` (must be set explicitly) |
| Python client | `cassandra.cluster.Cluster` |

`CassandraConfig` inherits `port` from the base class where the default is `None`. Always set `port=9042` explicitly:

```python
config = CassandraConfig(..., port=9042)
```

`db.connection` returns a `Cluster` object. Call `.connect(keyspace)` on it to open a `Session`.

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | required | Application username |
| `password` | `str` | required | Application user password |
| `keyspace` | `str` | required | Keyspace to create (equivalent to a database) |
| `root_username` | `str` | required | Cassandra superuser username (default image: `cassandra`) |
| `root_password` | `str` | required | Cassandra superuser password (default image: `cassandra`) |
| `port` | `int` | `None` | CQL native transport port — set to `9042` |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `image_name` | `str` | `"cassandra:4"` | Docker image |

## Notes

- **Cassandra starts slowly.** The `start_db()` call adds a fixed 10-second wait after the container reports `Running`, then polls for a successful CQL connection. Expect startup to take 30–60 seconds on first run.
- The keyspace is created with `SimpleStrategy` and `replication_factor=1`, which is appropriate for single-node local development.
- Two credential pairs are required: `root_username`/`root_password` are the superuser credentials used during provisioning (matching the image defaults); `user`/`password` are the application credentials granted access to the keyspace.
- There is no built-in `connection_string()` method. Use `db.connection` to get the `Cluster` object and call `.connect()` on it directly.
