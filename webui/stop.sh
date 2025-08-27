#!/bin/bash
# Stop Gate.io Arbitrage Web UI

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

log "Stopping Gate.io Arbitrage Web UI..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    warn "Docker is not running, but attempting to stop containers anyway..."
fi

# Stop containers
if docker compose ps | grep -q "Up"; then
    log "Stopping running containers..."
    docker compose down
    
    # Wait a moment for graceful shutdown
    sleep 5
    
    log "✅ All containers stopped successfully"
else
    log "No running containers found"
fi

# Optional: Clean up (uncomment if you want to remove images and volumes)
# if [ "$1" = "--clean" ]; then
#     log "Cleaning up images and volumes..."
#     docker compose down --rmi all --volumes --remove-orphans
#     log "✅ Cleanup completed"
# fi

log "Gate.io Arbitrage Web UI has been stopped"
log ""
log "To start again: ./start.sh"
log "To clean up completely: docker compose down --rmi all --volumes"

exit 0