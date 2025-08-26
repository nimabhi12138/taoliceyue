#!/bin/bash

# Gate.io Arbitrage Suite Web UI Installation Script
# For Ubuntu 22.04+

set -e

echo "=========================================="
echo "Gate.io Arbitrage Suite Web UI Installer"
echo "=========================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run as root. Use sudo when prompted."
   exit 1
fi

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed. Please log out and back in for group changes to take effect."
else
    echo "Docker is already installed."
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo apt install -y docker-compose-plugin
else
    echo "Docker Compose is already installed."
fi

# Create environment file
if [ ! -f .env ]; then
    echo "Creating environment configuration..."
    cp .env.example .env
    
    # Generate secure passwords
    ADMIN_PASS=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 32)
    
    # Update .env with secure values
    sed -i "s/your_secure_password_here/$ADMIN_PASS/g" .env
    sed -i "s/your_jwt_secret_key_here/$JWT_SECRET/g" .env
    
    echo "=========================================="
    echo "IMPORTANT: Save these credentials!"
    echo "Admin Username: admin"
    echo "Admin Password: $ADMIN_PASS"
    echo "=========================================="
    echo "You can change these in the .env file"
else
    echo ".env file already exists. Skipping..."
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p backend/logs
mkdir -p frontend/logs
mkdir -p nginx/ssl

# Build Docker images
echo "Building Docker images..."
docker-compose build

# Create Dockerfiles if they don't exist
if [ ! -f backend/Dockerfile ]; then
    cat > backend/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF
fi

if [ ! -f backend/requirements.txt ]; then
    cat > backend/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pyyaml==6.0.1
python-multipart==0.0.6
httpx==0.25.1
EOF
fi

if [ ! -f frontend/Dockerfile ]; then
    cat > frontend/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
EOF
fi

if [ ! -f frontend/requirements.txt ]; then
    cat > frontend/requirements.txt << 'EOF'
streamlit==1.28.2
requests==2.31.0
pandas==2.1.3
plotly==5.18.0
pyyaml==6.0.1
EOF
fi

# Create nginx config
if [ ! -f nginx/nginx.conf ]; then
    cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }
    
    upstream frontend {
        server frontend:8501;
    }
    
    server {
        listen 80;
        server_name _;
        
        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Backend API
        location /api/ {
            rewrite ^/api/(.*) /$1 break;
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # WebSocket support for Streamlit
        location /_stcore/stream {
            proxy_pass http://frontend/_stcore/stream;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
        }
    }
}
EOF
fi

echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To start the Web UI, run: ./start.sh"
echo "To stop the Web UI, run: ./stop.sh"
echo ""
echo "Access the Web UI at: http://localhost:8080"
echo "API documentation at: http://localhost:8000/docs"
echo ""
echo "Default credentials are in the .env file"
echo "=========================================="