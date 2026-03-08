# Redis

Redis is an in-memory data structure store used as a cache, message broker, and database. It supports strings, hashes, lists, sets, sorted sets, and more. `py-dockerdb` uses the official `redis:7` image.

## Install

```bash
pip install py-dockerdb[redis]
```

This installs `py-dockerdb` together with `redis` (redis-py).

## Minimal example

```python
from docker_db import RedisConfig, RedisDB

config = RedisConfig(
    database=0,    # logical database index (0–15)
)

db = RedisDB(config)
db.start_db()

r = db.connection              # redis.Redis
r.set("key", "value")
print(r.get("key"))            # b"value"

db.stop_db()
```

Use as a context manager:

```python
with RedisDB(config) as db:
    r = db.connection
    r.lpush("mylist", "a", "b", "c")
    print(r.lrange("mylist", 0, -1))
```

## Connection details

| Item | Value |
|---|---|
| Protocol | TCP (RESP) |
| Default port | `6379` |
| Connection string | `redis://127.0.0.1:6379/0` |
| Python client | `redis.Redis` |

```python
url = db.connection_string()        # "redis://127.0.0.1:6379/0"
url = db.connection_string(db_name=1)  # "redis://127.0.0.1:6379/1"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `database` | `int` | `0` | Logical database index (0–15) |
| `port` | `int` | `6379` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"redis:7"` | Docker image |

## Notes

- The `database` field is an integer index (0–15), not a name. Redis logical databases are isolated key spaces within the same server process — no explicit creation is needed.
- `db.connection` returns a `redis.Redis` instance with `decode_responses=True`, so string values are returned as `str` rather than `bytes`.
- Redis data is persisted to the `volume_path` bind mount, so keys survive container restarts.
