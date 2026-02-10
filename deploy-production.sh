#!/bin/bash

# CodeGraphContext - Production Deployment Script
# This script automates the deployment of CodeGraphContext to a cloud VM

set -e

echo "🚀 CodeGraphContext Production Deployment"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_warning "Please do not run as root. Run as a regular user with sudo privileges."
    exit 1
fi

# System check
print_info "Checking system requirements..."

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_success "OS: $NAME $VERSION"
else
    print_error "Cannot determine OS. This script requires Ubuntu/Debian."
    exit 1
fi

# Update system
print_info "Updating system packages..."
sudo apt-get update -qq
print_success "System updated"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    print_info "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    print_success "Docker installed"
else
    print_success "Docker already installed: $(docker --version)"
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_info "Installing Docker Compose..."
    sudo apt-get install -y docker-compose-plugin
    print_success "Docker Compose installed"
else
    print_success "Docker Compose already installed"
fi

# Install git if not present
if ! command -v git &> /dev/null; then
    print_info "Installing Git..."
    sudo apt-get install -y git
    print_success "Git installed"
fi

# Install other useful tools
print_info "Installing additional tools..."
sudo apt-get install -y curl wget htop vim ufw -qq
print_success "Additional tools installed"

# Configure firewall
print_info "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 7474/tcp comment 'Neo4j HTTP'
sudo ufw allow 7687/tcp comment 'Neo4j Bolt'
print_success "Firewall configured"

# Ask for deployment directory
read -p "Enter deployment directory (default: ~/codegraphcontext): " DEPLOY_DIR
DEPLOY_DIR=${DEPLOY_DIR:-~/codegraphcontext}

# Create deployment directory
mkdir -p $DEPLOY_DIR
cd $DEPLOY_DIR

# Clone or update repository
if [ -d ".git" ]; then
    print_info "Updating existing repository..."
    git pull
else
    print_info "Cloning repository..."
    git clone https://github.com/Shashankss1205/CodeGraphContext.git .
fi
print_success "Repository ready"

# Copy docker-compose template
if [ ! -f "docker-compose.yml" ]; then
    print_info "Creating docker-compose.yml..."
    cp docker-compose.template.yml docker-compose.yml
    print_success "docker-compose.yml created"
fi

# Ask for database choice
echo ""
print_info "Database Selection"
echo "1) FalkorDB Lite (default, lightweight)"
echo "2) Neo4j (production-grade)"
read -p "Choose database [1-2] (default: 1): " DB_CHOICE
DB_CHOICE=${DB_CHOICE:-1}

# Configure Neo4j password if selected
if [ "$DB_CHOICE" = "2" ]; then
    echo ""
    print_info "Neo4j Configuration"
    read -sp "Enter Neo4j password (default: codegraph123): " NEO4J_PASSWORD
    echo ""
    NEO4J_PASSWORD=${NEO4J_PASSWORD:-codegraph123}
    
    # Update docker-compose.yml with new password
    sed -i "s/NEO4J_AUTH=neo4j\/codegraph123/NEO4J_AUTH=neo4j\/$NEO4J_PASSWORD/" docker-compose.yml
    print_success "Neo4j password configured"
fi

# Build and start services
echo ""
print_info "Building Docker images..."
docker-compose build --no-cache

if [ "$DB_CHOICE" = "2" ]; then
    print_info "Starting services with Neo4j..."
    docker-compose --profile neo4j up -d
else
    print_info "Starting services with FalkorDB Lite..."
    docker-compose up -d codegraphcontext
fi

# Wait for services to start
print_info "Waiting for services to start..."
sleep 10

# Check service status
if docker-compose ps | grep -q "Up"; then
    print_success "Services started successfully!"
else
    print_error "Services failed to start. Check logs with: docker-compose logs"
    exit 1
fi

# Display service information
echo ""
echo "=========================================="
print_success "Deployment Complete!"
echo "=========================================="
echo ""
print_info "Service Information:"
echo "  - CodeGraphContext: Running"
if [ "$DB_CHOICE" = "2" ]; then
    echo "  - Neo4j Browser: http://$(curl -s ifconfig.me):7474"
    echo "  - Neo4j Bolt: bolt://$(curl -s ifconfig.me):7687"
    echo "  - Neo4j Username: neo4j"
    echo "  - Neo4j Password: $NEO4J_PASSWORD"
fi
echo ""
print_info "Useful Commands:"
echo "  - Access container: docker-compose exec codegraphcontext bash"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo ""
print_info "Next Steps:"
echo "  1. Access the container: docker-compose exec codegraphcontext bash"
echo "  2. Index your code: cgc index /workspace"
echo "  3. Query the graph: cgc list"
echo ""

# Create systemd service for auto-start
read -p "Create systemd service for auto-start on boot? [y/N]: " CREATE_SERVICE
if [[ $CREATE_SERVICE =~ ^[Yy]$ ]]; then
    print_info "Creating systemd service..."
    
    sudo tee /etc/systemd/system/codegraphcontext.service > /dev/null <<EOF
[Unit]
Description=CodeGraphContext Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=$USER

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable codegraphcontext.service
    print_success "Systemd service created and enabled"
fi

# Setup automatic backups
read -p "Setup automatic daily backups? [y/N]: " SETUP_BACKUPS
if [[ $SETUP_BACKUPS =~ ^[Yy]$ ]]; then
    print_info "Setting up automatic backups..."
    
    # Create backup script
    cat > $DEPLOY_DIR/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=~/codegraphcontext-backups
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d-%H%M%S)
docker run --rm -v cgc-data:/data -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/cgc-backup-$DATE.tar.gz /data
# Keep only last 7 backups
ls -t $BACKUP_DIR/cgc-backup-*.tar.gz | tail -n +8 | xargs -r rm
echo "Backup completed: cgc-backup-$DATE.tar.gz"
EOF
    
    chmod +x $DEPLOY_DIR/backup.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $DEPLOY_DIR/backup.sh >> $DEPLOY_DIR/backup.log 2>&1") | crontab -
    
    print_success "Daily backups configured (runs at 2 AM)"
    print_info "Backup location: ~/codegraphcontext-backups"
fi

# Security recommendations
echo ""
print_warning "Security Recommendations:"
echo "  1. Change Neo4j password (if using Neo4j)"
echo "  2. Configure SSL/TLS with a reverse proxy (nginx/Traefik)"
echo "  3. Restrict firewall rules to specific IPs if possible"
echo "  4. Enable automatic security updates"
echo "  5. Regularly backup your data"
echo ""

# Monitoring setup
read -p "Install monitoring tools (htop, ctop)? [y/N]: " INSTALL_MONITORING
if [[ $INSTALL_MONITORING =~ ^[Yy]$ ]]; then
    print_info "Installing monitoring tools..."
    sudo apt-get install -y htop
    
    # Install ctop (container monitoring)
    sudo wget https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-linux-amd64 \
        -O /usr/local/bin/ctop
    sudo chmod +x /usr/local/bin/ctop
    
    print_success "Monitoring tools installed"
    print_info "Use 'htop' for system monitoring and 'ctop' for container monitoring"
fi

echo ""
print_success "🎉 Production deployment complete!"
print_info "For more information, see DOCKER_DEPLOYMENT.md"
echo ""

# Ask if user wants to enter container
read -p "Enter the container now? [y/N]: " ENTER_CONTAINER
if [[ $ENTER_CONTAINER =~ ^[Yy]$ ]]; then
    docker-compose exec codegraphcontext bash
fi
