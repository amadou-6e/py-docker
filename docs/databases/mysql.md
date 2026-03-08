# MySQL

MySQL is the world's most popular open-source relational database. It is a common choice for web applications, data warehouses, and analytics. `py-dockerdb` uses the official `mysql:8` image.

## Install

```bash
pip install py-dockerdb[mysql]
```

This installs `py-dockerdb` together with `mysql-connector-python`.

## Minimal example

```python
from docker_db import MySQLConfig, MySQLDB

config = MySQLConfig(
    user="myuser",
    password="mypassword",
    database="mydb",
    root_password="rootpassword",
)

db = MySQLDB(config)
db.start_db()

conn = db.connection           # mysql.connector.connection.MySQLConnection
cursor = conn.cursor()
cursor.execute("SELECT VERSION()")
print(cursor.fetchone())
cursor.close()
conn.close()

db.stop_db()
```

Use as a context manager:

```python
with MySQLDB(config) as db:
    conn = db.connection
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    print(cursor.fetchall())
```

## Connection details

| Item | Value |
|---|---|
| Protocol | TCP |
| Default port | `3306` |
| Connection string | `mysql://user:password@127.0.0.1:3306/mydb` |
| Python client | `mysql.connector.connection.MySQLConnection` |

```python
url = db.connection_string()
# "mysql://myuser:mypassword@127.0.0.1:3306/mydb"

# For Jupyter %sql magic (uses pymysql dialect):
url = db.connection_string(sql_magic=True)
# "mysql+pymysql://myuser:mypassword@127.0.0.1:3306/mydb"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | required | Database username |
| `password` | `str` | required | Database user password |
| `database` | `str` | required | Database name to create |
| `root_password` | `str` | required | MySQL root user password |
| `port` | `int` | `3306` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"mysql:8"` | Docker image |

## Notes

- Two passwords are required: `root_password` is used internally during provisioning; `password` is the application credential used at runtime.
- The `start_db()` call creates the database, grants `ALL PRIVILEGES` on it to `user`, and waits until the health check passes.
- If `host` is `"localhost"`, the driver rewrites it to `"127.0.0.1"` internally to avoid Unix socket resolution on some platforms.
