#!/bin/bash
set -e

# Start DB services in the background (if not already running)
docker compose up -d mongo-init postgres redis

# Wait for services to be healthy (optional, see below for more robust way)
# Wait for Mongo to be ready
until nc -z localhost 27017; do
  echo "Waiting for MongoDB..."
  sleep 1
done
until nc -z localhost 27018; do
  echo "Waiting for MongoDB..."
  sleep 1
done
# Wait for Postgres to be ready
until nc -z localhost 5432; do
  echo "Waiting for Postgres..."
  sleep 1
done
# Wait for Redis to be ready
until nc -z localhost 6379; do
  echo "Waiting for Redis..."

  sleep 1
done
