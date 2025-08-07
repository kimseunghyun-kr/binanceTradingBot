#!/bin/bash
set -e

echo "========================================="
echo "Starting Binance Trading Bot with Docker Compose"
echo "========================================="
echo ""

# Check if Docker socket exists and set permissions
if [ -e /var/run/docker.sock ]; then
    echo "Setting Docker socket permissions..."
    sudo chmod 666 /var/run/docker.sock || {
        echo "Warning: Could not set Docker socket permissions."
        echo "You may need to run: sudo chmod 666 /var/run/docker.sock"
    }
else
    echo "Warning: Docker socket not found at /var/run/docker.sock"
fi

# Check if .env.development exists
if [ ! -f .env.development ]; then
    echo "Creating .env.development from .env..."
    cp .env .env.development 2>/dev/null || {
        echo "Warning: .env file not found. Please create .env.development with your configuration."
    }
fi

echo ""
echo "Starting services with profiles: db and app"
echo "This will start:"
echo "  - MongoDB (master & slave with replica set)"
echo "  - Redis"
echo "  - PostgreSQL"
echo "  - FastAPI application"
echo "  - Celery worker"
echo "  - Nginx proxy"
echo ""

# Start all services with both profiles
docker compose --profile db --profile app up -d --build

echo ""
echo "Waiting for services to be ready..."
sleep 5

# Check service status
echo ""
echo "Service Status:"
echo "---------------"
docker compose ps

echo ""
echo "========================================="
echo "Services started successfully!"
echo "========================================="
echo ""
echo "Access points:"
echo "  - API: http://localhost:8000"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - GraphQL: http://localhost:8000/graphql"
echo "  - Nginx Proxy: http://localhost:80"
echo ""
echo "To view logs: docker compose logs -f [service_name]"
echo "To stop all: docker compose --profile db --profile app down"
echo ""