# Docker Deployment Guide for CodeGraphContext

This guide explains how to build, run, and deploy CodeGraphContext using Docker.

## 📦 Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Copy the template file:**
   ```bash
   cp docker-compose.template.yml docker-compose.yml
   ```

2. **Start CodeGraphContext with FalkorDB Lite (default):**
   ```bash
   docker-compose up -d codegraphcontext
   ```

3. **Access the container:**
   ```bash
   docker-compose exec codegraphcontext bash
   ```

4. **Inside the container, use cgc commands:**
   ```bash
   cgc index .
   cgc list
   cgc analyze callers my_function
   ```

### Option 2: Using Docker Directly

1. **Build the image:**
   ```bash
   docker build -t codegraphcontext:latest .
   ```

2. **Run the container:**
   ```bash
   docker run -it --rm \
     -v $(pwd):/workspace \
     -v cgc-data:/root/.codegraphcontext \
     codegraphcontext:latest bash
   ```

3. **Use cgc commands inside the container:**
   ```bash
   cgc index .
   cgc help
   ```

## 🗄️ Database Options

### FalkorDB Lite (Default - Included in Container)

FalkorDB Lite is built into the Docker image and requires no additional setup. It's perfect for:
- Development and testing
- Single-user scenarios
- Quick analysis tasks

**No additional configuration needed!** Just start the container and use `cgc` commands.

### Neo4j (Optional - For Production)

If you need a production-grade database, you can use Neo4j:

1. **Start both CodeGraphContext and Neo4j:**
   ```bash
   docker-compose --profile neo4j up -d
   ```

2. **Configure CodeGraphContext to use Neo4j:**
   ```bash
   docker-compose exec codegraphcontext bash
   cgc neo4j setup
   ```
   
   When prompted, use:
   - URI: `bolt://neo4j:7687`
   - Username: `neo4j`
   - Password: `codegraph123`

3. **Access Neo4j Browser:**
   Open http://localhost:7474 in your browser

## 📊 Volume Mounts

The Docker setup uses two types of volumes:

1. **Workspace Volume** (`./:/workspace`):
   - Mounts your current directory into the container
   - Allows CodeGraphContext to index your code
   - Changes are bidirectional

2. **Data Volume** (`cgc-data:/root/.codegraphcontext`):
   - Persists database files and configuration
   - Survives container restarts
   - Keeps your indexed data safe

## 🚀 Common Usage Patterns

### Index a Project

```bash
# Start the container
docker-compose up -d codegraphcontext

# Access the container
docker-compose exec codegraphcontext bash

# Index the current directory
cgc index .

# List indexed repositories
cgc list
```

### Run as MCP Server

```bash
# Start the container with MCP server
docker-compose run --rm -p 8080:8080 codegraphcontext cgc mcp start
```

### Watch for Changes

```bash
docker-compose exec codegraphcontext cgc watch /workspace
```

### One-off Analysis

```bash
# Run a single command without entering the container
docker-compose run --rm codegraphcontext cgc analyze complexity --threshold 10
```

## 🌐 Hosting Online

### Option 1: Cloud VM (AWS, GCP, Azure, DigitalOcean)

1. **Provision a VM** (Ubuntu 22.04 recommended):
   - Minimum: 2 vCPUs, 4GB RAM
   - Recommended: 4 vCPUs, 8GB RAM

2. **Install Docker and Docker Compose:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo apt-get install docker-compose-plugin
   ```

3. **Clone your repository:**
   ```bash
   git clone https://github.com/CodeGraphContext/CodeGraphContext.git
   cd CodeGraphContext
   ```

4. **Start the services:**
   ```bash
   cp docker-compose.template.yml docker-compose.yml
   docker-compose --profile neo4j up -d
   ```

5. **Configure firewall:**
   ```bash
   # For Neo4j Browser
   sudo ufw allow 7474/tcp
   sudo ufw allow 7687/tcp
   ```

### Option 2: Container Platforms

#### Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/codegraphcontext

# Deploy to Cloud Run
gcloud run deploy codegraphcontext \
  --image gcr.io/YOUR_PROJECT_ID/codegraphcontext \
  --platform managed \
  --region us-central1 \
  --memory 2Gi
```

#### AWS ECS/Fargate

1. **Push to ECR:**
   ```bash
   aws ecr create-repository --repository-name codegraphcontext
   docker tag codegraphcontext:latest YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/codegraphcontext:latest
   docker push YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/codegraphcontext:latest
   ```

2. **Create ECS Task Definition** and deploy using AWS Console or CLI

#### Azure Container Instances

```bash
# Create resource group
az group create --name cgc-rg --location eastus

# Create container instance
az container create \
  --resource-group cgc-rg \
  --name codegraphcontext \
  --image codegraphcontext:latest \
  --cpu 2 \
  --memory 4
```

### Option 3: Kubernetes (For Scale)

1. **Create deployment:**
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: codegraphcontext
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: codegraphcontext
     template:
       metadata:
         labels:
           app: codegraphcontext
       spec:
         containers:
         - name: codegraphcontext
           image: codegraphcontext:latest
           volumeMounts:
           - name: cgc-data
             mountPath: /root/.codegraphcontext
         volumes:
         - name: cgc-data
           persistentVolumeClaim:
             claimName: cgc-pvc
   ```

2. **Apply configuration:**
   ```bash
   kubectl apply -f deployment.yaml
   ```

### Option 4: Self-Hosted with Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml cgc
```

## 🔒 Security Considerations

1. **Change default Neo4j password:**
   Edit `docker-compose.yml` and update `NEO4J_AUTH`

2. **Use environment variables for secrets:**
   ```bash
   docker-compose run --rm \
     -e NEO4J_PASSWORD=your_secure_password \
     codegraphcontext bash
   ```

3. **Enable HTTPS** for production deployments using reverse proxy (nginx, Traefik)

4. **Restrict network access:**
   - Use firewall rules
   - Configure security groups
   - Use VPN for sensitive codebases

## 🔧 Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs codegraphcontext

# Rebuild image
docker-compose build --no-cache codegraphcontext
```

### Database connection issues
```bash
# Verify Neo4j is running
docker-compose ps

# Check Neo4j logs
docker-compose logs neo4j

# Test connection
docker-compose exec codegraphcontext cgc query "MATCH (n) RETURN count(n)"
```

### Out of memory
```bash
# Increase Docker memory limit in Docker Desktop settings
# Or for Neo4j, edit docker-compose.yml:
NEO4J_dbms_memory_heap_max__size=4G
```

## 📈 Performance Optimization

1. **Use volumes for large codebases:**
   ```yaml
   volumes:
     - type: volume
       source: cgc-data
       target: /root/.codegraphcontext
   ```

2. **Allocate more resources:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '4'
         memory: 8G
   ```

3. **Use SSD storage** for database volumes in production

## 🎯 Production Checklist

- [ ] Change default passwords
- [ ] Configure persistent volumes
- [ ] Set up automated backups
- [ ] Configure monitoring and logging
- [ ] Enable HTTPS/TLS
- [ ] Set resource limits
- [ ] Configure health checks
- [ ] Set up CI/CD pipeline
- [ ] Document deployment process
- [ ] Test disaster recovery

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Neo4j Docker Guide](https://neo4j.com/developer/docker/)
- [CodeGraphContext Documentation](https://CodeGraphContext.github.io/CodeGraphContext/)

## 💡 Tips

- Use `.cgcignore` to exclude files from indexing
- Mount specific directories instead of entire filesystem
- Use Docker networks for service isolation
- Implement log rotation for long-running containers
- Consider using Docker secrets for sensitive data
