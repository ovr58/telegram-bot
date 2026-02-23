#!/bin/bash
set -e
echo "Creating pgvector extension..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "Restoring course database from custom-format dump..."
pg_restore -v -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /docker-entrypoint-initdb.d/course_data.dump 2>&1 || true
echo "Course database restore complete."
