#!/bin/bash

# Production Deployment Script for Gate.io Arbitrage Suite
# Run with: sudo ./deploy_production.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_info() { echo -e "ℹ $1"; }

echo "================================================"
echo "  Gate.io Arbitrage Suite Production Deployment"
echo "================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   print_error "Please run as root (use sudo)"
   exit 1
fi

# Check system requirements
print_info "Checking system requirements..."

# Check CPU cores
CPU_CORES=$(nproc)
if [ "$CPU_CORES" -lt 4 ]; then
    print_warning "Recommended: 4+ CPU cores (found: $CPU_CORES)"
fi

# Check memory
MEM_GB=$(free -g | awk '/^Mem:/{print $2}')
if [ "$MEM_GB" -lt 8 ]; then
    print_warning "Recommended: 8+ GB RAM (found: ${MEM_GB}GB)"
fi

# Check disk space
DISK_AVAILABLE=$(df / | awk 'NR==2 {print $4}')
DISK_GB=$((DISK_AVAILABLE / 1024 / 1024))
if [ "$DISK_GB" -lt 50 ]; then
    print_warning "Recommended: 50+ GB disk space (found: ${DISK_GB}GB)"
fi

# Install dependencies
print_info "Installing system dependencies..."
apt-get update
apt-get install -y \
    docker.io \
    docker-compose \
    git \
    curl \
    wget \
    htop \
    iotop \
    nethogs \
    ufw \
    fail2ban \
    certbot \
    python3-certbot-nginx

# Configure firewall
print_info "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 3000/tcp  # Grafana
ufw allow 9090/tcp  # Prometheus
print_success "Firewall configured"

# Setup environment
print_info "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.production .env
    print_warning "Created .env file - PLEASE EDIT WITH YOUR ACTUAL VALUES!"
    
    # Generate secure passwords
    print_info "Generating secure passwords..."
    ADMIN_PASS=$(openssl rand -base64 32)
    DB_PASS=$(openssl rand -base64 32)
    REDIS_PASS=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 48)
    
    # Update .env with generated passwords
    sed -i "s/CHANGE_THIS_STRONG_PASSWORD_123!/$ADMIN_PASS/g" .env
    sed -i "s/CHANGE_THIS_DATABASE_PASSWORD_789!/$DB_PASS/g" .env
    sed -i "s/CHANGE_THIS_REDIS_PASSWORD_012!/$REDIS_PASS/g" .env
    sed -i "s/CHANGE_THIS_JWT_SECRET_KEY_678!/$JWT_SECRET/g" .env
    
    # Save credentials
    cat > credentials.txt << EOF
=== IMPORTANT: SAVE THESE CREDENTIALS ===
Admin Password: $ADMIN_PASS
Database Password: $DB_PASS
Redis Password: $REDIS_PASS
JWT Secret: $JWT_SECRET
=========================================
EOF
    
    chmod 600 credentials.txt
    print_warning "Credentials saved to credentials.txt - KEEP THIS SECURE!"
fi

# Create necessary directories
print_info "Creating directories..."
mkdir -p {logs,data,backups,secrets,ssl}
chmod 700 secrets

# Setup SSL certificates
print_info "Setting up SSL certificates..."
read -p "Enter your domain name (or press Enter to skip SSL): " DOMAIN
if [ -n "$DOMAIN" ]; then
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN"
    
    # Copy certificates
    cp /etc/letsencrypt/live/"$DOMAIN"/fullchain.pem ssl/
    cp /etc/letsencrypt/live/"$DOMAIN"/privkey.pem ssl/
    chmod 600 ssl/*
    
    print_success "SSL certificates configured for $DOMAIN"
else
    print_warning "Skipping SSL setup - using HTTP only"
fi

# Create database initialization script
print_info "Creating database schema..."
cat > init.sql << 'EOF'
-- Arbitrage Suite Database Schema

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    strategy VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8),
    pnl DECIMAL(20, 8),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_trades_strategy ON trades(strategy);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    strategy VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 8) NOT NULL,
    labels JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metrics_name ON metrics(metric_name);
CREATE INDEX idx_metrics_timestamp ON metrics(timestamp);

-- Create read-only user for monitoring
CREATE USER monitor WITH PASSWORD 'monitor_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO monitor;
EOF

# Pull Docker images
print_info "Pulling Docker images..."
docker-compose -f production.yml pull

# Build custom images
print_info "Building custom Docker images..."
docker-compose -f production.yml build

# Initialize database
print_info "Initializing database..."
docker-compose -f production.yml up -d postgres
sleep 10  # Wait for postgres to start

# Start services
print_info "Starting all services..."
docker-compose -f production.yml up -d

# Wait for services to be healthy
print_info "Waiting for services to be healthy..."
sleep 30

# Check service status
print_info "Checking service status..."
docker-compose -f production.yml ps

# Setup cron jobs
print_info "Setting up cron jobs..."
cat > /etc/cron.d/arbitrage-suite << EOF
# Arbitrage Suite Maintenance Tasks
0 */6 * * * root docker system prune -f >> /var/log/docker-prune.log 2>&1
0 2 * * * root /usr/local/bin/backup-arbitrage.sh >> /var/log/backup.log 2>&1
*/5 * * * * root /usr/local/bin/health-check.sh >> /var/log/health.log 2>&1
EOF

# Create backup script
cat > /usr/local/bin/backup-arbitrage.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup database
docker exec gate-arb-postgres pg_dump -U arbitrage arbitrage > "$BACKUP_DIR/database.sql"

# Backup configurations
cp -r /opt/gate-arbitrage-suite/conf "$BACKUP_DIR/"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

# Remove old backups (keep last 7 days)
find /backups -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-arbitrage.sh

# Create health check script
cat > /usr/local/bin/health-check.sh << 'EOF'
#!/bin/bash
# Check if all services are running
SERVICES="hummingbot-prod gate-arb-backend-prod gate-arb-frontend-prod gate-arb-postgres gate-arb-redis"

for service in $SERVICES; do
    if ! docker ps | grep -q "$service"; then
        echo "WARNING: $service is not running!"
        # Attempt restart
        docker-compose -f /opt/gate-arbitrage-suite/deploy/production.yml restart "$service"
    fi
done
EOF

chmod +x /usr/local/bin/health-check.sh

# Setup log rotation
print_info "Configuring log rotation..."
cat > /etc/logrotate.d/arbitrage-suite << EOF
/opt/gate-arbitrage-suite/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
    sharedscripts
    postrotate
        docker-compose -f /opt/gate-arbitrage-suite/deploy/production.yml restart promtail
    endscript
}
EOF

# Performance tuning
print_info "Applying performance optimizations..."
cat >> /etc/sysctl.conf << EOF

# Arbitrage Suite Performance Tuning
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_notsent_lowat = 16384
EOF

sysctl -p

# Final summary
echo ""
echo "================================================"
print_success "Production deployment complete!"
echo "================================================"
echo ""
echo "Access points:"
echo "  Web UI: http://localhost:80"
echo "  API: http://localhost:8000"
echo "  Grafana: http://localhost:3000"
echo "  Prometheus: http://localhost:9090"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your actual values"
echo "2. Configure Gate.io API keys in Hummingbot"
echo "3. Review and adjust risk parameters"
echo "4. Start with small test trades"
echo ""
echo "Commands:"
echo "  View logs: docker-compose -f production.yml logs -f"
echo "  Stop all: docker-compose -f production.yml down"
echo "  Backup: /usr/local/bin/backup-arbitrage.sh"
echo ""
print_warning "Remember to secure your credentials.txt file!"
echo "================================================"