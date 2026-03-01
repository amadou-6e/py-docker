# py-dockerdb — AI Narrative Arc Plan

> **Core thesis**: Every serious AI application needs infrastructure. That infrastructure is painful to set up. py-dockerdb makes it a one-liner — locally, reproducibly, in Python.

---

## The Narrative Arc

```
[Foundation]         [Vector Layer]        [Knowledge Layer]     [Inference Layer]
Postgres/MySQL  →→   pgvector / Redis   →→   Neo4j (GraphRAG)  →→  Ollama / LocalAI
MongoDB/MSSQL        Redis Stack            Elasticsearch              ↑
                          ↓                                    [Streaming Layer]
                    [Observability]                              Kafka / Redis Streams
                    TimescaleDB / InfluxDB
```

The library becomes the answer to: *"I just want to experiment with [hot AI pattern] without fighting Docker"*

---

## Phase 0 — Ship What's In-Flight (feat_redis)

**Status**: Branch exists, most code written. Needs polish + story.

| Task | Output |
|---|---|
| Finalize `RedisDB` / `RedisConfig` | Merged, tested |
| Complete `001_pgvector_rag_example.ipynb` | Runnable end-to-end |
| Write `redis_example.ipynb` | Cache, pub/sub, streams basics |
| Update README with Redis + pgvector sections | Discoverability |
| PR → main | Release 0.8.0 |

---

## Phase 1 — Complete the Vector Story

### 1A. Redis Stack (Vector Search + Semantic Cache)

**Why**: The plain `redis:7` image doesn't ship with RedisSearch or RedisVL. The Stack image does, and it's what LangChain's `RedisSemanticCache` and `redisvl` actually need.

**What to build**:
- `RedisStackDB` + `RedisStackConfig` (image: `redis/redis-stack:latest`)
- Expose `RedisVL` client via `.connection`
- Notebook: **Semantic LLM response cache** — embed query → check Redis → skip OpenAI call on hit → show cost savings

**Why it's hot**: LLM API cost reduction is a top enterprise pain point right now.

### 1B. Elasticsearch / OpenSearch

**Why**: Hybrid search (BM25 keyword + kNN vector) consistently beats pure vector search in production RAG benchmarks. ES is the most deployed search backend.

**What to build**:
- `ElasticsearchDB` + `ElasticsearchConfig` (image: `elasticsearch:8`)
- `OpenSearchDB` variant (image: `opensearchproject/opensearch:2`)
- Notebook: **Hybrid RAG** — index docs with both dense vectors and BM25, use Reciprocal Rank Fusion, compare vs pgvector-only

**Why it's hot**: "Hybrid search" is one of the top RAG improvement techniques of 2024–2025.

---

## Phase 2 — Knowledge Graph Layer (GraphRAG)

### Neo4j

**Why**: Microsoft Research's GraphRAG paper (2024) triggered massive interest in graph-based retrieval. Neo4j is the dominant graph database with a production Docker image. LlamaIndex and LangChain both have Neo4j integrations.

**What to build**:
- `Neo4jDB` + `Neo4jConfig` (image: `neo4j:5`, default bolt port 7687 + HTTP 7474)
- Expose `neo4j.GraphDatabase.driver()` via `.connection`
- Notebook: **GraphRAG pipeline** — extract entity relationships from documents → store as graph → traverse graph for context-enriched retrieval → compare answer quality vs naive RAG

**Why it's hot**: GraphRAG is the current frontier of RAG research. Having a local Neo4j in one call is the exact pain point developers complain about.

### Apache AGE (Bonus — Postgres Graph Extension)

- Similar Dockerfile pattern to pgvector
- Enables graph queries inside Postgres — reduces infra footprint for smaller projects
- Lower priority than Neo4j but tells a good "Postgres does everything" story

---

## Phase 3 — LLM Inference Layer

### Ollama

**Why**: This is the wildcard that could 10x the library's audience. Ollama is the de facto standard for running local LLMs (Llama 3, Mistral, Phi, Gemma). It ships as a Docker image. Managing it the same way you manage a database — `OllamaManager.create_db()`, `manager.connection` returns an OpenAI-compatible client — is a genuinely novel idea.

**What to build**:
- `OllamaManager` + `OllamaConfig` (image: `ollama/ollama:latest`)
- `.pull_model(model_name)` method (calls Ollama pull API)
- `.connection` returns an `openai.OpenAI(base_url="http://localhost:11434/v1")` client
- Notebook: **Full local AI stack** — `OllamaManager` + `pgvector PostgresDB` + `Neo4jDB` = complete RAG system, zero cloud, zero cost

**Why it's hot**: "Run AI locally" is the top developer interest category right now. This would make the library's story: *"The entire AI infrastructure stack, locally, in Python."*

### LocalAI (Alternative/Complement)

- OpenAI-compatible API, broader model format support (GGUF, GPTQ)
- Docker image: `localai/localai:latest`
- Lower priority than Ollama but worth noting as a variant

---

## Phase 4 — Streaming & Async Pipelines

### Apache Kafka

