#!/bin/bash

# Stop Gate.io Arbitrage Suite Web UI

echo "Stopping Gate.io Arbitrage Suite Web UI..."

# Stop services
docker-compose down

echo "Web UI stopped successfully."