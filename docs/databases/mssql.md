# Microsoft SQL Server

Microsoft SQL Server (MSSQL) is an enterprise relational database engine. `py-dockerdb` provisions the Developer edition via the official `mcr.microsoft.com/mssql/server:2022-latest` image and connects through `pyodbc`.

## Install

```bash
pip install py-dockerdb[mssql]
```

This installs `py-dockerdb` together with `pyodbc`. You also need a host-level ODBC driver:

- **Windows**: ODBC Driver 17 or 18 for SQL Server (available from Microsoft).
- **macOS / Linux**: Install via `brew install msodbcsql18` or the Microsoft package repo.

The driver is resolved automatically at runtime — `MSSQLDB` checks for drivers 18, 17, and the legacy `SQL Server` driver in that order.

## Minimal example

```python
from docker_db import MSSQLConfig, MSSQLDB

config = MSSQLConfig(
    user="myuser",
    password="MyPassword123!",
    database="mydb",
    sa_password="StrongSAPassword1!",
)

db = MSSQLDB(config)
db.start_db()

conn = db.connection           # pyodbc.Connection
cursor = conn.cursor()
cursor.execute("SELECT @@VERSION")
print(cursor.fetchone()[0])
cursor.close()
conn.close()

db.stop_db()
```

Use as a context manager:

```python
with MSSQLDB(config) as db:
    conn = db.connection
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sys.databases")
    print([row[0] for row in cursor.fetchall()])
```

## Connection details

| Item | Value |
|---|---|
| Protocol | TDS over TCP |
| Default port | `1433` |
| Python client | `pyodbc.Connection` |

```python
# Standard pyodbc connection string:
cs = db.connection_string()
# "DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;UID=myuser;PWD=...;"

# For Jupyter %sql magic (SQLAlchemy URL):
cs = db.connection_string(sql_magic=True)
# "mssql+pyodbc://myuser:MyPassword123!@127.0.0.1:1433/mydb?driver=ODBC+Driver+18+for+SQL+Server&..."
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `user` | `str` | required | SQL Server login name |
| `password` | `str` | required | Login password |
| `database` | `str` | required | Database to create |
| `sa_password` | `str` | required | System administrator (`sa`) password |
| `port` | `int` | `1433` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"mcr.microsoft.com/mssql/server:2022-latest"` | Docker image |

## Additional methods

### `_execute_sql_script(script_path, db_name)`

Execute a `.sql` file against a named database. The script is split on `GO` statements (the SQL Server batch separator) and each batch is executed individually.

```python
from pathlib import Path

with MSSQLDB(config) as db:
    db._execute_sql_script(Path("schema.sql"), db_name="mydb")
```

## Notes

- The `sa_password` must meet SQL Server complexity requirements (upper, lower, digit, special character, at least 8 characters).
- `TrustServerCertificate=yes` is added automatically for drivers 17/18 to avoid self-signed certificate errors in local development.
- On Linux, the bind-mounted volume directory is `chmod 777`'d to allow write access by the container's non-root SQL Server process.
- The Developer edition is free for development and testing; it must not be used in production.
