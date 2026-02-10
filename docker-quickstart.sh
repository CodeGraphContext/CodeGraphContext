#!/bin/bash

# CodeGraphContext Docker Quick Start Script
# This script helps you quickly set up and run CodeGraphContext in Docker

set -e

echo "🚀 CodeGraphContext Docker Quick Start"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

# Use docker-compose or docker compose based on availability
DOCKER_COMPOSE="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Copy template if docker-compose.yml doesn't exist
if [ ! -f "docker-compose.yml" ]; then
    echo "📋 Creating docker-compose.yml from template..."
    cp docker-compose.template.yml docker-compose.yml
    echo "✅ docker-compose.yml created"
else
    echo "ℹ️  docker-compose.yml already exists"
fi
echo ""

# Ask user which database to use
echo "Which database would you like to use?"
echo "1) FalkorDB Lite (default, lightweight, built-in)"
echo "2) Neo4j (production-grade, requires more resources)"
read -p "Enter choice [1-2] (default: 1): " db_choice
db_choice=${db_choice:-1}
echo ""

# Build the image
echo "🔨 Building CodeGraphContext Docker image..."
$DOCKER_COMPOSE build codegraphcontext
echo "✅ Image built successfully"
echo ""

# Start services based on choice
if [ "$db_choice" = "2" ]; then
    echo "🚀 Starting CodeGraphContext with Neo4j..."
    $DOCKER_COMPOSE --profile neo4j up -d
    echo ""
    echo "✅ Services started!"
    echo ""
    echo "📊 Neo4j Browser: http://localhost:7474"
    echo "   Username: neo4j"
    echo "   Password: codegraph123"
    echo ""
    echo "⚙️  To configure CodeGraphContext to use Neo4j:"
    echo "   $DOCKER_COMPOSE exec codegraphcontext bash"
    echo "   cgc neo4j setup"
    echo "   (Use URI: bolt://neo4j:7687, Username: neo4j, Password: codegraph123)"
else
    echo "🚀 Starting CodeGraphContext with FalkorDB Lite..."
    $DOCKER_COMPOSE up -d codegraphcontext
    echo ""
    echo "✅ Service started!"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📝 Quick commands:"
echo "   Access container:  $DOCKER_COMPOSE exec codegraphcontext bash"
echo "   View logs:         $DOCKER_COMPOSE logs -f codegraphcontext"
echo "   Stop services:     $DOCKER_COMPOSE down"
echo "   Restart services:  $DOCKER_COMPOSE restart"
echo ""
echo "💡 Inside the container, you can use cgc commands:"
echo "   cgc index .              # Index current directory"
echo "   cgc list                 # List indexed repositories"
echo "   cgc analyze callers fn   # Find function callers"
echo "   cgc help                 # Show all commands"
echo ""
echo "📚 For more information, see DOCKER_DEPLOYMENT.md"
echo ""

# Ask if user wants to enter the container
read -p "Would you like to enter the container now? [y/N]: " enter_container
if [[ $enter_container =~ ^[Yy]$ ]]; then
    echo ""
    echo "🐚 Entering container..."
    $DOCKER_COMPOSE exec codegraphcontext bash
fi
