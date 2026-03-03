py-dockerdb
============

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

|Build| |PyPI| |License|

.. |Build| image:: https://img.shields.io/github/actions/workflow/status/amadou-6e/docker-db/cicd.yml?branch=main&label=tests
   :target: https://github.com/amadou-6e/docker-db/actions/workflows/cicd.yml
.. |PyPI| image:: https://img.shields.io/pypi/v/py-dockerdb
   :target: https://pypi.org/project/py-dockerdb/
.. |License| image:: https://img.shields.io/badge/license-MIT-lightgrey
   :target: ../LICENSE

``py-dockerdb`` gives you easy Docker database setup in Python for PostgreSQL, MySQL, MongoDB, Microsoft SQL Server, Redis, and Neo4j. It is built for people who teach, demo, and prototype with notebooks or scripts and need repeatable local databases in minutes. Instead of writing Docker commands and per-engine setup code, you use one API to create, start, connect, and clean up containers.

Switch from PostgreSQL to MongoDB and back without changing a line of connection code. This makes side-by-side database comparison a first-class workflow, useful for MVPs where the right engine is not decided yet, and for RAG and GraphRAG experiments where you want to test one storage backend, then swap it out without rewriting environment glue.

If you teach SQL or data workflows, it removes the environment setup section from your slides entirely: every student runs the same two lines and gets a working database.

Who Is This For
---------------

Python instructors and demo authors who need a classroom-ready, reproducible setup across machines and operating systems. The goal is to spend time teaching SQL, workflow design, and experimentation instead of debugging Docker setup in front of learners.

Learners and MVP builders who want to compare databases quickly with the same Pythonic workflow. You can test PostgreSQL, MySQL, MongoDB, MSSQL, Redis, and Neo4j under one lifecycle pattern and decide based on behavior instead of setup overhead.

RAG and AI prototype builders who need fast local backend swaps during iteration. This workflow supports testing one database option, then changing engines without rebuilding your orchestration from scratch. Neo4j support enables GraphRAG workflows — provision a knowledge graph container and run multi-hop queries with LlamaIndex or LangChain in the same lifecycle pattern.

What You Can Do With py-dockerdb
--------------------------------

For teaching and workshops, you can provision a real database container from a notebook, run seeded examples, and clean up at the end of class with the same script every learner can run. This keeps lesson flow focused on SQL and data concepts.

For MVP database comparison, you can run equivalent workflows against multiple engines and evaluate tradeoffs with less glue code. The same lifecycle methods reduce per-engine setup complexity during early product decisions.

For local RAG prototypes, you can start with one backing database, validate retrieval behavior, then switch to another engine without redesigning your setup process. This keeps experimentation fast when architecture is still changing.

Where To Go Next
----------------

.. toctree::
   :maxdepth: 1

   quick_start
   source/modules

- Usage notebooks:
  `db_management_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/db_management_example.ipynb>`_
  `postgres_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/postgres_example.ipynb>`_
  `mysql_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mysql_example.ipynb>`_
  `mongo_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mongo_example.ipynb>`_
  `mssql_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/mssql_example.ipynb>`_
  `redis_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/redis_example.ipynb>`_
  `neo4j_example.ipynb <https://github.com/amadou-6e/docker-db/blob/main/usage/neo4j_example.ipynb>`_
