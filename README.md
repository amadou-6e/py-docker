# Docker-DB

A Python library for managing containerized databases through Docker. This library provides a simple interface for creating, configuring, and managing database containers for development and testing environments, from within python.

## Features

The following features are supported:

- Easy setup and management of database containers
- Automated container lifecycle management
- Standardized configuration interfaces
- Connection management and health checking
- Volume persistence capabilities
- Initialization script support

The following features are implemented but not tested:
- Enable/Disable error if already created
- startdb
- restartdb
- init scripts to examples

The following databases are supported:
  - MongoDB
  - Microsoft SQL Server
  - PostgreSQL
  - MySQL
  - Ollama (local LLM runtime)

These databases might be added in the future:
- Cassandra

## Installation

```bash
pip install py-dockerdb
```

## Requirements

- Python 3.7+
- Docker installed and running
- Database-specific Python drivers:
  - `pymongo` for MongoDB
  - `pyodbc` for Microsoft SQL Server
  - `psycopg2` for PostgreSQL
  - `mysql-connector-python` for MySQL

## Basic Usage

Check out the following usage examples:

### MongoDB Example

```python
from docker_db.mongodb import MongoDBConfig, MongoDB

# Create configuration
config = MongoDBConfig(
    user="testuser",
    password="testpass",
    database="testdb",
    root_username="admin",
    root_password="adminpass",
    container_name="test-mongodb"
)

# Create and start MongoDB container
db = MongoDB(config)
db.create_db()

# Connect to database
client = db.connection
# Use the database...

# Stop the container when done
db.stop_db()

# Completely remove the container
db.delete_db()
```

### PostgreSQL Example

```python
from docker_db.postgres import PostgresConfig, PostgresDB

# Create configuration
config = PostgresConfig(
    user="testuser",
    password="testpass",
    database="testdb",
    container_name="test-postgres"
)

# Create and start PostgreSQL container
db = PostgresDB(config)
db.create_db()

# Connect to the database
conn = db.connection

# Create a cursor and execute a query
cursor = conn.cursor()
cursor.execute("SELECT version();")
version = cursor.fetchone()
print(f"PostgreSQL version: {version[0]}")

# Clean up
cursor.close()
db.stop_db()
```

### Working with Initialization Scripts

All database managers support initialization scripts that can be executed when the container is created:

```python
from pathlib import Path
from docker_db.mongodb import MongoDBConfig, MongoDB

config = MongoDBConfig(
    user="testuser",
    password="testpass",
    database="testdb",
    root_username="admin",
    root_password="adminpass",
    container_name="test-mongodb",
    init_script=Path("./path/to/init_script.js")
)
```

### Custom Volume Paths

You can specify custom volume paths to persist data between container restarts:

```python
from pathlib import Path
from docker_db.mssql import MSSQLConfig, MSSQLDB

config = MSSQLConfig(
    user="testuser",
    password="testpass",
    database="testdb",
    sa_password="StrongPassword123!",
    container_name="test-mssql",
    volume_path=Path("./data/mssql")
)
```

### Network Mode and Optional Port Mapping

You can now run containers with explicit Docker network settings and optionally skip host port publishing.

```python
from docker_db.postgres_db import PostgresConfig, PostgresDB

config = PostgresConfig(
    user="testuser",
    password="testpass",
    database="testdb",
    network_mode="host",  # Linux native host networking
    port=None,            # no host port mapping
)

db = PostgresDB(config)
db.create_db()
```

Notes:
- `network_mode="host"` works natively on Linux.
- On Windows/macOS, host mode falls back to bridge mode.
- If `port=None`, the manager skips host port mapping.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
