#!/bin/bash

echo "========================================="
echo "Stopping Binance Trading Bot Services"
echo "========================================="
echo ""

# Stop all services with both profiles
docker compose --profile db --profile app down

if [ $? -eq 0 ]; then
    echo ""
    echo "All services stopped successfully!"
else
    echo ""
    echo "Warning: Some services may not have stopped properly."
    echo "You can check with: docker ps"
fi

echo ""