# Marketing Prose: py-dockerdb

**Target audience:** Python instructors and demo authors (primary), learners and MVP builders comparing databases (secondary)
**Keyword targets:** python notebook docker database, jupyter database tutorial, easy docker database setup python, pythonic sql database setup, pythonic docker database management, mvp database comparison python, compare postgres mysql mongodb mssql, local rag database setup python, rag prototype postgres docker, rag prototype mongodb docker

---

## 1. README Hero Section

# py-dockerdb

*Pythonic Docker database management for notebooks, tutorials, and fast MVPs.*

[![Build](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your-org/py-dockerdb/actions)
[![PyPI](https://img.shields.io/badge/pypi-v0.8.0-blue)](https://pypi.org/project/py-dockerdb/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](./LICENSE)

`py-dockerdb` gives you easy Docker database setup in Python for PostgreSQL, MySQL, MongoDB, and Microsoft SQL Server. It is built for people who teach, demo, and prototype with notebooks or scripts and need repeatable local databases in minutes. Instead of writing Docker commands and per-engine setup code, you use one API to create, start, connect, and clean up containers.

Switch from PostgreSQL to MongoDB and back without changing a line of connection code. This makes side-by-side database comparison a first-class workflow - useful for MVPs where the right engine isn't decided yet, and for RAG experiments where you want to test one storage backend, then swap it out without rewriting environment glue.

If you teach SQL or data workflows, it removes the environment-setup section from your slides entirely: every student runs the same two lines and gets a working database.

---

## 2. PyPI Long Description Intro

py-dockerdb is a Python package for easy Docker database setup across PostgreSQL, MySQL, MongoDB, and Microsoft SQL Server. It gives you a pythonic SQL database setup workflow for notebooks, tutorials, and MVPs: define a config, create the containerized database, connect, and tear it down with the same interface. For instructors and demo authors, this removes repetitive environment prep and makes sessions reproducible on local machines and CI. For learners and builders, it simplifies side-by-side database comparison and rapid prototyping, including local RAG database setup in Python when you want to test different storage options quickly.

---

## 3. GitHub "About" One-Liner

Spin up PostgreSQL, MySQL, MongoDB, or MSSQL from a notebook in two lines - no Docker commands, no per-engine setup code.

---

## 4. Social Share Blurb

If you teach SQL or run data workshops, `py-dockerdb` lets you drop the environment setup section from your slides entirely - every student runs two lines and gets a working database. It also handles side-by-side engine comparison and local RAG prototypes across PostgreSQL, MySQL, MongoDB, and MSSQL. One interface, no Docker commands, no per-engine glue.

---

## 5. Documentation Meta Description

py-dockerdb provides easy Docker database setup in Python for notebooks, tutorials, MVP database comparison, and quick local RAG prototypes across SQL and NoSQL.

---

## Audience Cards Considered

> These were the candidate audiences evaluated in Phase 1. Preserved here so you can
> revisit targeting without starting from scratch.

### Audience: Python instructors and demo authors
**Who they are:** Developers and educators who teach SQL, data engineering, or backend workflows via notebooks, workshops, or recorded tutorials. They spend significant prep time on environment setup before a session even starts.
**Their pain point:** Every student has a different machine. Docker commands differ by OS, per-engine setup varies, and one broken environment derails a class. They need something reproducible that doesn't require a Docker explanation mid-lesson.
**Why this framing works:** py-dockerdb removes the environment section from the lesson plan entirely. That's a tangible time saving with a clear before/after.
**Where they gather:** Real Python, YouTube (Corey Schafer, Tech With Tim), PyData conferences, r/learnpython, Jupyter community forum, O'Reilly learning platform.
**Elevator pitch:** Stop writing Docker setup instructions in your README. py-dockerdb gives every student a running PostgreSQL, MySQL, MongoDB, or MSSQL instance in two lines of Python - same result, every machine.
**Keywords they search for:** jupyter database tutorial, python classroom database setup, reproducible notebook database, docker database python teaching

### Audience: Learners and MVP builders comparing databases
**Who they are:** Developers building early-stage products or working through database selection. They know Python but may not have deep Docker or DBA experience. They want to test PostgreSQL vs MongoDB vs MSSQL without provisioning cloud infrastructure.
**Their pain point:** Comparing databases locally means learning each engine's Docker image, port conventions, and connection string format separately. The comparison work drowns in environment work.
**Why this framing works:** A single interface across all four engines turns a multi-day yak-shave into an afternoon experiment.
**Where they gather:** Hacker News (Show HN), r/Python, r/dataengineering, Indie Hackers, Dev.to, Discord servers for FastAPI / SQLAlchemy.
**Elevator pitch:** Switch from PostgreSQL to MongoDB and back without changing a line of connection code. py-dockerdb makes database comparison a one-afternoon experiment instead of a multi-engine setup project.
**Keywords they search for:** compare postgres mysql mongodb python, local database comparison python, mvp database setup python, easy docker database python

### Audience: RAG and AI prototype builders
**Who they are:** ML engineers and applied AI developers spinning up retrieval-augmented generation prototypes. They need a vector-capable or document store backend fast, want to swap it out if it doesn't fit, and don't want to manage infrastructure while the architecture is still fluid.
**Their pain point:** Setting up and tearing down database backends during prototyping is friction that interrupts the actual experiment. Cloud databases add latency and cost during iteration.
**Why this framing works:** Local, disposable, swappable databases are exactly what RAG prototyping needs. py-dockerdb frames this as a feature, not a workaround.
**Where they gather:** LangChain Discord, LlamaIndex community, Hugging Face forums, r/LocalLLaMA, AI-focused newsletters (The Batch, TLDR AI).
**Elevator pitch:** Run your RAG prototype against PostgreSQL with pgvector, then swap to MongoDB Atlas-compatible local storage in one config change. py-dockerdb keeps your local AI experiments clean and reproducible without touching cloud infrastructure.
**Keywords they search for:** local rag database setup python, rag prototype postgres docker, pgvector local python, mongodb rag prototype local