#!/bin/bash
# Start Gate.io Arbitrage Web UI

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running. Please start Docker and try again."
fi

# Check if .env file exists
if [ ! -f .env ]; then
    error ".env file not found. Please run install.sh first or copy .env.example to .env"
fi

# Load environment variables
set -o allexport
source .env
set +o allexport

# Validate required environment variables
if [ -z "$HUMMINGBOT_PATH" ] || [ "$HUMMINGBOT_PATH" = "/path/to/your/hummingbot" ]; then
    error "HUMMINGBOT_PATH not set in .env file. Please update it to your Hummingbot installation directory."
fi

if [ ! -d "$HUMMINGBOT_PATH" ]; then
    error "Hummingbot directory not found at $HUMMINGBOT_PATH. Please check the path in .env file."
fi

log "Starting Gate.io Arbitrage Web UI..."

# Check if containers are already running
if docker compose ps | grep -q "Up"; then
    warn "Some containers are already running. Stopping them first..."
    docker compose down
fi

# Create necessary directories
mkdir -p logs backend/logs nginx/ssl

# Build and start containers
log "Building and starting containers..."
docker compose up -d --build

# Wait for services to be ready
log "Waiting for services to start..."
sleep 10

# Check service health
log "Checking service health..."

# Check backend
if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    log "✅ Backend API is healthy"
else
    warn "❌ Backend API is not responding"
fi

# Check frontend
if curl -s http://localhost:8501/_stcore/health >/dev/null 2>&1; then
    log "✅ Frontend is healthy"
else
    warn "❌ Frontend is not responding"
fi

# Show status
log "Container Status:"
docker compose ps

log ""
log "🎉 Gate.io Arbitrage Web UI is starting!"
log ""
log "Access points:"
log "  Frontend (Streamlit): http://localhost:8501"
log "  Backend API:          http://localhost:8000"
log "  API Documentation:    http://localhost:8000/docs"
log ""
log "Default credentials:"
log "  Username: ${ADMIN_USERNAME:-admin}"
log "  Password: Check your .env file"
log ""
log "To view logs: docker compose logs -f"
log "To stop:      ./stop.sh"
log ""

# Optional: Open browser (commented out by default)
# if command -v xdg-open > /dev/null; then
#     xdg-open http://localhost:8501
# elif command -v open > /dev/null; then
#     open http://localhost:8501
# fi

exit 0