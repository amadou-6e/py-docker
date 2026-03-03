Quickstart
==========

By the end of this page, you will have a running PostgreSQL container managed from Python, execute a query, and cleanly tear everything down.

Prerequisites
-------------

- Python 3.7+
- Docker installed and running
- Database drivers (installed automatically with package dependencies):
  - ``psycopg2-binary`` for PostgreSQL
  - ``mysql-connector-python`` for MySQL
  - ``pymongo`` for MongoDB
  - ``pyodbc`` for MSSQL

Installation
------------

.. code-block:: bash

   pip install py-dockerdb

Your First py-dockerdb Workflow
-------------------------------

This example uses the canonical README workflow for instructors, learners, and MVP builders: configure a database, create it, run a query, then clean up so your machine and class environment stay reproducible.

.. code-block:: python

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

The script provisions the containerized database, connects with the configured user, runs a real SQL query, prints the result, and removes the running container at the end.

What Just Happened
------------------

You used the core lifecycle pattern visible across the library: define a config object, call ``create_db()`` to provision and wait for readiness, use the connection for your workload, then call teardown (``delete_db(running_ok=True)`` in this example). This pattern keeps workshop and MVP environments reproducible because setup and cleanup are explicit in the same script.

Next Steps
----------

- `db_management_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/db_management_example.ipynb>`_:
  container lifecycle behavior and restart patterns.
- `postgres_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/postgres_example.ipynb>`_:
  PostgreSQL setup with SQL notebook flow and seeded data.
- `mysql_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mysql_example.ipynb>`_:
  MySQL setup and SQL workflow examples.
- `mongo_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mongo_example.ipynb>`_:
  MongoDB CRUD and collection examples.
- `mssql_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mssql_example.ipynb>`_:
  MSSQL setup and query workflow.
- `redis_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/redis_example.ipynb>`_:
  Redis key-value store and caching examples.
- `neo4j_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/neo4j_example.ipynb>`_:
  Neo4j knowledge graph setup, node/relationship queries, and GraphRAG with LlamaIndex.
- API reference: :doc:`source/modules`
