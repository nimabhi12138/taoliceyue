#!/bin/bash

# Start Gate.io Arbitrage Suite Web UI

echo "Starting Gate.io Arbitrage Suite Web UI..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Run ./install.sh first."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Start services
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 5

# Check service status
docker-compose ps

echo ""
echo "=========================================="
echo "Gate.io Arbitrage Suite Web UI Started!"
echo "=========================================="
echo "Web UI: http://localhost:${WEB_PORT:-8080}"
echo "API Docs: http://localhost:${API_PORT:-8000}/docs"
echo "Frontend: http://localhost:${FRONTEND_PORT:-8501}"
echo ""
echo "Username: ${ADMIN_USER:-admin}"
echo "Password: Check .env file"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: ./stop.sh"
echo "=========================================="