**Why**: AI agents that call tools, process results, and chain actions are inherently async. Kafka is the standard message backbone for production AI pipelines. LangChain and LlamaIndex both have Kafka integrations.

**What to build**:
- `KafkaManager` + `KafkaConfig` (image: `apache/kafka:3`)
- Note: Kafka needs ZooKeeper or KRaft mode — use KRaft (built-in since Kafka 3.3) to keep it single-container
- `.connection` returns `confluent_kafka.Producer` / `Consumer`
- Notebook: **Async AI agent pipeline** — tasks flow through Kafka topics → multiple agent workers consume → results written to Postgres

**Why it's hot**: Agentic AI systems need reliable task queues. This is the infrastructure glue nobody wants to configure manually.

---

## Phase 5 — Observability Layer

### TimescaleDB

**Why**: Monitoring LLM latency, token costs, embedding drift, and eval scores over time is a time-series problem. TimescaleDB is Postgres + time-series — same Dockerfile pattern as pgvector.

**What to build**:
- `TimescaleDB` variant of `PostgresDB` (image: `timescale/timescaledb:latest-pg16`)
- Notebook: **LLM observability dashboard** — log every LLM call (latency, tokens, cost) to TimescaleDB → query rolling averages → detect regressions

**Why it's hot**: LLMOps/MLOps observability is a top enterprise priority.

### InfluxDB (Alternative)

- Purpose-built time series, less SQL-familiar but simpler for pure metrics
- Image: `influxdb:2`
- Useful if Timescale feels too Postgres-heavy

---

## Priority Ranking (Impact vs Effort)

| Priority | Addition | Effort | AI Narrative Fit | Audience |
|---|---|---|---|---|
| 🔴 Now | pgvector RAG notebook polish | Low | Vector RAG | All AI devs |
| 🔴 Now | Redis Stack semantic cache | Medium | Cost reduction | Enterprise |
| 🟠 Next | Neo4j + GraphRAG notebook | Medium-High | GraphRAG frontier | Research-aware devs |
| 🟠 Next | Elasticsearch hybrid search | Medium | Production RAG | ML engineers |
| 🟡 Soon | Ollama manager | High | Local AI stack | Indie/hobbyist devs |
| 🟡 Soon | TimescaleDB observability | Medium | LLMOps | MLOps engineers |
| 🟢 Later | Kafka async pipelines | High | Agentic AI | Platform engineers |
| 🟢 Later | Apache AGE | Low | Postgres story | Postgres fans |

---

## Content & Discoverability Plan

The library needs a **notebook series** that tells the story end-to-end:

| Notebook | Concept | Tags |
|---|---|---|
| `001_pgvector_rag_example.ipynb` | Basic vector RAG | rag, pgvector, llamaindex |
| `002_redis_semantic_cache.ipynb` | LLM semantic caching | redis, langchain, cost |
| `003_hybrid_search_rag.ipynb` | BM25 + vector hybrid | elasticsearch, rag, search |
| `004_graphrag_neo4j.ipynb` | GraphRAG pipeline | neo4j, graphrag, knowledge-graph |
| `005_local_ai_stack.ipynb` | Full local stack | ollama, pgvector, neo4j, local-llm |
| `006_llmops_observability.ipynb` | Monitoring LLM calls | timescaledb, mlops, metrics |
| `007_agent_pipeline_kafka.ipynb` | Async agent pipeline | kafka, agents, async |

Each notebook = a standalone shareable artifact (HuggingFace, Medium, Reddit r/LocalLLaMA).

---

## Positioning

**Tagline candidates**:
- *"The entire local AI infrastructure stack, in one `pip install`"*
- *"Stop fighting Docker. Start building AI."*
- *"pgvector, Neo4j, Redis, Ollama — one Pythonic API"*

**Comparison table for README**:

| Tool | What you'd normally do | With py-dockerdb |
|---|---|---|
| pgvector | Write Dockerfile, init SQL, manage container | `PostgresDB(PostgresConfig(dockerfile_path="Dockerfile.pgvector")).create_db()` |
| Neo4j | Pull image, set env vars, wait for bolt port | `Neo4jDB(Neo4jConfig()).create_db()` |
| Ollama | Install Ollama, manage process, remember flags | `OllamaManager(OllamaConfig(model="llama3")).create_db()` |
| Redis Stack | Pull stack image, configure modules | `RedisStackDB(RedisStackConfig()).create_db()` |

---

## Open Questions

1. **Scope boundary**: Does Ollama fit the "database management" framing, or should it live in a separate but related library? (Suggestion: keep it in, rename the library conceptually to "AI infrastructure manager")
2. **Docker Compose support**: Some stacks (Kafka + ZooKeeper, Weaviate + its deps) are multi-container. Worth adding a `ComposeManager` base class?
3. **GPU containers**: Ollama on GPU requires `--gpus all` flag — is that in scope?
4. **Hosted vector DBs**: Should there be a `QdrantDB` (purpose-built vector DB, single Docker container, excellent Python SDK) — probably yes, lower effort than Neo4j.
