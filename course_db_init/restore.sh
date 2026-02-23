#!/bin/bash
set -e
echo "Restoring course database from custom-format dump..."
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges /docker-entrypoint-initdb.d/course_data.dump || true
echo "Course database restore complete."
