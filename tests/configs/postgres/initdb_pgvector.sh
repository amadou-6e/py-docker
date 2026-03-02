#!/bin/bash
set -e

# Ensure essential variables are set
if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_PASSWORD" ]]; then
  echo "ERROR: POSTGRES_USER and POSTGRES_PASSWORD must be set." >&2
  exit 1
fi

VECTOR_DB_NAME="${VECTOR_DB_NAME:-vector_db}"

# Create vector DB if needed.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
SELECT format('CREATE DATABASE %I', '${VECTOR_DB_NAME}')
WHERE NOT EXISTS (
  SELECT 1 FROM pg_database WHERE datname = '${VECTOR_DB_NAME}'
)\gexec
EOSQL

# Enable pgvector and create a compatibility table.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$VECTOR_DB_NAME" <<-EOSQL
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS test_table (
  id SERIAL PRIMARY KEY,
  name TEXT
);
EOSQL
