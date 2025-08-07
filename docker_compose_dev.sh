#!/bin/bash
set -e

echo "========================================="
echo "Starting Development Environment (DB only)"
echo "========================================="
echo ""

# Check if Docker socket exists and set permissions
if [ -e /var/run/docker.sock ]; then
    echo "Setting Docker socket permissions..."
    sudo chmod 666 /var/run/docker.sock || {
        echo "Warning: Could not set Docker socket permissions."
        echo "You may need to run: sudo chmod 666 /var/run/docker.sock"
    }
fi

# Check if .env.development exists
if [ ! -f .env.development ]; then
    echo "Creating .env.development from .env..."
    cp .env .env.development 2>/dev/null || {
        echo "Warning: .env file not found. Please create .env.development with your configuration."
    }
fi

echo ""
echo "Starting database services only (profile: db)"
echo "This will start:"
echo "  - MongoDB master (port 27017)"
echo "  - MongoDB slave (port 27018)"
echo "  - Redis (port 6379)"
echo "  - PostgreSQL (port 5432)"
echo "  - Mongo replica set initialization"
echo ""

# Start DB services only
docker compose --profile db up -d

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to start database services!"
    echo "Please check Docker is running."
    exit 1
fi

echo ""
echo "Waiting for databases to be ready..."
sleep 8

echo ""
echo "Database Status:"
echo "----------------"
docker compose --profile db ps

echo ""
echo "========================================="
echo "Database services ready for development!"
echo "========================================="
echo ""
echo "Now you can run locally:"
echo "  1. Start Celery Worker: python worker.py"
echo "  2. Start FastAPI: python run_local.py"
echo ""
echo "MongoDB replica set is automatically initialized."
echo ""
echo "To stop databases: docker compose --profile db down"
echo ""