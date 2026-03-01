# py-dockerdb

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

[![Build](https://img.shields.io/github/actions/workflow/status/amadou-6e/docker-db/cicd.yml?branch=main&label=tests)](https://github.com/amadou-6e/docker-db/actions/workflows/cicd.yml)
[![PyPI](https://img.shields.io/pypi/v/py-dockerdb)](https://pypi.org/project/py-dockerdb/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

`py-dockerdb` gives you easy Docker database setup in Python for PostgreSQL, MySQL, MongoDB, and Microsoft SQL Server. It is built for people who teach, demo, and prototype with notebooks or scripts and need repeatable local databases in minutes. Instead of writing Docker commands and per-engine setup code, you use one API to create, start, connect, and clean up containers.

Switch from PostgreSQL to MongoDB and back without changing a line of connection code. This makes side-by-side database comparison a first-class workflow - useful for MVPs where the right engine isn't decided yet, and for RAG experiments where you want to test one storage backend, then swap it out without rewriting environment glue.

If you teach SQL or data workflows, it removes the environment-setup section from your slides entirely: every student runs the same two lines and gets a working database.

`py-dockerdb` is designed for instructors and demo authors who need classroom-ready environments that start consistently on student machines. The same workflow also supports learners and MVP builders who want to compare databases quickly, plus local RAG prototype builders who need to swap backends without reworking setup scripts. You focus on teaching, experimenting, and comparing outcomes while the library handles container lifecycle and connection setup.

## When to use this

- **Teaching a SQL workshop or notebook tutorial** - use easy docker database setup in Python so every learner starts from the same environment with minimal setup friction.
- **Comparing databases for an MVP** - run a quick mvp database comparison in python across PostgreSQL, MySQL, MongoDB, and MSSQL with one pythonic docker database management flow.
- **Building a local RAG prototype** - do local rag database setup python-first, then swap from a rag prototype postgres docker setup to rag prototype mongodb docker without changing your orchestration style.

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

For development:

```bash
python -m pip install -e ".[test]"
```

## Usage

If you are teaching, demoing, or doing an MVP database comparison in python, start with the same pattern for each engine: define config, `create_db()`, run your workload, then teardown.

### PostgreSQL notebook workflow

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

### MySQL notebook workflow

```python
import uuid
from pathlib import Path
from docker_db.dbs.mysql_db import MySQLConfig, MySQLDB

container_name = f"demo-mysql-{uuid.uuid4().hex[:8]}"
temp_dir = Path("tmp")
temp_dir.mkdir(exist_ok=True)

config = MySQLConfig(
    user="demouser",
    password="demopass",
    database="demodb",
    root_password="rootpass",
    project_name="demo",
    workdir=temp_dir,
    container_name=container_name,
    retries=20,
    delay=3,
)

db_manager = MySQLDB(config)
db_manager.create_db()

conn = db_manager.connection
cur = conn.cursor()
cur.execute("SELECT 1;")
print(cur.fetchone())

cur.close()
conn.close()
db_manager.delete_db(running_ok=True)
```

### MongoDB notebook workflow

```python
import uuid
from pathlib import Path
from docker_db.dbs.mongo_db import MongoDBConfig, MongoDB

container_name = f"demo-mongodb-{uuid.uuid4().hex[:8]}"
temp_dir = Path("tmp")
temp_dir.mkdir(exist_ok=True)

config = MongoDBConfig(
    user="demouser",
    password="demopass",
    database="demodb",
    root_username="admin",
    root_password="adminpass",
    project_name="demo",
    workdir=temp_dir,
    container_name=container_name,
    retries=20,
    delay=3,
)

db_manager = MongoDB(config)
db_manager.create_db()

client = db_manager.connection
db = client[config.database]
print(db.list_collection_names())

client.close()
db_manager.delete_db(running_ok=True)
```

### MSSQL notebook workflow

```python
import uuid
from pathlib import Path
from docker_db.dbs.mssql_db import MSSQLConfig, MSSQLDB

container_name = f"demo-mssql-{uuid.uuid4().hex[:8]}"
temp_dir = Path("tmp").absolute()
temp_dir.mkdir(exist_ok=True)

config = MSSQLConfig(
    user="demouser",
    host="127.0.0.1",
    password="Demo_Pass123",
    database="demodb",
    sa_password="StrongPass123!",
    project_name="demo",
    workdir=temp_dir,
    container_name=container_name,
    retries=20,
    delay=3,
)

db_manager = MSSQLDB(config)
db_manager.create_db()

conn = db_manager.connection
cur = conn.cursor()
cur.execute("SELECT @@VERSION")
print(cur.fetchone())

cur.close()
conn.close()
db_manager.delete_db(running_ok=True)
```

### Initialization scripts for seeded demos

Use `init_script` to preload tables or documents for lessons and live demos.

```python
from pathlib import Path
from docker_db.dbs.postgres_db import PostgresConfig

config = PostgresConfig(
    user="demouser",
    password="demopass",
    database="demodb",
    init_script=Path("./configs/postgres/initdb.sh"),
)
```

### SQL magic or client integration

Notebook examples include connection string helpers for SQL magic workflows.

```python
conn_string = db_manager.connection_string(sql_magic=True)
```

## Development

```bash
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
