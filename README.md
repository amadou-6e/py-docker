# py-dockerdb

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

[![Build](https://img.shields.io/github/actions/workflow/status/amadou-6e/docker-db/cicd.yml?branch=main&label=tests)](https://github.com/amadou-6e/docker-db/actions/workflows/cicd.yml)
[![PyPI](https://img.shields.io/pypi/v/py-dockerdb)](https://pypi.org/project/py-dockerdb/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

`py-dockerdb` gives you easy Docker database setup in Python for PostgreSQL, MySQL, MongoDB, and Microsoft SQL Server. It is built for people who teach, demo, and prototype with notebooks or scripts and need repeatable local databases in minutes. Instead of writing Docker commands and per-engine setup code, you use one API to create, start, connect, and clean up containers.

Switch from PostgreSQL to MongoDB and back without changing a line of connection code. This makes side-by-side database comparison a first-class workflow - useful for MVPs where the right engine isn't decided yet, and for RAG experiments where you want to test one storage backend, then swap it out without rewriting environment glue.

If you teach SQL or data workflows, it removes the environment-setup section from your slides entirely: every student runs the same two lines and gets a working database.

## When to use this

- **Teaching a SQL workshop or notebook tutorial** - every learner starts from the same environment with no per-machine Docker setup required.
- **Comparing databases for an MVP** - run PostgreSQL, MySQL, MongoDB, and MSSQL under the same Python interface and switch engines without rewriting connection code.
- **Building a local RAG prototype** - spin up a backing store, test your retrieval pipeline, then swap from PostgreSQL to MongoDB in one config change without touching orchestration code.

## Supported Databases

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/docs/)
[![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)](https://dev.mysql.com/doc/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/docs/)
[![SQL Server](https://img.shields.io/badge/SQL_Server-CC2927?logo=microsoftsqlserver&logoColor=white)](https://learn.microsoft.com/en-us/sql/sql-server/)

## Prerequisites

- Python 3.7+
- Docker installed and running
- Database drivers (installed automatically with package dependencies):
  - `psycopg2-binary` for PostgreSQL
  - `mysql-connector-python` for MySQL
  - `pymongo` for MongoDB
  - `pyodbc` for MSSQL

## Installation

```bash
pip install py-dockerdb
```

## Usage

The API is consistent across all four engines: define a config, call `create_db()`, run your workload, then tear down with `delete_db()`.

### PostgreSQL example

```python
import uuid
from pathlib import Path
from docker_db.dbs.postgres_db import PostgresConfig, PostgresDB

container_name = f"demo-postgres-{uuid.uuid4().hex[:8]}"
temp_dir = Path("tmp")
temp_dir.mkdir(exist_ok=True)

config = PostgresConfig(
    user="demouser",
    password="demopass",
    database="demodb",
    project_name="demo",
    container_name=container_name,
    workdir=temp_dir.absolute(),
    retries=20,
    delay=3,
)

db_manager = PostgresDB(config)
db_manager.create_db()

conn = db_manager.connection
cur = conn.cursor()
cur.execute("SELECT version();")
print(cur.fetchone())

cur.close()
conn.close()
db_manager.delete_db(running_ok=True)
```

### More examples

Full runnable notebooks for each engine are in the [`usage/`](./usage/) directory:

- [PostgreSQL](./usage/postgres_example.ipynb)
- [MySQL](./usage/mysql_example.ipynb)
- [MongoDB](./usage/mongo_example.ipynb)
- [MSSQL](./usage/mssql_example.ipynb)
- [Container lifecycle and management](./usage/db_management_example.ipynb)

### Seeding data for demos and workshops

Use `init_script` to preload tables or documents before handing the environment to students or running a live demo.

```python
config = PostgresConfig(
    ...
    init_script=Path("./configs/postgres/initdb.sh"),
)
```

### SQL magic and client tool integration

```python
conn_string = db_manager.connection_string(sql_magic=True)
```

## Development

```bash
git clone https://github.com/amadou-6e/docker-db.git
cd docker-db
python -m pip install -e ".[test]"
```

## Testing

```bash
python -m pytest -vv -s tests/test_manager.py
python -m pytest -vv -s tests/test_postgres.py
python -m pytest -vv -s tests/test_mysql.py
python -m pytest -vv -s tests/test_mongodb.py
python -m pytest -vv -s tests/test_mssql.py
python -m pytest -vv -s tests/test_notebooks.py
```

## Contributing

Pull requests are welcome. Please include tests for behavior changes and keep examples runnable in the `usage/` notebooks when applicable.

## License

MIT License. See `LICENSE`.