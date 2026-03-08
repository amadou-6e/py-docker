# MongoDB

MongoDB is a document-oriented NoSQL database. It stores data as JSON-like documents with dynamic schemas, making it a common choice for flexible data models and rapid prototyping. `py-dockerdb` uses the official `mongo:6` image.

## Install

```bash
pip install py-dockerdb[mongodb]
```

This installs `py-dockerdb` together with `pymongo`.

## Minimal example

```python
from docker_db import MongoDBConfig, MongoDB

config = MongoDBConfig(
    user="myuser",
    password="mypassword",
    database="mydb",
    root_username="admin",
    root_password="adminpassword",
)

db = MongoDB(config)
db.start_db()

client = db.connection         # pymongo.MongoClient
collection = client["mydb"]["documents"]
collection.insert_one({"title": "Hello", "body": "World"})
client.close()

db.stop_db()
```

Use as a context manager:

```python
with MongoDB(config) as db:
    client = db.connection
    doc = client["mydb"]["documents"].find_one({"title": "Hello"})
    print(doc)
```

## Connection details

| Item | Value |
|---|---|
| Protocol | TCP (MongoDB Wire Protocol) |
| Default port | `27017` |
| Connection string | `mongodb://user:password@127.0.0.1:27017/mydb?authSource=admin` |
| Python client | `pymongo.MongoClient` |

```python
url = db.connection_string()
# "mongodb://myuser:mypassword@127.0.0.1:27017/mydb?authSource=admin"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | required | Database user |
| `password` | `str` | required | Database user password |
| `database` | `str` | required | Default database name |
| `root_username` | `str` | required | MongoDB root (admin) username |
| `root_password` | `str` | required | MongoDB root (admin) password |
| `port` | `int` | `27017` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"mongo:6"` | Docker image |

## Notes

- MongoDB creates databases on demand. The `start_db()` call creates a user with `readWrite` access on the configured database; the database itself materialises when the first document is inserted.
- Two credentials are required: `root_username`/`root_password` are the superuser credentials used during provisioning; `user`/`password` are the application credentials you use at runtime.
- Authentication is scoped to `authSource=admin`.
