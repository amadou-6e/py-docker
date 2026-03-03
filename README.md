# py-dockerdb

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

[![Build](https://img.shields.io/github/actions/workflow/status/amadou-6e/docker-db/cicd.yml?branch=main&label=tests)](https://github.com/amadou-6e/docker-db/actions/workflows/cicd.yml)
[![PyPI](https://img.shields.io/pypi/v/py-dockerdb)](https://pypi.org/project/py-dockerdb/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

`py-dockerdb` gives you easy Docker database setup in Python for PostgreSQL, MySQL, MongoDB, Microsoft SQL Server, Redis, Cassandra, Neo4j, OpenSearch, Qdrant, and Ollama. It is built for people who teach, demo, and prototype with notebooks or scripts and need repeatable local databases in minutes.

## When to use this

- **Teaching workshops**: every learner starts from the same environment.
- **Comparing databases for an MVP**: switch backends with minimal code changes.
- **Local RAG / GraphRAG prototyping**: run vector and graph backends locally.
- **Local LLM experiments**: use Ollama in Docker for model-serving workflows.

## Supported Databases

- PostgreSQL
- MySQL
- MongoDB
- Microsoft SQL Server
- Redis
- Cassandra
- Neo4j
- OpenSearch
- Qdrant
- Ollama

## Prerequisites

- Python 3.10+
- Docker installed and running

## Installation

```bash
# Core
pip install py-dockerdb

# Graph/RAG extras
pip install "py-dockerdb[graph,rag]"
```

## Usage

The API is consistent across engines: define a config, call `create_db()`, run your workload, then tear down with `delete_db()`.

See runnable notebooks in [`usage/`](./usage/):

- `postgres_example.ipynb`
- `mysql_example.ipynb`
- `mongo_example.ipynb`
- `mssql_example.ipynb`
- `redis_example.ipynb`
- `neo4j_example.ipynb`
- `ollama_example.ipynb`

## Roadmap

- [x] PostgreSQL + `pgvector`
- [x] Neo4j
- [x] Qdrant
- [ ] Chroma
- [ ] Weaviate
- [ ] Milvus

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
python -m pytest -vv -s tests/test_postgres_pgvector.py
python -m pytest -vv -s tests/test_mysql.py
python -m pytest -vv -s tests/test_mongodb.py
python -m pytest -vv -s tests/test_mssql.py
python -m pytest -vv -s tests/test_redis.py
python -m pytest -vv -s tests/test_cassandra.py
python -m pytest -vv -s tests/test_neo4j.py
python -m pytest -vv -s tests/test_opensearch.py
python -m pytest -vv -s tests/test_qdrant.py
python -m pytest -vv -s tests/test_ollama.py
python -m pytest -vv -s tests/test_notebooks.py
```

## Contributing

Pull requests are welcome. Please include tests for behavior changes and keep examples runnable in `usage/` notebooks when applicable.

## License

MIT License. See `LICENSE`.
